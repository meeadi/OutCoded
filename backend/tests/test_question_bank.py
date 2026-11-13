import csv
from pathlib import Path

from app.question_bank import REQUIRED_COLUMNS, validate_rows

COLUMNS = sorted(REQUIRED_COLUMNS | {"category"}) 


def make_row(**overrides) -> dict:
    row = {
        "slug": "py-example",
        "format": "predict_output",
        "category": "python",
        "language": "python",
        "difficulty": "easy",
        "prompt": "What does this print?",
        "code": "print(1 + 1)\n",
        "option_a": "2",
        "option_b": "11",
        "option_c": "",
        "option_d": "",
        "correct": "a",
        "explanation": "Integer addition.",
        "time_limit_s": "",
        "status": "",
    }
    row.update(overrides)
    return row


def test_valid_row_is_normalised():
    result = validate_rows([make_row()], COLUMNS)
    assert result.ok, result.errors
    q = result.questions[0]
    assert q["options"] == ["2", "11"]
    assert q["correct_index"] == 0
    assert q["time_limit_s"] == 30  # default
    assert q["status"] == "active"  # default
    assert q["code"] == "print(1 + 1)"


def test_code_indentation_is_preserved():
    code = "def f():\n    return 1\n"
    result = validate_rows([make_row(code=code)], COLUMNS)
    assert result.questions[0]["code"] == "def f():\n    return 1"


def test_correct_answer_must_point_at_a_real_option():
    result = validate_rows([make_row(correct="C")], COLUMNS)
    assert not result.ok
    assert "option is empty" in result.errors[0]


def test_bad_correct_values_are_rejected():
    for bad in ["", "E", "AB", "1"]:
        assert not validate_rows([make_row(correct=bad)], COLUMNS).ok, bad


def test_gaps_and_duplicate_options_are_rejected():
    gap = make_row(option_b="", option_c="3")
    dupe = make_row(option_b="2")
    assert not validate_rows([gap], COLUMNS).ok
    assert not validate_rows([dupe], COLUMNS).ok


def test_duplicate_slugs_are_rejected():
    result = validate_rows([make_row(), make_row()], COLUMNS)
    assert any("duplicate slug" in e for e in result.errors)


def test_missing_columns_are_reported():
    result = validate_rows([], ["slug", "prompt"])
    assert result.errors and "Missing columns" in result.errors[0]


def test_seed_file_is_valid():
    path = Path(__file__).resolve().parents[1] / "data" / "questions.csv"
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        result = validate_rows(rows, list(reader.fieldnames))
    assert result.ok, result.errors
    assert len(result.questions) >= 20

def test_topic_column_can_be_called_topic_or_category():
    row = make_row(category="", topic="sql")
    del row["category"]
    columns = [c for c in COLUMNS if c != "category"] + ["topic"]
    result = validate_rows([row], columns)
    assert result.ok and result.questions[0]["category"] == "sql"


def test_unknown_topics_are_rejected():
    result = validate_rows([make_row(category="postgres")], COLUMNS)
    assert any("topic must be one of" in e for e in result.errors)


def test_pool_defaults_to_both_and_is_checked():
    assert validate_rows([make_row()], COLUMNS).questions[0]["pool"] == "both"
    assert validate_rows([make_row(pool="practice")], COLUMNS + ["pool"]).questions[0]["pool"] == "practice"
    bad = validate_rows([make_row(pool="casual")], COLUMNS + ["pool"])
    assert any("pool must be one of" in e for e in bad.errors)


def test_errors_name_the_file_and_row():
    row = make_row(category="nope", _file="sql.csv", _row=7)
    assert validate_rows([row], COLUMNS).errors[0].startswith("sql.csv, row 7")