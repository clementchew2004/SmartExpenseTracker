"""The Insights graphs' numbers: spending per month for the last six months,
per currency and per category, with each month's budget. All SQL and code;
the screen only draws them."""

import datetime
from decimal import Decimal
from typing import get_args

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense
from app.schemas import Currency, CurrencyTrend, SpendingTrend, TrendMonth
from app.services.budgets import month_budgets, next_month

MONTHS_SHOWN = 6


def previous_month(month: datetime.date) -> datetime.date:
    if month.month == 1:
        return datetime.date(month.year - 1, 12, 1)
    return datetime.date(month.year, month.month - 1, 1)


def months_ending(
    month: datetime.date, count: int = MONTHS_SHOWN
) -> list[datetime.date]:
    """The 1st of each of the `count` months ending at `month`, oldest first."""
    months = [month]
    while len(months) < count:
        months.insert(0, previous_month(months[0]))
    return months


def spending_trend(
    db: Session, user_id: int, month: datetime.date, today: datetime.date
) -> SpendingTrend:
    months = months_ending(month)
    key = func.to_char(Expense.date, "YYYY-MM")
    rows = db.execute(
        select(Expense.currency, key, Expense.category, func.sum(Expense.amount))
        .where(
            Expense.user_id == user_id,
            Expense.date >= months[0],
            Expense.date < next_month(months[-1]),
        )
        .group_by(Expense.currency, key, Expense.category)
    ).all()

    # (currency, "2026-10") -> {category: total}; months with nothing stay empty.
    spent: dict[tuple[str, str], dict[str, Decimal]] = {}
    for currency, month_key, category, total in rows:
        spent.setdefault((currency, month_key), {})[category] = total

    budgets = {m: month_budgets(db, user_id, m) for m in months}
    this_month = today.replace(day=1)

    currencies = []
    for currency in get_args(Currency):
        trend_months = []
        for m in months:
            month_key = m.strftime("%Y-%m")
            by_category = spent.get((currency, month_key), {})
            future = m > this_month
            trend_months.append(
                TrendMonth(
                    month=month_key,
                    # A quiet month is £0 (a dip, not a gap); a future one is None.
                    total=None
                    if future
                    else sum(by_category.values(), Decimal("0.00")),
                    by_category=by_category,
                    budget=budgets[m][currency][0] if currency in budgets[m] else None,
                )
            )
        currencies.append(CurrencyTrend(currency=currency, months=trend_months))
    return SpendingTrend(month=month.strftime("%Y-%m"), currencies=currencies)
