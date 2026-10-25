import datetime

import pytest

from app.llm.dates import resolve_weekday

SUNDAY = datetime.date(2026, 10, 25)
MONDAY = datetime.date(2026, 10, 19)
THURSDAY = datetime.date(2026, 10, 22)


def d(day: int) -> datetime.date:
    return datetime.date(2026, 10, day)


@pytest.mark.parametrize(
    ("today", "text", "expected"),
    [
        # "last <day>" = that day in last week (Mon 12 - Sun 18 when today is the 25th).
        (SUNDAY, "last friday", d(16)),
        (SUNDAY, "last wednesday", d(14)),
        (SUNDAY, "last monday", d(12)),
        (SUNDAY, "last sunday", d(18)),
        (MONDAY, "last monday", d(12)),
        (THURSDAY, "last friday", d(16)),
        # "<day>" / "on <day>" = most recent on or before today.
        (SUNDAY, "friday", d(23)),
        (SUNDAY, "on friday", d(23)),
        (SUNDAY, "on sunday", d(25)),
        (MONDAY, "monday", d(19)),
        (THURSDAY, "friday", d(16)),
        # Short forms, capitals, extra spaces, punctuation.
        (SUNDAY, "last fri", d(16)),
        (SUNDAY, "on tues", d(20)),
        (SUNDAY, "thurs", d(22)),
        (SUNDAY, "  Last   FRIDAY. ", d(16)),
    ],
)
def test_resolves_weekday_phrases(today, text, expected):
    assert resolve_weekday(text, today) == expected


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "yesterday",
        "two days ago",
        "on the 1st",
        "20 oct",
        "last week",
        "last fri night",
    ],
)
def test_leaves_everything_else_to_the_model(text):
    assert resolve_weekday(text, SUNDAY) is None
