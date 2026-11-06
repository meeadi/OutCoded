"""Read from (and, for cheat-flag reviews, write to) the database.

This connects with DATABASE_URL from backend/.env, which can see everything,
so only ever run the dashboard on your own machine.
"""

import pandas as pd
import psycopg

from app.config import get_settings

ANSWERS = """
    select user_id, question_id, mode, shown_at, response_ms,
           coalesce(is_correct, false) as is_correct, timed_out, chosen_index, away_ms
    from public.attempts
    where answered_at is not null
"""

QUESTIONS = """
    select id, slug, category, format, difficulty, options, correct_index,
           time_limit_s, rating, rating_deviation, status
    from public.questions
    order by slug
"""

PLAYERS = """
    select id, username, rating, rating_deviation, created_at
    from public.profiles
"""

MATCHES = """
    select id, status, rated, forfeit, created_at, finished_at
    from public.matches
"""

FLAGS = """
    select f.id, f.user_id, p.username, f.kind, f.severity, f.status,
           f.evidence, f.first_seen, f.last_seen,
           round(p.rating) as rating, round(p.rating_deviation) as rd
    from public.cheat_flags f
    join public.profiles p on p.id = f.user_id
    order by f.severity desc, f.last_seen desc
"""

PLAYER_ANSWERS = """
    select a.shown_at, q.slug, a.mode, a.is_correct, a.timed_out,
           a.response_ms, a.away_ms, round(q.rating) as question_rating
    from public.attempts a
    join public.questions q on q.id = a.question_id
    where a.user_id = %s and a.answered_at is not null
    order by a.shown_at desc
    limit 100
"""


def _connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url, autocommit=True)


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=columns)


def answers() -> pd.DataFrame:
    df = query(ANSWERS)
    df["shown_at"] = pd.to_datetime(df["shown_at"], utc=True)
    df["is_correct"] = df["is_correct"].astype(bool)
    df["timed_out"] = df["timed_out"].astype(bool)
    return df


def questions() -> pd.DataFrame:
    return query(QUESTIONS)


def players() -> pd.DataFrame:
    return query(PLAYERS)


def matches() -> pd.DataFrame:
    df = query(MATCHES)
    df["finished_at"] = pd.to_datetime(df["finished_at"], utc=True)
    return df


def flags() -> pd.DataFrame:
    return query(FLAGS)


def player_answers(user_id) -> pd.DataFrame:
    return query(PLAYER_ANSWERS, (user_id,))


def set_flag_status(flag_id: int, status: str) -> None:
    with _connect() as conn:
        conn.execute("update public.cheat_flags set status = %s where id = %s", (status, flag_id))