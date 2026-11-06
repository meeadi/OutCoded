"""OutCoded analytics dashboard.

Run from the backend folder:
    streamlit run dashboard/app.py
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard import data, metrics  # noqa: E402

TIMEZONE = "Asia/Kolkata"
BLUE, ORANGE = "#2a78d6", "#eb6834"  # solo, match: the same colors everywhere
PERIODS = {"7 days": 7, "30 days": 30, "90 days": 90, "All time": None}

st.set_page_config(page_title="OutCoded analytics", page_icon="📊", layout="wide")


@st.cache_data(ttl=60, show_spinner="Loading data…")
def load():
    return data.answers(), data.questions(), data.players(), data.matches(), data.flags()


def percent(value: float | None) -> str:
    return "–" if value is None or pd.isna(value) else f"{value:.0%}"


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("OutCoded")
    period = st.radio("Period", list(PERIODS), index=1)
    if st.button("Refresh data", icon="🔄"):
        st.cache_data.clear()
    st.caption(f"Days are counted in {TIMEZONE}. Data is cached for a minute.")

all_answers, questions, players, matches, flags = load()
now = datetime.now(ZoneInfo(TIMEZONE))
today = now.date()
days = PERIODS[period]
since = pd.Timestamp(now - timedelta(days=days)) if days else None

answers = all_answers if since is None else all_answers[all_answers["shown_at"] >= since]
finished = matches[matches["status"] == "finished"]
if since is not None:
    finished = finished[finished["finished_at"] >= since]

overview, retention, question_tab, cheat_tab = st.tabs(["Overview", "Retention", "Questions", "Cheat flags"])

# ------------------------------------------------------------------ overview
with overview:
    daily = metrics.daily_activity(answers, TIMEZONE)
    new_players = (
        len(players)
        if since is None
        else int((pd.to_datetime(players["created_at"], utc=True) >= since).sum())
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Players", len(players), delta=f"+{new_players} new", delta_color="off", border=True)
    c2.metric(
        "Active players",
        answers["user_id"].nunique(),
        help="Answered at least one question in this period",
        chart_data=daily["players"].tolist() or None,
        border=True,
    )
    c3.metric("Answers", f"{len(answers):,}", border=True)
    c4.metric("Accuracy", percent(answers["is_correct"].mean() if len(answers) else None), border=True)
    c5.metric(
        "Matches",
        len(finished),
        help=f"Finished in this period: {int(finished['rated'].sum())} ranked, {int((~finished['rated']).sum())} casual",
        border=True,
    )

    if daily.empty:
        st.info("No answers in this period yet.")
    else:
        left, right = st.columns(2)
        with left:
            st.subheader("Active players per day")
            chart = (
                alt.Chart(daily)
                .mark_line(color=BLUE, strokeWidth=2, point=alt.OverlayMarkDef(size=40, color=BLUE))
                .encode(
                    x=alt.X("day:T", title=None),
                    y=alt.Y("players:Q", title="Players"),
                    tooltip=[alt.Tooltip("day:T", format="%a %d %b"), "players:Q"],
                )
            )
            st.altair_chart(chart, width="stretch")
        with right:
            st.subheader("Answers per day")
            by_mode = daily.melt(
                id_vars="day", value_vars=["solo", "match"], var_name="mode", value_name="answers"
            )
            chart = (
                alt.Chart(by_mode)
                .mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=40))
                .encode(
                    x=alt.X("day:T", title=None),
                    y=alt.Y("answers:Q", title="Answers"),
                    color=alt.Color(
                        "mode:N",
                        scale=alt.Scale(domain=["solo", "match"], range=[BLUE, ORANGE]),
                        legend=alt.Legend(orient="top", title=None),
                    ),
                    tooltip=[alt.Tooltip("day:T", format="%a %d %b"), "mode:N", "answers:Q"],
                )
            )
            st.altair_chart(chart, width="stretch")

        st.subheader("When people play")
        hours = metrics.answers_by_hour(answers, TIMEZONE)
        chart = (
            alt.Chart(hours)
            .mark_bar(color=BLUE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("hour:O", title=f"Hour of day ({TIMEZONE})"),
                y=alt.Y("answers:Q", title="Answers"),
                tooltip=["hour:O", "answers:Q"],
            )
            .properties(height=220)
        )
        st.altair_chart(chart, width="stretch")
        st.caption("Handy for picking a tournament time.")

# ------------------------------------------------------------------ retention
with retention:
    st.caption("Retention always uses all-time data: it needs history to mean anything.")
    rates = metrics.return_rates(all_answers, TIMEZONE, today)
    c1, c2 = st.columns(2)
    c1.metric(
        "Came back the next day",
        percent(rates["next_day"]),
        help=f"Out of {rates['next_day_players']} players who started at least a day ago",
        border=True,
    )
    c2.metric(
        "Came back within a week",
        percent(rates["within_week"]),
        help=f"Out of {rates['within_week_players']} players who started at least a week ago",
        border=True,
    )

    cohorts = metrics.weekly_cohorts(all_answers, TIMEZONE, today)
    if cohorts.empty:
        st.info("No players yet.")
    else:
        st.subheader("Weekly cohorts")
        st.caption(
            "Each row is the players who started that week. Each cell is the share of them "
            "who played in a later week. Week 0 is always 100%."
        )
        cohorts["group"] = [
            f"{c:%d %b} ({s})" for c, s in zip(cohorts["cohort"], cohorts["size"], strict=True)
        ]
        order = cohorts.sort_values("cohort")["group"].unique().tolist()
        base = alt.Chart(cohorts).encode(
            x=alt.X(
                "week:O",
                title="Weeks since starting",
                axis=alt.Axis(labelAngle=0),
                scale=alt.Scale(paddingInner=0.06),  # small gaps between cells, any theme
            ),
            y=alt.Y(
                "group:N", title="Started week of (players)", sort=order, scale=alt.Scale(paddingInner=0.1)
            ),
        )
        cells = base.mark_rect(cornerRadius=4).encode(
            color=alt.Color("share:Q", scale=alt.Scale(scheme="blues", domain=[0, 1]), legend=None),
            tooltip=["group:N", "week:O", "players:Q", alt.Tooltip("share:Q", format=".0%")],
        )
        labels = base.mark_text(fontSize=12).encode(
            text=alt.Text("share:Q", format=".0%"),
            color=alt.condition("datum.share > 0.5", alt.value("white"), alt.value("#333")),
        )
        st.altair_chart((cells + labels).properties(height=max(120, 36 * len(order))), width="stretch")

# ------------------------------------------------------------------ questions
with question_tab:
    stats = metrics.question_stats(answers, questions)

    f1, f2, f3 = st.columns([2, 2, 1])
    categories = f1.multiselect("Category", sorted(stats["category"].unique()))
    formats = f2.multiselect("Format", sorted(stats["format"].unique()))
    attention_only = f3.toggle(
        "Needs attention", help="Mislabelled, wrong time limit, or a suspicious answer key"
    )
    if categories:
        stats = stats[stats["category"].isin(categories)]
    if formats:
        stats = stats[stats["format"].isin(formats)]

    mislabelled = stats["label_verdict"].isin(["easier than labelled", "harder than labelled"])
    timing = stats["time_verdict"].isin(["too tight", "too generous"])
    key = stats["check_answer_key"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Questions", len(stats), border=True)
    c2.metric(
        "Mislabelled", int(mislabelled.sum()), help="Calibrated rating outside its label's band", border=True
    )
    c3.metric(
        "Time limit off",
        int(timing.sum()),
        help="Too many timeouts, or far more time than needed",
        border=True,
    )
    c4.metric(
        "Check answer key",
        int(key.sum()),
        help="A wrong option is picked clearly more often than the right one: "
        "either the key is wrong or it's a great trick question. Worth a look.",
        border=True,
    )

    if attention_only:
        stats = stats[mislabelled | timing | key]

    shares = ["accuracy", "timeout_rate", "top_wrong_share"]
    st.dataframe(
        stats.assign(**{c: stats[c] * 100 for c in shares}),  # 0.42 -> 42 for display
        hide_index=True,
        column_config={
            "slug": st.column_config.TextColumn("Question", pinned=True),
            "category": "Category",
            "format": "Format",
            "label": "Label",
            "rating": st.column_config.NumberColumn("Rating", help="Calibrated difficulty"),
            "rd": st.column_config.NumberColumn("±RD", help="Uncertainty: 150 or less counts as calibrated"),
            "answers": "Answers",
            "accuracy": st.column_config.ProgressColumn(
                "Accuracy", format="%.0f%%", min_value=0, max_value=100
            ),
            "timeout_rate": st.column_config.NumberColumn("Timeouts", format="%.0f%%"),
            "median_correct_s": st.column_config.NumberColumn("Median right (s)", format="%.1f"),
            "limit_s": st.column_config.NumberColumn("Limit (s)"),
            "time_verdict": "Time limit",
            "suggested_limit_s": st.column_config.NumberColumn(
                "Try (s)", help="1.5x the time 90% of right answers took"
            ),
            "label_verdict": "Label check",
            "top_wrong_option": "Favourite wrong answer",
            "top_wrong_share": st.column_config.NumberColumn("of wrong picks", format="%.0f%%"),
            "check_answer_key": st.column_config.CheckboxColumn("Check key?"),
        },
    )

    timed = stats.dropna(subset=["median_correct_s"])
    timed = timed[timed["answers"] >= metrics.MIN_ANSWERS]
    if len(timed):
        st.subheader("Difficulty and time are different things")
        st.caption(
            "A hard question isn't always a slow one: some are quick once you spot the trick. "
            "That's why time limits are tuned separately from ratings."
        )
        chart = (
            alt.Chart(timed)
            .mark_circle(size=90, color=BLUE, opacity=0.8)
            .encode(
                x=alt.X("rating:Q", title="Calibrated rating", scale=alt.Scale(zero=False)),
                y=alt.Y("median_correct_s:Q", title="Median time to a right answer (s)"),
                tooltip=["slug:N", "rating:Q", alt.Tooltip("median_correct_s:Q", format=".1f"), "answers:Q"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, width="stretch")

# ------------------------------------------------------------------ cheat flags
with cheat_tab:
    st.caption(
        "Flags are leads, not verdicts. Look at the answers before deciding. "
        "Update them by running `python scripts/detect_cheating.py`."
    )
    status = st.segmented_control("Status", ["open", "confirmed", "dismissed"], default="open")
    shown = flags if status is None else flags[flags["status"] == status]

    if shown.empty:
        st.success(f"No {status or ''} flags.")
    else:
        st.dataframe(
            shown.drop(columns=["user_id", "evidence"]),
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("#"),
                "username": "Player",
                "status": "Status",
                "rating": "Rating",
                "kind": "Flag",
                "severity": st.column_config.ProgressColumn(
                    "Severity", min_value=0, max_value=1, format="%.2f"
                ),
                "first_seen": st.column_config.DatetimeColumn("First seen", format="D MMM, HH:mm"),
                "last_seen": st.column_config.DatetimeColumn("Last seen", format="D MMM, HH:mm"),
                "rd": "±RD",
            },
        )

        st.subheader("Review a flag")
        labels = {
            row.id: f"#{row.id} · {row.username or str(row.user_id)[:8]} · {row.kind} ({row.severity:.2f})"
            for row in shown.itertuples()
        }
        picked = st.selectbox("Flag", list(labels), format_func=labels.get)
        flag = shown[shown["id"] == picked].iloc[0]

        left, right = st.columns([1, 2])
        with left:
            st.markdown("**Evidence**")
            evidence = flag["evidence"]
            st.json(json.loads(evidence) if isinstance(evidence, str) else evidence)
            b1, b2, b3 = st.columns(3)
            new_status = None
            if b1.button("Confirm", type="primary", disabled=flag["status"] == "confirmed"):
                new_status = "confirmed"
            if b2.button("Dismiss", disabled=flag["status"] == "dismissed"):
                new_status = "dismissed"
            if b3.button("Reopen", disabled=flag["status"] == "open"):
                new_status = "open"
            if new_status:
                data.set_flag_status(int(flag["id"]), new_status)
                st.cache_data.clear()
                st.rerun()
        with right:
            st.markdown(f"**{flag['username'] or 'This player'}'s last 100 answers**")
            st.dataframe(
                data.player_answers(flag["user_id"]),
                hide_index=True,
                height=360,
                column_config={
                    "shown_at": st.column_config.DatetimeColumn("When", format="D MMM, HH:mm"),
                    "slug": "Question",
                    "is_correct": st.column_config.CheckboxColumn("Right"),
                    "timed_out": st.column_config.CheckboxColumn("Timed out"),
                    "response_ms": st.column_config.NumberColumn("Time (ms)"),
                    "away_ms": st.column_config.NumberColumn("Away (ms)"),
                    "question_rating": "Q rating",
                },
            )