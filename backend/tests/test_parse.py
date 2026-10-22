import datetime
import json
from decimal import Decimal

import pytest

from app.llm.parse import ExpenseParseError, MissingAmountError, parse_expense_text

# These tests never call the real OpenAI API: FakeLLM returns scripted replies.

TODAY = datetime.date(2026, 10, 22)

GOOD = {
    "amount": "4.50",
    "currency": "GBP",
    "date": "2026-10-21",
    "merchant": "Bubble tea",
    "category": "Food",
    "note": None,
}


def reply(**changes) -> str:
    return json.dumps(GOOD | changes)


class FakeLLM:
    """Pretends to be LLMClient. Each call returns the next scripted reply."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system_prompt, user_message):
        self.calls.append({"system": system_prompt, "user": user_message})
        return self.replies.pop(0)


def test_parses_a_good_reply_first_time():
    llm = FakeLLM([reply()])

    parsed = parse_expense_text("4.50 bubble tea yesterday", llm, TODAY)

    assert parsed.amount == Decimal("4.50")
    assert parsed.currency == "GBP"
    assert parsed.date == datetime.date(2026, 10, 21)
    assert parsed.category == "Food"
    assert len(llm.calls) == 1
    assert llm.calls[0]["user"] == "4.50 bubble tea yesterday"
    assert "Today is 2026-10-22" in llm.calls[0]["system"]


def test_accepts_amount_sent_as_a_number():
    llm = FakeLLM([reply(amount=4.5)])

    parsed = parse_expense_text("4.50 bubble tea", llm, TODAY)

    assert parsed.amount == Decimal("4.5")


def test_retries_once_with_the_error_and_succeeds():
    llm = FakeLLM([reply(category="Drinks"), reply(category="Food")])

    parsed = parse_expense_text("4.50 bubble tea", llm, TODAY)

    assert parsed.category == "Food"
    assert len(llm.calls) == 2
    retry_prompt = llm.calls[1]["system"]
    assert "Your previous reply was rejected" in retry_prompt
    assert "'Drinks'" in retry_prompt
    # The user's text is resent unchanged, separate from our instructions.
    assert llm.calls[1]["user"] == "4.50 bubble tea"


def test_gives_up_after_the_retry_also_fails():
    llm = FakeLLM([reply(category="Drinks"), reply(category="Beverages")])

    with pytest.raises(ExpenseParseError, match="rephrasing"):
        parse_expense_text("4.50 bubble tea", llm, TODAY)

    assert len(llm.calls) == 2


def test_retries_on_invalid_json():
    llm = FakeLLM(["this is not json", reply()])

    parsed = parse_expense_text("4.50 bubble tea", llm, TODAY)

    assert parsed.amount == Decimal("4.50")
    assert len(llm.calls) == 2


def test_missing_amount_asks_the_user_without_retrying():
    llm = FakeLLM([reply(amount=None)])

    with pytest.raises(MissingAmountError, match="include how much you spent"):
        parse_expense_text("bubble tea yesterday", llm, TODAY)

    assert len(llm.calls) == 1


def test_default_currency_reaches_the_prompt():
    llm = FakeLLM([reply(currency="MYR")])

    parse_expense_text("12 nasi lemak", llm, TODAY, default_currency="MYR")

    assert 'If no currency is mentioned, use "MYR"' in llm.calls[0]["system"]
