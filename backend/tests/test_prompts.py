import datetime
from typing import get_args

from app.llm.prompts import CATEGORY_HINTS, build_parse_prompt
from app.schemas import Category

TODAY = datetime.date(2026, 10, 22)


def test_prompt_asks_for_the_date_words():
    assert '"date_text": the words in the note that say when' in build_parse_prompt(
        TODAY, "GBP"
    )


def test_every_category_has_a_hint():
    assert set(CATEGORY_HINTS) == set(get_args(Category))


def test_prompt_says_a_bare_number_is_the_amount():
    assert "Every number in the note is an amount of money" in build_parse_prompt(
        TODAY, "GBP"
    )


def test_prompt_includes_today_and_weekday():
    prompt = build_parse_prompt(TODAY, "GBP")

    assert "Today is 2026-10-22 (Thursday)" in prompt


def test_prompt_lists_every_category():
    prompt = build_parse_prompt(TODAY, "GBP")

    for category in get_args(Category):
        assert category in prompt


def test_prompt_uses_the_default_currency_passed_in():
    prompt = build_parse_prompt(TODAY, "MYR")

    assert 'If no expense in the note mentions a currency, use "MYR"' in prompt


def test_prompt_says_a_bare_amount_takes_the_notes_currency():
    prompt = build_parse_prompt(TODAY, "GBP")

    assert "use the currency of the other expenses in the same note" in prompt


def test_prompt_mentions_json():
    # OpenAI's JSON mode refuses requests whose prompt never says "JSON".
    assert "JSON" in build_parse_prompt(TODAY, "GBP")


def test_prompt_states_the_failure_mode_rules():
    prompt = build_parse_prompt(TODAY, "GBP")

    assert "one entry for each expense" in prompt
    assert "return an empty list" in prompt
    assert "keep the minus sign" in prompt


def test_prompt_has_no_unfilled_placeholders():
    prompt = build_parse_prompt(TODAY, "GBP")

    assert "{" not in prompt
    assert "}" not in prompt
