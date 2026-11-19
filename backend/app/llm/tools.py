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
    """Two exact dates, both included ("from 3 Nov to 10 Nov")."""

    kind: Literal["between"]
    from_date: datetime.date
    to_date: datetime.date


Period = Annotated[
    DayPeriod | LastDaysPeriod | WeekPeriod | MonthPeriod | BetweenPeriod,
    Field(discriminator="kind"),
]


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
        case BetweenPeriod(from_date=start, to_date=end):
            if start > end:
                raise ToolError("from_date is after to_date")

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
    start: datetime.date,
    end: datetime.date,
    requested: Currency | None,
    default: Currency,
    category: Category | None = None,
) -> Currency | list[str]:
    """The currency to answer in, or the list to ask about.

    Your rule: if the question names none, use the only one you spent in; ask
    only when both were used. GBP and MYR are never added together.
    """
    if requested is not None:
        return requested
    where = [*_spent(user_id, start, end)]
    if category is not None:
        where.append(Expense.category == category)
    used = db.scalars(
        select(Expense.currency).where(*where).distinct().order_by(Expense.currency)
    ).all()
    if len(used) > 1:
        return list(used)
    return used[0] if used else default


def get_total(
    args: GetTotalArgs,
    db: Session,
    user_id: int,
    today: datetime.date,
    default_currency: Currency,
) -> dict[str, Any]:
    start, end = resolve_period(args.period, today)
    currency = _pick_currency(
        db, user_id, start, end, args.currency, default_currency, args.category
    )
    result: dict[str, Any] = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "category": args.category,
    }
    if isinstance(currency, list):
        return result | {"needs_currency": currency}

    where = [*_spent(user_id, start, end), Expense.currency == currency]
    if args.category is not None:
        where.append(Expense.category == args.category)
    total = db.scalar(select(func.sum(Expense.amount)).where(*where))
    return result | {"currency": currency, "total": str(total or Decimal("0.00"))}


def get_breakdown(
    args: GetBreakdownArgs,
    db: Session,
    user_id: int,
    today: datetime.date,
    default_currency: Currency,
) -> dict[str, Any]:
    start, end = resolve_period(args.period, today)
    currency = _pick_currency(db, user_id, start, end, args.currency, default_currency)
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


TOOLS = {
    "get_total": (
        GetTotalArgs,
        get_total,
        "Total spent in a period, optionally for one category.",
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
) -> dict[str, Any]:
    """Run one tool call from the AI. Raises ToolError for anything invalid."""
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
    return function(args, db, user_id, today, default_currency)
