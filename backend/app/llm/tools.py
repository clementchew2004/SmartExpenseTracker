"""Tools the AI may call to answer questions about your spending.

The AI never writes SQL and never sees the database. It can only pick one of
these functions and fill in its arguments. Then this code:
1. validates the arguments with Pydantic (they're untrusted input),
2. works out the dates itself (the AI picks *what kind* of period; code does
   the arithmetic, like resolve_weekday in Phase 2),
3. runs fixed SQL, always filtered by the user_id the route passes in - the
   AI can't choose or even see it,
4. returns only numbers, dates and fixed labels (categories, months).
   Never merchants or notes: those are text you typed, and anything returned
   here is put in front of the AI, where hidden instructions could steer it.
"""

import calendar
import datetime
import json
from decimal import Decimal
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.llm.prompts import CATEGORY_HINTS
from app.models import Expense
from app.schemas import Category, Currency
from app.services.weekly import percent


class ToolError(Exception):
    """The AI asked for something invalid. The message is sent back to it so
    it can correct the call."""


# --- When: a small menu the AI picks from ------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DayPeriod(_Strict):
    """A single day, counted back from today."""

    kind: Literal["day"]
    days_ago: int = Field(ge=0, le=366, description="0 = today, 1 = yesterday")


class LastDaysPeriod(_Strict):
    """The last N days, including today ("the last 7 days", "past fortnight")."""

    kind: Literal["last_days"]
    days: int = Field(ge=1, le=366)


class WeekPeriod(_Strict):
    """A Monday-to-Sunday week: this one (so far) or the one before."""

    kind: Literal["week"]
    which: Literal["this", "last"]


class MonthPeriod(_Strict):
    """A calendar month, e.g. "September" or "last month"."""

    kind: Literal["month"]
    month: int = Field(ge=1, le=12)
    year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
        description="Leave out unless the question names a year: the most "
        "recent such month is used.",
    )


class BetweenPeriod(_Strict):
    """Two dates, both included ("from 3 Nov to 10 Nov"). Day and month only:
    the most recent such range is used, like a month name."""

    kind: Literal["between"]
    from_day: int = Field(ge=1, le=31)
    from_month: int = Field(ge=1, le=12)
    to_day: int = Field(ge=1, le=31)
    to_month: int = Field(ge=1, le=12)
    # The AI once wrote 2023 for "1 Oct" in 2026: years are code's job unless
    # the question actually names one.
    year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
        description="The year of the from date. Leave out unless the question "
        "names a year.",
    )


Period = Annotated[
    DayPeriod | LastDaysPeriod | WeekPeriod | MonthPeriod | BetweenPeriod,
    Field(discriminator="kind"),
]


def _date(year: int, month: int, day: int) -> datetime.date:
    try:
        return datetime.date(year, month, day)
    except ValueError as e:
        raise ToolError(f"{day}/{month}/{year} isn't a real date") from e


def _between(
    period: BetweenPeriod, today: datetime.date
) -> tuple[datetime.date, datetime.date]:
    """Day/month pairs -> real dates. Without a year: the most recent range
    that has started (3 Nov asked on 19 Nov -> this year; 3 Dec -> last year).
    A range like 20 Dec - 5 Jan crosses New Year."""
    starts = (period.from_month, period.from_day)
    if period.year is not None:
        start_year = period.year
    elif starts <= (today.month, today.day):
        start_year = today.year
    else:
        start_year = today.year - 1
    crosses_new_year = (period.to_month, period.to_day) < starts
    return (
        _date(start_year, period.from_month, period.from_day),
        _date(start_year + crosses_new_year, period.to_month, period.to_day),
    )


def resolve_period(
    period: Period, today: datetime.date
) -> tuple[datetime.date, datetime.date]:
    """The first and last day of the period, both included. Never past today."""
    match period:
        case DayPeriod(days_ago=n):
            start = end = today - datetime.timedelta(days=n)
        case LastDaysPeriod(days=n):
            start, end = today - datetime.timedelta(days=n - 1), today
        case WeekPeriod(which=which):
            monday = today - datetime.timedelta(days=today.weekday())
            if which == "last":
                monday -= datetime.timedelta(days=7)
            start, end = monday, monday + datetime.timedelta(days=6)
        case MonthPeriod(month=month, year=year):
            if (
                year is None
            ):  # the most recent one: September asked in March -> last year's
                year = today.year if month <= today.month else today.year - 1
            start = datetime.date(year, month, 1)
            end = datetime.date(year, month, calendar.monthrange(year, month)[1])
        case BetweenPeriod():
            start, end = _between(period, today)

    if start > today:
        raise ToolError("That period is in the future - there's no spending yet")
    return start, min(end, today)


# --- The tools' arguments: what the AI fills in --------------------------------

CATEGORY_HELP = "Only if the question is about one kind of spending. " + "; ".join(
    f"{name}: {CATEGORY_HINTS[name]}" for name in get_args(Category)
)
CURRENCY_HELP = (
    "Only if the question says (£/pounds/GBP or RM/ringgit/MYR). Otherwise leave "
    "it out: the tool picks it, or tells you to ask."
)


class GetTotalArgs(_Strict):
    period: Period
    category: Category | None = Field(default=None, description=CATEGORY_HELP)
    currency: Currency | None = Field(default=None, description=CURRENCY_HELP)


class GetBreakdownArgs(_Strict):
    group_by: Literal["category", "month"]
    period: Period
    currency: Currency | None = Field(default=None, description=CURRENCY_HELP)


# --- Running them --------------------------------------------------------------


def _spent(user_id: int, start: datetime.date, end: datetime.date):
    """Base filter for every query: this user, this date range. user_id comes
    from the caller (the logged-in user), never from the AI."""
    return (
        Expense.user_id == user_id,
        Expense.date >= start,
        Expense.date <= end,
    )


def _pick_currency(
    db: Session,
    user_id: int,
    ranges: list[tuple[datetime.date, datetime.date]],
    requested: Currency | None,
    default: Currency,
    category: Category | None = None,
) -> Currency | list[str]:
    """The currency to answer in, or the list to ask about.

    Your rule: if the question names none, use the only one you spent in
    (across every period it covers); ask only when both were used. GBP and
    MYR are never added together.
    """
    if requested is not None:
        return requested
    used: set[str] = set()
    for start, end in ranges:
        where = [*_spent(user_id, start, end)]
        if category is not None:
            where.append(Expense.category == category)
        used.update(db.scalars(select(Expense.currency).where(*where).distinct()))
    if len(used) > 1:
        return sorted(used)
    return used.pop() if used else default


def _total(
    db: Session,
    user_id: int,
    start: datetime.date,
    end: datetime.date,
    currency: str,
    category: Category | None,
) -> Decimal:
    where = [*_spent(user_id, start, end), Expense.currency == currency]
    if category is not None:
        where.append(Expense.category == category)
    total = db.scalar(select(func.sum(Expense.amount)).where(*where))
    return total or Decimal("0.00")


def get_total(
    args: GetTotalArgs,
    db: Session,
    user_id: int,
    today: datetime.date,
    default_currency: Currency,
) -> dict[str, Any]:
    start, end = resolve_period(args.period, today)
    currency = _pick_currency(
        db, user_id, [(start, end)], args.currency, default_currency, args.category
    )
    result: dict[str, Any] = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "category": args.category,
    }
    if isinstance(currency, list):
        return result | {"needs_currency": currency}
    total = _total(db, user_id, start, end, currency, args.category)
    return result | {"currency": currency, "total": str(total)}


def get_breakdown(
    args: GetBreakdownArgs,
    db: Session,
    user_id: int,
    today: datetime.date,
    default_currency: Currency,
) -> dict[str, Any]:
    start, end = resolve_period(args.period, today)
    currency = _pick_currency(
        db, user_id, [(start, end)], args.currency, default_currency
    )
    result: dict[str, Any] = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "group_by": args.group_by,
    }
    if isinstance(currency, list):
        return result | {"needs_currency": currency}

    # Both labels come from code, never from text you typed: a category from
    # the fixed list, or a month like "2026-09".
    label = (
        Expense.category
        if args.group_by == "category"
        else func.to_char(Expense.date, "YYYY-MM")
    )
    total = func.sum(Expense.amount)
    order = total.desc() if args.group_by == "category" else label
    rows = db.execute(
        select(label, total)
        .where(*_spent(user_id, start, end), Expense.currency == currency)
        .group_by(label)
        .order_by(order)
    ).all()
    return result | {
        "currency": currency,
        "rows": [{"label": name, "total": str(amount)} for name, amount in rows],
    }


class CompareArgs(_Strict):
    period_a: Period = Field(description="The first period in the question")
    period_b: Period = Field(description="The period it's compared with")
    category: Category | None = Field(default=None, description=CATEGORY_HELP)
    currency: Currency | None = Field(default=None, description=CURRENCY_HELP)


def compare(
    args: CompareArgs,
    db: Session,
    user_id: int,
    today: datetime.date,
    default_currency: Currency,
) -> dict[str, Any]:
    """Both totals AND the difference, worked out here, so the AI never has
    to subtract (it's bad at it, and the rule says it mustn't)."""
    a = resolve_period(args.period_a, today)
    b = resolve_period(args.period_b, today)
    currency = _pick_currency(
        db, user_id, [a, b], args.currency, default_currency, args.category
    )
    result: dict[str, Any] = {"category": args.category}
    if isinstance(currency, list):
        return result | {"needs_currency": currency}

    total_a = _total(db, user_id, *a, currency, args.category)
    total_b = _total(db, user_id, *b, currency, args.category)
    difference = total_a - total_b
    return result | {
        "currency": currency,
        "a": {"from": a[0].isoformat(), "to": a[1].isoformat(), "total": str(total_a)},
        "b": {"from": b[0].isoformat(), "to": b[1].isoformat(), "total": str(total_b)},
        # Positive: A was more. Write it without the sign: "£23.40 more".
        "difference_a_minus_b": str(difference),
        "change_pct_a_vs_b": percent(difference, total_b) if total_b else None,
    }


TOOLS = {
    "get_total": (
        GetTotalArgs,
        get_total,
        "Total spent in a period, optionally for one category.",
    ),
    "compare": (
        CompareArgs,
        compare,
        (
            "Two periods side by side, with the difference and % change already "
            "worked out. For ANY comparison ('vs', 'more than', 'than last month') "
            "call this once - not get_total twice - and pass the category if the "
            "question names one."
        ),
    ),
    "get_breakdown": (
        GetBreakdownArgs,
        get_breakdown,
        "Spending in a period split by category (biggest first) or by month.",
    ),
}


def tool_schemas() -> list[dict[str, Any]]:
    """The tool descriptions sent to the AI, generated from the same Pydantic
    models that validate its arguments, so the two can't drift apart."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": model.model_json_schema(),
            },
        }
        for name, (model, _, description) in TOOLS.items()
    ]


def run_tool(
    name: str,
    arguments: str,
    db: Session,
    user_id: int,
    today: datetime.date,
    default_currency: Currency,
    currency: Currency | None = None,
) -> dict[str, Any]:
    """Run one tool call from the AI. Raises ToolError for anything invalid.

    `currency` is the one you picked with the GBP/MYR buttons: it overrides
    whatever the AI asked for.
    """
    if name not in TOOLS:
        raise ToolError(f"There is no tool called {name!r}")
    model, function, _ = TOOLS[name]
    try:
        args = model.model_validate(json.loads(arguments))
    except json.JSONDecodeError as e:
        raise ToolError("The arguments weren't valid JSON") from e
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'arguments'}: {err['msg']}"
            for err in e.errors()
        )
        raise ToolError(f"Invalid arguments - {problems}") from e
    if currency is not None:
        args = args.model_copy(update={"currency": currency})
    return function(args, db, user_id, today, default_currency)
