"""Weekly summary numbers. Everything here is SQL and arithmetic in code:
the LLM is only handed the finished numbers to put into words.

A week is Monday to Sunday. A month's list holds every week that touches the
month, so a week crossing two months (27 Oct - 2 Nov) appears in both.
"""

import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense
from app.schemas import CurrencyWeek, MerchantTotal, WeekFacts
from app.services.budgets import month_budgets, next_month

TOP_MERCHANTS = 3
WEEK = datetime.timedelta(days=7)


def monday_of(day: datetime.date) -> datetime.date:
    return day - datetime.timedelta(days=day.weekday())  # Monday is weekday 0


def weeks_in_month(month: datetime.date, today: datetime.date) -> list[datetime.date]:
    """The Mondays of every week touching `month` (a 1st), up to this week.
    Newest first. A future month has none."""
    last_day = next_month(month) - datetime.timedelta(days=1)
    week = monday_of(month)
    mondays = []
    while week <= min(last_day, today):
        mondays.append(week)
        week += WEEK
    return mondays[::-1]


def percent(part: Decimal, whole: Decimal) -> int:
    """A whole-number percentage, rounded the way people expect (14.5 -> 15)."""
    return int((part / whole * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def totals_by_currency(
    db: Session, user_id: int, start: datetime.date, end: datetime.date
) -> dict[str, Decimal]:
    """Spending per currency from `start` to `end`, both included."""
    rows = db.execute(
        select(Expense.currency, func.sum(Expense.amount))
        .where(Expense.user_id == user_id)
        .where(Expense.date >= start, Expense.date <= end)
        .group_by(Expense.currency)
    ).all()
    return dict(rows)


def top_merchants(
    db: Session, user_id: int, currency: str, start: datetime.date, end: datetime.date
) -> list[MerchantTotal]:
    rows = db.execute(
        select(Expense.merchant, func.sum(Expense.amount).label("spent"))
        .where(Expense.user_id == user_id, Expense.currency == currency)
        .where(Expense.date >= start, Expense.date <= end)
        .group_by(Expense.merchant)
        .order_by(func.sum(Expense.amount).desc(), Expense.merchant)
        .limit(TOP_MERCHANTS)
    ).all()
    return [MerchantTotal(merchant=m, spent=s) for m, s in rows]


def week_facts(
    db: Session,
    user_id: int,
    week_start: datetime.date,
    month: datetime.date,
    today: datetime.date,
) -> WeekFacts:
    week_end = week_start + datetime.timedelta(days=6)
    in_progress = week_end > today
    # This week so far: only up to today, and compared with the same days of
    # last week, so Mon-Wed isn't measured against a whole 7 days.
    until = today if in_progress else week_end
    days = (until - week_start).days + 1
    prev_start = week_start - WEEK
    prev_until = prev_start + datetime.timedelta(days=days - 1)

    # Your first week: nothing dated before it, so there's nothing to compare with.
    has_history = db.scalar(
        select(func.count())
        .select_from(Expense)
        .where(Expense.user_id == user_id, Expense.date < week_start)
    )

    spent = totals_by_currency(db, user_id, week_start, until)
    previous = totals_by_currency(db, user_id, prev_start, prev_until)
    budgets = month_budgets(db, user_id, month)

    currencies = []
    # A currency used either week, so "RM 0 this week, down from RM 40" can show.
    for currency in sorted(spent.keys() | (previous.keys() if has_history else set())):
        now = spent.get(currency, Decimal("0.00"))
        before = previous.get(currency, Decimal("0.00")) if has_history else None
        budget = budgets[currency][0] if currency in budgets else None
        currencies.append(
            CurrencyWeek(
                currency=currency,
                spent=now,
                previous=before,
                change=None if before is None else now - before,
                change_pct=percent(now - before, before) if before else None,
                budget=budget,
                budget_share_pct=percent(now, budget) if budget else None,
                top_merchants=top_merchants(db, user_id, currency, week_start, until),
            )
        )

    if not has_history:
        compared_with = None
    elif in_progress:
        compared_with = (
            "the same day last week" if days == 1 else f"the same {days} days last week"
        )
    else:
        compared_with = "last week"

    return WeekFacts(
        week_start=week_start,
        week_end=week_end,
        in_progress=in_progress,
        days_counted=days,
        compared_with=compared_with,
        currencies=currencies,
    )


def spent_anything(facts: WeekFacts) -> bool:
    return any(c.spent > 0 for c in facts.currencies)
