"""Scan recent answers for suspicious patterns and record flags for review.

Run it whenever you like (or on a schedule). It's safe to re-run: each player
has at most one flag per kind, updated with the latest evidence. Flags you've
dismissed or confirmed keep that status.

Usage (from the backend folder):
    python scripts/detect_cheating.py
    python scripts/detect_cheating.py --days 7
"""

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cheat_detection import Answer, detect  # noqa: E402
from app.config import get_settings  # noqa: E402

ANSWERS = """
    select a.user_id, q.slug, a.is_correct, a.timed_out, a.response_ms, a.away_ms,
           q.rating as question_rating,
           length(q.prompt) + coalesce(length(q.code), 0)
               + (select coalesce(sum(length(o)), 0)
                  from jsonb_array_elements_text(q.options) as o)         as text_chars,
           -- first time this player ever saw this question?
           a.shown_at = min(a.shown_at) over (partition by a.user_id, a.question_id) as first_time
    from public.attempts a
    join public.questions q on q.id = a.question_id
    where a.answered_at is not null
      and a.response_ms is not null
"""

UPSERT = """
    insert into public.cheat_flags (user_id, kind, severity, evidence)
    values ($1, $2, $3, $4::jsonb)
    on conflict (user_id, kind) do update set
        severity  = excluded.severity,
        evidence  = excluded.evidence,
        last_seen = now()
    returning (xmax = 0) as is_new, status
"""


async def main(days: int) -> None:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        rows = await conn.fetch(
            f"select * from ({ANSWERS}) x where x.user_id in "
            "(select user_id from public.attempts where answered_at > now() - make_interval(days => $1))",
            days,
        )
        players = {
            r["id"]: r
            for r in await conn.fetch("select id, username, rating, rating_deviation from public.profiles")
        }

        answers_by_player: dict = defaultdict(list)
        for r in rows:
            answers_by_player[r["user_id"]].append(
                Answer(
                    correct=r["is_correct"],
                    timed_out=r["timed_out"],
                    response_ms=r["response_ms"],
                    text_chars=r["text_chars"],
                    question_rating=r["question_rating"],
                    first_time=r["first_time"],
                    away_ms=r["away_ms"],
                    slug=r["slug"],
                )
            )

        new = updated = 0
        for user_id, answers in answers_by_player.items():
            player = players[user_id]
            for flag in detect(answers, player["rating"], player["rating_deviation"]):
                result = await conn.fetchrow(
                    UPSERT, user_id, flag.kind, flag.severity, json.dumps(flag.evidence)
                )
                new += result["is_new"]
                updated += not result["is_new"]
                marker = "NEW " if result["is_new"] else f"{result['status']:<4}"
                name = player["username"] or str(user_id)[:8]
                print(f"  {marker} {name:<20} {flag.kind:<17} severity {flag.severity:.2f}  {flag.evidence}")

        open_flags = await conn.fetchval("select count(*) from public.cheat_flags where status = 'open'")
    finally:
        await conn.close()

    print(
        f"\nChecked {len(answers_by_player)} players active in the last {days} days: "
        f"{new} new flags, {updated} updated, {open_flags} open in total."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=30, help="check players active in this many days")
    asyncio.run(main(parser.parse_args().days))