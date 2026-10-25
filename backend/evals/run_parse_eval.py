"""Score parse_expense_text against the REAL OpenAI API.

Run from backend/ with the venv active:
    python evals/run_parse_eval.py

This makes real API calls (well under 1p per run on gpt-4o-mini).
It is deliberately not a pytest test: tests must never call the real API.
"""

import datetime
import json
import sys
from decimal import Decimal
from pathlib import Path

# Let "import app..." work when this file is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.llm.client import LLMError, get_llm_client
from app.llm.parse import (
    ExpenseParseError,
    UserInputError,
    parse_expense_text,
)

# Fixed so the expected dates in the cases never go stale.
TODAY = datetime.date(2026, 10, 25)
CASES_FILE = Path(__file__).parent / "parse_cases.jsonl"
FIELDS = ["amount", "currency", "date", "category"]
# Phase 2 is done when these are met.
TARGETS = {"amount": 1.00, "category": 0.90}


def load_cases() -> list[dict]:
    with CASES_FILE.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def actual_value(expense, field: str) -> str:
    value = getattr(expense, field)
    return str(value)


def expected_matches(field: str, expected: str, actual: str) -> bool:
    if field == "amount":
        return Decimal(expected) == Decimal(actual)
    return expected == actual


def main() -> int:
    if get_settings().OPENAI_API_KEY.get_secret_value() == "sk-replace-me":
        print(
            "OPENAI_API_KEY in backend/.env is still the placeholder - add a real key."
        )
        return 1

    llm = get_llm_client()
    cases = load_cases()
    correct = {field: 0 for field in FIELDS}
    total = {field: 0 for field in FIELDS}
    errors_right = errors_total = 0

    for number, case in enumerate(cases, start=1):
        text = case["text"]
        problems: list[str] = []

        try:
            expenses = parse_expense_text(text, llm, TODAY)
            outcome = None
        except (UserInputError, ExpenseParseError) as e:
            expenses = []
            outcome = type(e).__name__
        except LLMError as e:
            print(f"\nStopped: the API call itself failed ({e}).")
            return 1

        if "expected_error" in case:
            errors_total += 1
            if outcome == case["expected_error"]:
                errors_right += 1
            else:
                got = outcome or f"{len(expenses)} expense(s)"
                problems.append(f"expected {case['expected_error']}, got {got}")
        else:
            if outcome:
                problems.append(f"expected expenses, got {outcome}")
            elif len(expenses) != len(case["expected"]):
                problems.append(
                    f"expected {len(case['expected'])} expense(s), got {len(expenses)}"
                )
            # Score expense by expense, in order. Missing ones count as wrong.
            for index, wanted in enumerate(case["expected"]):
                got = expenses[index] if index < len(expenses) else None
                for field in FIELDS:
                    total[field] += 1
                    if got is None:
                        continue
                    value = actual_value(got, field)
                    if expected_matches(field, wanted[field], value):
                        correct[field] += 1
                    else:
                        problems.append(
                            f"{field}: expected {wanted[field]}, got {value}"
                        )

        mark = "✓" if not problems else "✗"
        print(f"{mark} {number:>2}  {text}")
        for problem in problems:
            print(f"        {problem}   [{case.get('checks', '')}]")

    print("\nAccuracy")
    passed = True
    for field in FIELDS:
        score = correct[field] / total[field]
        target = TARGETS.get(field)
        note = ""
        if target is not None:
            ok = score >= target
            passed = passed and ok
            note = f"  (target {target:.0%}: {'met' if ok else 'NOT met'})"
        print(f"  {field:<9} {correct[field]:>2}/{total[field]:<2}  {score:6.1%}{note}")
    if errors_total:
        print(
            f"  {'errors':<9} {errors_right:>2}/{errors_total:<2}  {errors_right / errors_total:6.1%}"
        )

    print("\nPASS" if passed else "\nFAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
