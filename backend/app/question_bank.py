"""Validate question rows from a CSV before they reach the database.

A broken answer key in a ranked match kills trust in the whole platform,
so the importer refuses the entire file if any row has a problem.
"""

import re
from dataclasses import dataclass, field

FORMATS = {"predict_output", "spot_bug", "quickfire"}
DIFFICULTIES = {"easy", "medium", "hard"}
STATUSES = {"draft", "active", "retired"}
OPTION_COLUMNS = ["option_a", "option_b", "option_c", "option_d"]
REQUIRED_COLUMNS = {
    "slug", "format", "category", "language", "difficulty", "prompt", "code",
    *OPTION_COLUMNS, "correct", "explanation", "time_limit_s", "status",
}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Starting difficulty rating for a new question. Real answers adjust it later.
INITIAL_RATING = {"easy": 1300.0, "medium": 1500.0, "hard": 1700.0}


@dataclass
class ValidationResult:
    questions: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _clean(value: str | None) -> str:
    return (value or "").strip()


def validate_rows(rows: list[dict], columns: list[str]) -> ValidationResult:
    result = ValidationResult()

    missing = REQUIRED_COLUMNS - set(columns)
    if missing:
        result.errors.append(f"Missing columns: {', '.join(sorted(missing))}")
        return result

    seen_slugs: set[str] = set()
    for number, raw in enumerate(rows, start=1):
        slug = _clean(raw.get("slug"))
        where = f"Row {number} ({slug or 'no slug'})"
        errors: list[str] = []

        if not SLUG_PATTERN.match(slug):
            errors.append("slug must be lowercase letters, digits and dashes, e.g. py-late-binding")
        elif slug in seen_slugs:
            errors.append("duplicate slug")
        seen_slugs.add(slug)

        fmt = _clean(raw.get("format"))
        if fmt not in FORMATS:
            errors.append(f"format must be one of {sorted(FORMATS)}")

        difficulty = _clean(raw.get("difficulty")).lower()
        if difficulty not in DIFFICULTIES:
            errors.append(f"difficulty must be one of {sorted(DIFFICULTIES)}")

        status = _clean(raw.get("status")).lower() or "active"
        if status not in STATUSES:
            errors.append(f"status must be one of {sorted(STATUSES)}")

        for name in ("category", "prompt", "explanation"):
            if not _clean(raw.get(name)):
                errors.append(f"{name} is empty")

        # Options: A and B required, no gaps, no duplicates.
        options = [_clean(raw.get(col)) for col in OPTION_COLUMNS]
        while options and not options[-1]:
            options.pop()
        if len(options) < 2:
            errors.append("needs at least option_a and option_b")
        elif "" in options:
            errors.append("options can't have gaps (fill them in order A, B, C, D)")
        elif len(set(options)) != len(options):
            errors.append("two options are identical")

        correct = _clean(raw.get("correct")).upper()
        if correct not in {"A", "B", "C", "D"}:
            errors.append("correct must be A, B, C or D")
        elif "ABCD".index(correct) >= len(options):
            errors.append(f"correct is {correct} but that option is empty")

        time_limit_raw = _clean(raw.get("time_limit_s")) or "30"
        try:
            time_limit = int(time_limit_raw)
            if not 5 <= time_limit <= 300:
                raise ValueError
        except ValueError:
            errors.append("time_limit_s must be a whole number from 5 to 300")
            time_limit = 30

        if errors:
            result.errors.extend(f"{where}: {e}" for e in errors)
            continue

        # Keep code exactly as written (indentation matters), minus outer blank lines.
        code = (raw.get("code") or "").strip("\n").rstrip() or None

        result.questions.append(
            {
                "slug": slug,
                "format": fmt,
                "category": _clean(raw.get("category")).lower(),
                "language": _clean(raw.get("language")).lower() or None,
                "difficulty": difficulty,
                "prompt": _clean(raw.get("prompt")),
                "code": code,
                "options": options,
                "correct_index": "ABCD".index(correct),
                "explanation": _clean(raw.get("explanation")),
                "time_limit_s": time_limit,
                "status": status,
                "rating": INITIAL_RATING[difficulty],
            }
        )

    return result
