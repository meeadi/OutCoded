from datetime import date, datetime, timedelta, timezone

import pytest

pd = pytest.importorskip("pandas")  # dashboard extras: pip install -r requirements-dashboard.txt
from dashboard import metrics  # noqa: E402

TZ = "Asia/Kolkata"
TODAY = date(2026, 11, 6)


def at(day: date, hour_ist: int = 18) -> datetime:
    return datetime(day.year, day.month, day.day, hour_ist, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def answers(*rows) -> pd.DataFrame:
    """rows: (user, day, mode) or (user, datetime, mode)"""
    records = []
    for user, when, mode in rows:
        shown = when if isinstance(when, datetime) else at(when)
        records.append(
            {
                "user_id": user,
                "question_id": "q1",
                "mode": mode,
                "shown_at": shown,
                "response_ms": 5000,
                "is_correct": True,
                "timed_out": False,
                "chosen_index": 0,
            }
        )
    df = pd.DataFrame(records)
    df["shown_at"] = pd.to_datetime(df["shown_at"], utc=True)
    return df


def test_daily_activity_counts_players_and_fills_quiet_days():
    d = date(2026, 11, 1)
    df = answers(("a", d, "solo"), ("a", d, "solo"), ("b", d, "match"), ("a", d + timedelta(days=2), "solo"))
    daily = metrics.daily_activity(df, TZ)
    assert daily["players"].tolist() == [2, 0, 1]
    assert daily["solo"].tolist() == [2, 0, 1] and daily["match"].tolist() == [1, 0, 0]


def test_days_are_counted_in_local_time():
    # 00:30 IST on the 2nd is still the 1st in UTC, but it belongs to the 2nd here.
    late = datetime(2026, 11, 2, 0, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    daily = metrics.daily_activity(answers(("a", late, "solo")), TZ)
    assert daily["day"].tolist() == [date(2026, 11, 2)]


def test_return_rates_only_count_players_who_had_the_chance():
    start = TODAY - timedelta(days=10)
    df = answers(
        ("came_back", start, "solo"),
        ("came_back", start + timedelta(days=1), "solo"),
        ("left", start, "solo"),
        ("new", TODAY, "solo"),  # started today: can't have come back yet
    )
    rates = metrics.return_rates(df, TZ, TODAY)
    assert rates["next_day"] == 0.5 and rates["next_day_players"] == 2
    assert rates["within_week"] == 0.5


def test_weekly_cohorts_track_each_starting_week():
    monday = date(2026, 10, 19)
    df = answers(
        ("a", monday, "solo"),
        ("b", monday + timedelta(days=2), "solo"),
        ("a", monday + timedelta(days=8), "solo"),  # a comes back in week 1
    )
    cohorts = metrics.weekly_cohorts(df, TZ, TODAY)
    first = cohorts[cohorts["cohort"] == monday].set_index("week")
    assert first.loc[0, "share"] == 1.0
    assert first.loc[1, "share"] == 0.5
    assert first.loc[2, "share"] == 0.0  # quiet weeks still show up, as zero
    assert first["size"].iloc[0] == 2


def test_label_verdict_waits_for_calibration():
    assert metrics.label_verdict("easy", 1700, 200, 50) == "calibrating"
    assert metrics.label_verdict("easy", 1700, 100, 5) == "calibrating"
    assert metrics.label_verdict("easy", 1700, 100, 50) == "harder than labelled"
    assert metrics.label_verdict("hard", 1450, 100, 50) == "easier than labelled"
    assert metrics.label_verdict("medium", 1500, 100, 50) == "ok"


def test_time_limit_too_tight_when_people_run_out():
    correct = [8000] * 20
    verdict, suggested = metrics.time_limit_advice(correct, timeouts=10, answers=40, limit_s=10)
    assert verdict == "too tight" and suggested > 10


def test_time_limit_too_generous_when_everyone_is_fast():
    verdict, suggested = metrics.time_limit_advice([4000] * 20, timeouts=0, answers=20, limit_s=120)
    assert verdict == "too generous" and suggested == 10  # 1.5 x 4 s, rounded up to 5


def test_time_limit_ok_and_not_enough_data():
    assert metrics.time_limit_advice([10_000] * 20, 0, 20, 30) == ("ok", None)
    assert metrics.time_limit_advice([10_000] * 3, 0, 3, 30) == ("not enough data", None)


def question_frame(**overrides):
    q = {
        "id": "q1",
        "slug": "py-test",
        "category": "python",
        "format": "predict_output",
        "difficulty": "medium",
        "options": ["right", "trap", "meh", "nope"],
        "correct_index": 0,
        "time_limit_s": 30,
        "rating": 1500.0,
        "rating_deviation": 100.0,
        "status": "active",
    }
    return pd.DataFrame([q | overrides])


def picks(chosen: list[int | None], correct_index: int = 0) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "user_id": [f"u{i}" for i in range(len(chosen))],
            "question_id": "q1",
            "mode": "solo",
            "shown_at": pd.Timestamp("2026-11-01", tz="UTC"),
            "response_ms": 6000,
            "is_correct": [c == correct_index for c in chosen],
            "timed_out": [c is None for c in chosen],
            "chosen_index": chosen,
        }
    )
    return df


def test_question_stats_find_the_favourite_wrong_answer():
    stats = metrics.question_stats(picks([0] * 12 + [1] * 6 + [2] * 2), question_frame()).iloc[0]
    assert stats["answers"] == 20 and stats["accuracy"] == 0.6
    assert stats["top_wrong_option"] == "trap" and stats["top_wrong_share"] == 0.75
    assert not stats["check_answer_key"]


def test_a_wrong_option_beating_the_right_one_suggests_checking_the_key():
    stats = metrics.question_stats(picks([1] * 18 + [0] * 4), question_frame()).iloc[0]
    assert stats["check_answer_key"]


def test_a_question_nobody_answered_still_appears():
    empty = picks([]).iloc[0:0]
    stats = metrics.question_stats(empty, question_frame()).iloc[0]
    assert stats["answers"] == 0 and stats["label_verdict"] == "calibrating"


def test_no_questions_gives_an_empty_table_with_the_right_columns():
    stats = metrics.question_stats(picks([]).iloc[0:0], question_frame().iloc[0:0])
    assert stats.empty and list(stats.columns) == metrics.QUESTION_COLUMNS

def test_zen_and_review_answers_dont_count_towards_question_stats():
    df = picks([0] * 10 + [1] * 10)
    df["variant"] = ["zen"] * 10 + ["rush"] * 10  # the 10 right answers were all in zen
    stats = metrics.question_stats(df, question_frame()).iloc[0]
    assert stats["answers"] == 10 and stats["accuracy"] == 0