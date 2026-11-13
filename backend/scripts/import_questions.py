"""Load questions from CSV files into the database.

Usage (from the backend folder):
    python scripts/import_questions.py                  # data/questions.csv + every CSV in data/questions/
    python scripts/import_questions.py data/questions/sql.csv
    python scripts/import_questions.py --dry-run        # validate only, no DB

One CSV per topic (data/questions/sql.csv, python.csv, ...) keeps things tidy.
Every file is checked first, and if any row anywhere has a problem, nothing is
imported. Slugs must be unique across all files.

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
        correct_index, explanation, time_limit_s, status, rating, pool
    )
    values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
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
        pool          = excluded.pool,
        updated_at    = now()
    returning (xmax = 0) as inserted
"""


def read_csv(path: Path) -> tuple[list[dict], list[str]]:
    # utf-8-sig also handles the invisible BOM that Excel adds when saving CSVs.
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    for number, row in enumerate(rows, start=1):
        row["_file"], row["_row"] = path.name, number  # for error messages
    return rows, list(reader.fieldnames or [])


def default_files() -> list[Path]:
    data = BACKEND_DIR / "data"
    files = [data / "questions.csv"] if (data / "questions.csv").exists() else []
    if (data / "questions").is_dir():
        files += sorted((data / "questions").glob("*.csv"))
    return files


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
                    q["explanation"], q["time_limit_s"], q["status"], q["rating"], q["pool"],
                )
                inserted += was_inserted
                updated += not was_inserted
        return inserted, updated
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="CSV files (default: all of them)")
    parser.add_argument("--dry-run", action="store_true", help="validate without touching the DB")
    args = parser.parse_args()

    files = [Path(p) for p in args.paths] or default_files()
    if not files:
        sys.exit("No CSV files found.")
    for path in files:
        if not path.exists():
            sys.exit(f"File not found: {path}")

    # Check every file before importing anything: all or nothing.
    questions: list[dict] = []
    errors: list[str] = []
    seen: dict[str, str] = {}
    for path in files:
        rows, columns = read_csv(path)
        result = validate_rows(rows, columns)
        errors += [f"{path.name}: {e}" if path.name not in e else e for e in result.errors]
        for q in result.questions:
            if q["slug"] in seen:
                errors.append(f"{path.name}: slug {q['slug']} is already used in {seen[q['slug']]}")
            seen.setdefault(q["slug"], path.name)
        questions += result.questions

    if errors:
        print(f"Found {len(errors)} problem(s), nothing was imported:\n")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print(f"{len(questions)} questions in {len(files)} file(s) look valid.")
    if args.dry_run:
        return

    inserted, updated = asyncio.run(upsert(questions))
    print(f"Imported: {inserted} new, {updated} updated.")


if __name__ == "__main__":
    main()