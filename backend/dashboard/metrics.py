"""The numbers behind the dashboard. Pure pandas, no database or Streamlit,
so every calculation here can be unit tested.

`answers` is one row per answered attempt with the columns:
    user_id, question_id, mode, shown_at (timezone-aware), response_ms,
    is_correct (bool), timed_out (bool), chosen_index (original option index or None)
"""

import math
from datetime import date, timedelta

import pandas as pd

# Same rules as scripts/question_report.py
BANDS = {"easy": (0, 1400), "medium": (1400, 1600), "hard": (1600, 10_000)}
CALIBRATED_RD = 150
MIN_ANSWERS = 10  # fewer than this and a question's stats are mostly noise
KEY_CHECK_Z = 2.0  # how clearly a wrong option must beat the right one to suspect the key

# Time limits: give people 1.5x the time that 90% of correct answers needed.
TIME_FACTOR = 1.5
TIGHT_TIMEOUT_RATE = 0.2  # a fifth of players running out of time is too many
LOOSE_SHARE = 0.5  # suggested limit under half the current one: it's too generous
MIN_LIMIT_S, MAX_LIMIT_S = 5, 300


def local_days(answers: pd.DataFrame, tz: str) -> pd.Series:
    """Calendar day of each answer in the given timezone."""
    return answers["shown_at"].dt.tz_convert(tz).dt.date


# ------------------------------------------------------------------ activity
def daily_activity(answers: pd.DataFrame, tz: str) -> pd.DataFrame:
    """Players and answers per day, with quiet days filled in as zeros."""
    columns = ["day", "players", "solo", "match"]
    if answers.empty:
        return pd.DataFrame(columns=columns)
    df = answers.assign(day=local_days(answers, tz))
    per_day = df.groupby("day").agg(players=("user_id", "nunique"))
    by_mode = df.pivot_table(index="day", columns="mode", values="user_id", aggfunc="size")
    per_day = per_day.join(by_mode.reindex(columns=["solo", "match"])).fillna(0)
    all_days = pd.date_range(min(per_day.index), max(per_day.index), freq="D").date
    per_day = per_day.reindex(all_days, fill_value=0)
    per_day.index.name = "day"
    return per_day.reset_index()[columns].astype({"players": int, "solo": int, "match": int})


def answers_by_hour(answers: pd.DataFrame, tz: str) -> pd.DataFrame:
    """How many answers land in each hour of the day: when do people play?"""
    hours = answers["shown_at"].dt.tz_convert(tz).dt.hour
    counts = hours.value_counts().reindex(range(24), fill_value=0)
    return pd.DataFrame({"hour": range(24), "answers": counts.to_numpy()})


# ------------------------------------------------------------------ retention
def _activity(answers: pd.DataFrame, tz: str) -> pd.DataFrame:
    """One row per player per active day, with the player's first day."""
    df = pd.DataFrame({"user_id": answers["user_id"], "day": local_days(answers, tz)})
    df = df.drop_duplicates()
    df["first_day"] = df.groupby("user_id")["day"].transform("min")
    return df


def return_rates(answers: pd.DataFrame, tz: str, today: date) -> dict:
    """Share of players who came back the day after their first day, and within
    a week of it. Only players who've had the chance to come back count."""
    result = {"next_day": None, "next_day_players": 0, "within_week": None, "within_week_players": 0}
    if answers.empty:
        return result
    df = _activity(answers, tz)
    df["offset"] = [(d - f).days for d, f in zip(df["day"], df["first_day"], strict=True)]
    firsts = df.groupby("user_id")["first_day"].first()

    for key, wait, window in (("next_day", 1, (1, 1)), ("within_week", 7, (1, 7))):
        eligible = firsts[firsts <= today - timedelta(days=wait)].index
        if len(eligible) == 0:
            continue
        came_back = df[df["offset"].between(*window) & df["user_id"].isin(eligible)]["user_id"].nunique()
        result[key] = came_back / len(eligible)
        result[f"{key}_players"] = len(eligible)
    return result


def weekly_cohorts(answers: pd.DataFrame, tz: str, today: date) -> pd.DataFrame:
    """Players grouped by the week they started (Monday). For each week since,
    the share of the group that played at least once that week."""
    columns = ["cohort", "size", "week", "players", "share"]
    if answers.empty:
        return pd.DataFrame(columns=columns)
    df = _activity(answers, tz)

    def monday(d: date) -> date:
        return d - timedelta(days=d.weekday())

    df["cohort"] = df["first_day"].map(monday)
    df["week"] = [(monday(d) - c).days // 7 for d, c in zip(df["day"], df["cohort"], strict=True)]
    sizes = df.groupby("cohort")["user_id"].nunique()
    active = df.groupby(["cohort", "week"])["user_id"].nunique()

    rows = []
    for cohort, size in sizes.items():
        weeks_elapsed = (monday(today) - cohort).days // 7
        for week in range(weeks_elapsed + 1):
            players = int(active.get((cohort, week), 0))
            rows.append((cohort, int(size), week, players, players / size))
    return pd.DataFrame(rows, columns=columns)


# ------------------------------------------------------------------ questions
def label_verdict(difficulty: str, rating: float, rd: float, answers: int) -> str:
    if answers < MIN_ANSWERS or rd > CALIBRATED_RD:
        return "calibrating"
    low, high = BANDS[difficulty]
    if rating < low:
        return "easier than labelled"
    if rating >= high:
        return "harder than labelled"
    return "ok"


def _round_up_to_5(seconds: float) -> int:
    return int(math.ceil(seconds / 5) * 5)


def time_limit_advice(
    correct_ms: list[int], timeouts: int, answers: int, limit_s: int
) -> tuple[str, int | None]:
    """Is the time limit right? Returns (verdict, suggested limit in seconds or None)."""
    if len(correct_ms) < MIN_ANSWERS:
        return "not enough data", None
    p90_s = pd.Series(correct_ms).quantile(0.9) / 1000
    suggested = min(MAX_LIMIT_S, max(MIN_LIMIT_S, _round_up_to_5(p90_s * TIME_FACTOR)))
    timeout_rate = timeouts / answers if answers else 0
    if timeout_rate >= TIGHT_TIMEOUT_RATE or suggested > limit_s:
        return "too tight", max(suggested, min(MAX_LIMIT_S, limit_s + 5))
    if suggested < limit_s * LOOSE_SHARE:
        return "too generous", suggested
    return "ok", None


QUESTION_COLUMNS = [
    "slug",
    "category",
    "format",
    "label",
    "rating",
    "rd",
    "answers",
    "accuracy",
    "timeout_rate",
    "median_correct_s",
    "limit_s",
    "time_verdict",
    "suggested_limit_s",
    "label_verdict",
    "top_wrong_option",
    "top_wrong_share",
    "check_answer_key",
]


def question_stats(answers: pd.DataFrame, questions: pd.DataFrame) -> pd.DataFrame:
    """One row per question: how often it's answered, how hard it really is,
    how long people take, and which wrong option fools them most."""
    rows = []
    grouped = dict(tuple(answers.groupby("question_id"))) if not answers.empty else {}
    for q in questions.itertuples():
        mine = grouped.get(q.id, answers.iloc[0:0])
        n = len(mine)
        is_correct = mine["is_correct"].astype(bool)
        correct = mine[is_correct]
        timeouts = int(mine["timed_out"].sum())
        correct_ms = correct["response_ms"].dropna().astype(int).tolist()

        wrong_picks = mine[~is_correct & mine["chosen_index"].notna()]
        trap, trap_share, trap_beats_answer = None, None, False
        if len(wrong_picks):
            counts = wrong_picks["chosen_index"].astype(int).value_counts()
            top = int(counts.index[0])
            trap = q.options[top]
            trap_share = counts.iloc[0] / len(wrong_picks)
            # A wrong option picked clearly more often than the right one: is the key wrong?
            # (z-test on the two counts, so a close call on a hard question doesn't count)
            picks, right = counts.iloc[0], len(correct)
            trap_beats_answer = bool(
                n >= MIN_ANSWERS and (picks - right) / math.sqrt(picks + right) >= KEY_CHECK_Z
            )

        verdict, suggested = time_limit_advice(correct_ms, timeouts, n, q.time_limit_s)
        rows.append(
            {
                "slug": q.slug,
                "category": q.category,
                "format": q.format,
                "label": q.difficulty,
                "rating": round(q.rating),
                "rd": round(q.rating_deviation),
                "answers": n,
                "accuracy": len(correct) / n if n else None,
                "timeout_rate": timeouts / n if n else None,
                "median_correct_s": pd.Series(correct_ms).median() / 1000 if correct_ms else None,
                "limit_s": q.time_limit_s,
                "time_verdict": verdict,
                "suggested_limit_s": suggested,
                "label_verdict": label_verdict(q.difficulty, q.rating, q.rating_deviation, n),
                "top_wrong_option": trap,
                "top_wrong_share": trap_share,
                "check_answer_key": trap_beats_answer,
            }
        )
    return pd.DataFrame(rows, columns=QUESTION_COLUMNS)