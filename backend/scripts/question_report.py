"""How hard is each question really? Compares the label you gave it with
what players' answers say, and flags the ones that look mislabelled.

Usage (from the backend folder):
    python scripts/question_report.py
    python scripts/question_report.py --min-answers 20
"""

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402

# Rating bands each label is expected to land in once calibrated.
BANDS = {"easy": (0, 1400), "medium": (1400, 1600), "hard": (1600, 10_000)}
CALIBRATED_RD = 150  # below this, the rating is trustworthy enough to judge

QUERY = """
    select q.slug, q.difficulty, q.rating, q.rating_deviation, q.status,
           count(a.answered_at)                                       as answers,
           avg(case when a.is_correct then 1.0 else 0.0 end)
               filter (where a.answered_at is not null)               as accuracy,
           avg(a.response_ms) filter (where a.is_correct)             as avg_correct_ms
    from public.questions q
    left join public.attempts a on a.question_id = q.id
    group by q.id
    order by q.rating desc
"""


def verdict(difficulty: str, rating: float, rd: float, answers: int, min_answers: int) -> str:
    if answers < min_answers or rd > CALIBRATED_RD:
        return "calibrating"
    low, high = BANDS[difficulty]
    if rating < low:
        return "easier than labelled"
    if rating >= high:
        return "harder than labelled"
    return "ok"


async def main(min_answers: int) -> None:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        rows = await conn.fetch(QUERY)
    finally:
        await conn.close()

    header = (
        f"{'question':<28} {'label':<7} {'rating':>7} {'±rd':>5} "
        f"{'answers':>8} {'right':>6} {'avg ok':>7}  verdict"
    )
    print(header)
    print("-" * len(header))
    flagged = 0
    for r in rows:
        v = verdict(r["difficulty"], r["rating"], r["rating_deviation"], r["answers"], min_answers)
        flagged += v not in ("ok", "calibrating")
        accuracy = "-" if r["accuracy"] is None else f"{float(r['accuracy']) * 100:.0f}%"
        avg_ms = "-" if r["avg_correct_ms"] is None else f"{float(r['avg_correct_ms']) / 1000:.1f}s"
        marker = "  <--" if v not in ("ok", "calibrating") else ""
        slug = r["slug"] + (" (retired)" if r["status"] == "retired" else "")
        print(
            f"{slug:<28} {r['difficulty']:<7} {r['rating']:>7.0f} {r['rating_deviation']:>5.0f} "
            f"{r['answers']:>8} {accuracy:>6} {avg_ms:>7}  {v}{marker}"
        )
    print(f"\n{len(rows)} questions, {flagged} look mislabelled.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-answers", type=int, default=10, help="answers needed before judging")
    asyncio.run(main(parser.parse_args().min_answers))