"""Changes vs usual: each category this month against your average over the
previous few months. SQL adds up each month; code averages and subtracts, in
Decimal. The screen only draws them."""

import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import get_args

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense
from app.schemas import CategoryChange, CategoryChanges, Currency, CurrencyChanges
from app.services.budgets import next_month
from app.services.trend import months_ending, previous_month

HISTORY_MONTHS = 3
PENNY = Decimal("0.01")


def category_totals(
    db: Session, user_id: int, start: datetime.date, end: datetime.date
) -> dict[tuple[str, str], Decimal]:
    """(currency, category) -> total, from `start` up to but not including `end`."""
    rows = db.execute(
        select(Expense.currency, Expense.category, func.sum(Expense.amount))
        .where(Expense.user_id == user_id, Expense.date >= start, Expense.date < end)
        .group_by(Expense.currency, Expense.category)
    ).all()
    return {(currency, category): total for currency, category, total in rows}


def category_changes(
    db: Session, user_id: int, month: datetime.date, today: datetime.date
) -> CategoryChanges:
    this_month = today.replace(day=1)
    # While a month is in progress, every month is compared over days 1..today only.
    up_to_day = today.day if month == this_month else None

    def window_end(m: datetime.date) -> datetime.date:
        """Where the compared part of month `m` stops (exclusive)."""
        if up_to_day is None:
            return next_month(m)
        # A short month (Feb) just stops at its own end.
        return min(m + datetime.timedelta(days=up_to_day), next_month(m))

    # Only months from your first expense on: before that you weren't tracking, and
    # those £0 months would make "usual" look smaller than it is.
    first = db.scalar(select(func.min(Expense.date)).where(Expense.user_id == user_id))
    history = (
        [
            m
            for m in months_ending(previous_month(month), HISTORY_MONTHS)
            if m >= first.replace(day=1)
        ]
        if first is not None and month <= this_month
        else []
    )

    empty = CategoryChanges(
        month=month.strftime("%Y-%m"),
        compared_months=[],
        up_to_day=up_to_day,
        currencies=[
            CurrencyChanges(currency=c, changes=[]) for c in get_args(Currency)
        ],
    )
    if not history:
        return empty  # nothing to compare with yet (or a month still to come)

    now = category_totals(db, user_id, month, window_end(month))
    before = [category_totals(db, user_id, m, window_end(m)) for m in history]

    currencies = []
    for currency in get_args(Currency):
        categories = {cat for cur, cat in now if cur == currency} | {
            cat for totals in before for cur, cat in totals if cur == currency
        }
        changes = []
        for category in categories:
            spent = now.get((currency, category), Decimal("0.00"))
            usual = (
                sum(
                    (t.get((currency, category), Decimal("0.00")) for t in before),
                    Decimal("0.00"),
                )
                / len(before)
            ).quantize(PENNY, rounding=ROUND_HALF_UP)
            changes.append(
                CategoryChange(
                    category=category, now=spent, usual=usual, change=spent - usual
                )
            )
        # Biggest change first, whichever way; ties by name so the order is stable.
        changes.sort(key=lambda c: (-abs(c.change), c.category))
        currencies.append(CurrencyChanges(currency=currency, changes=changes))

    return CategoryChanges(
        month=month.strftime("%Y-%m"),
        compared_months=[m.strftime("%Y-%m") for m in history],
        up_to_day=up_to_day,
        currencies=currencies,
    )
