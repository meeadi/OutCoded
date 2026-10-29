"""Load questions from a CSV into the database.

Usage (from the backend folder):
    python scripts/import_questions.py                      # data/questions.csv
    python scripts/import_questions.py my_questions.csv
    python scripts/import_questions.py --dry-run            # validate only, no DB

Rows are matched by slug: new slugs are inserted, existing ones updated.
Updating a question never resets its difficulty rating. To take a question
out of rotation, set its status to "retired" rather than deleting the row,
so old attempts and events still point at it.
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

import asyncpg

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
from app.config import get_settings  # noqa: E402
from app.db import _init_connection  # noqa: E402
from app.question_bank import validate_rows  # noqa: E402

UPSERT = """
    insert into public.questions (
        slug, format, category, language, difficulty, prompt, code, options,
        correct_index, explanation, time_limit_s, status, rating
    )
    values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
    on conflict (slug) do update set
        format        = excluded.format,
        category      = excluded.category,
        language      = excluded.language,
        difficulty    = excluded.difficulty,
        prompt        = excluded.prompt,
        code          = excluded.code,
        options       = excluded.options,
        correct_index = excluded.correct_index,
        explanation   = excluded.explanation,
        time_limit_s  = excluded.time_limit_s,
        status        = excluded.status,
        updated_at    = now()
    returning (xmax = 0) as inserted
"""


def read_csv(path: Path) -> tuple[list[dict], list[str]]:
    # utf-8-sig also handles the invisible BOM that Excel adds when saving CSVs.
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


async def upsert(questions: list[dict]) -> tuple[int, int]:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        await _init_connection(conn)
        inserted = updated = 0
        async with conn.transaction():  # all or nothing
            for q in questions:
                was_inserted = await conn.fetchval(
                    UPSERT,
                    q["slug"], q["format"], q["category"], q["language"], q["difficulty"],
                    q["prompt"], q["code"], q["options"], q["correct_index"],
                    q["explanation"], q["time_limit_s"], q["status"], q["rating"],
                )
                inserted += was_inserted
                updated += not was_inserted
        return inserted, updated
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv_path", nargs="?", default=str(BACKEND_DIR / "data" / "questions.csv"))
    parser.add_argument("--dry-run", action="store_true", help="validate without touching the DB")
    args = parser.parse_args()

    path = Path(args.csv_path)
    if not path.exists():
        sys.exit(f"File not found: {path}")

    rows, columns = read_csv(path)
    result = validate_rows(rows, columns)
    if not result.ok:
        print(f"Found {len(result.errors)} problem(s), nothing was imported:\n")
        for error in result.errors:
            print(f"  - {error}")
        sys.exit(1)

    print(f"{len(result.questions)} questions look valid.")
    if args.dry_run:
        return

    inserted, updated = asyncio.run(upsert(result.questions))
    print(f"Imported: {inserted} new, {updated} updated.")


if __name__ == "__main__":
    main()
