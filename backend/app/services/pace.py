"""Budget pace: a month's spending as a running total, day by day, next to the
pace that would land exactly on the budget. SQL adds up each day; code keeps the
running total and works out the even pace. The screen only draws them."""

import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import get_args

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense
from app.schemas import BudgetPace, Currency, CurrencyPace, PaceDay
from app.services.budgets import month_budgets, next_month

PENNY = Decimal("0.01")


def budget_pace(
    db: Session, user_id: int, month: datetime.date, today: datetime.date
) -> BudgetPace:
    end = next_month(month)
    days_in_month = (end - month).days

    # One row per currency per day that has any spending.
    rows = db.execute(
        select(Expense.currency, Expense.date, func.sum(Expense.amount))
        .where(Expense.user_id == user_id, Expense.date >= month, Expense.date < end)
        .group_by(Expense.currency, Expense.date)
    ).all()
    spent_on = {(currency, date): total for currency, date, total in rows}
    budgets = month_budgets(db, user_id, month)

    currencies = []
    for currency in get_args(Currency):
        budget = budgets[currency][0] if currency in budgets else None
        running = Decimal("0.00")
        days = []
        for i in range(days_in_month):
            date = month + datetime.timedelta(days=i)
            running += spent_on.get((currency, date), Decimal("0.00"))
            on_pace = (
                None
                if budget is None
                else (budget * (i + 1) / days_in_month).quantize(
                    PENNY, rounding=ROUND_HALF_UP
                )
            )
            # Days still to come have no point yet (an expense dated ahead waits too).
            days.append(
                PaceDay(
                    date=date, spent=None if date > today else running, on_pace=on_pace
                )
            )
        currencies.append(CurrencyPace(currency=currency, budget=budget, days=days))
    return BudgetPace(month=month.strftime("%Y-%m"), currencies=currencies)
