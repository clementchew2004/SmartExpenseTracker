import datetime
from typing import get_args

from app.llm.prompts import build_parse_prompt
from app.schemas import Category

TODAY = datetime.date(2026, 10, 22)


def test_prompt_includes_today_and_weekday():
    prompt = build_parse_prompt(TODAY, "GBP")

    assert "Today is 2026-10-22 (Thursday)" in prompt


def test_prompt_lists_every_category():
    prompt = build_parse_prompt(TODAY, "GBP")

    for category in get_args(Category):
        assert category in prompt


def test_prompt_uses_the_default_currency_passed_in():
    prompt = build_parse_prompt(TODAY, "MYR")

    assert 'If no currency is mentioned, use "MYR"' in prompt


def test_prompt_mentions_json():
    # OpenAI's JSON mode refuses requests whose prompt never says "JSON".
    assert "JSON" in build_parse_prompt(TODAY, "GBP")


def test_prompt_has_no_unfilled_placeholders():
    prompt = build_parse_prompt(TODAY, "GBP")

    assert "{" not in prompt
    assert "}" not in prompt
