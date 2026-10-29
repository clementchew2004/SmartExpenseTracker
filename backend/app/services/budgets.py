"""Budgets: which amount applies to a month, how much is spent, and the outlook.

All arithmetic happens here in code (the LLM never sees budgets): spent comes
from SQL, the prediction is a simple pace calculation.
"""

import calendar
import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Budget, DefaultBudget
from app.services.stats import monthly_currency_totals

# Before this day of the month the pace swings too much to predict anything.
VERDICT_FROM_DAY = 14

Outlook = Literal[
    "upcoming",  # a future month: nothing spent yet
    "too_early",  # this month, before day 14: progress bar only
    "on_track",  # this month: at this pace you'll stay within budget
    "likely_over",  # this month: at this pace you'll go over
    "over",  # already over (any day), or a finished month that went over
    "under",  # a finished month that stayed within budget
]


def next_month(month: datetime.date) -> datetime.date:
    """The 1st of the following month. `month` is always a 1st."""
    if month.month == 12:
        return datetime.date(month.year + 1, 1, 1)
    return datetime.date(month.year, month.month + 1, 1)


def outlook(
    spent: Decimal, budget: Decimal, month: datetime.date, today: datetime.date
) -> Outlook:
    end = next_month(month)
    if today < month:
        return "upcoming"
    if today >= end:  # the month is over: a verdict, not a prediction
        return "over" if spent > budget else "under"
    if spent > budget:  # already past it: a fact, so say it on any day
        return "over"
    if today.day < VERDICT_FROM_DAY:
        return "too_early"

    # Pace: what you've spent per day so far, carried on to the end of the month.
    # e.g. £300 by the 10th of a 31-day month -> £30 a day -> £930 projected.
    days_in_month = calendar.monthrange(month.year, month.month)[1]
    projected = spent / today.day * days_in_month
    return "likely_over" if projected > budget else "on_track"


def month_budgets(
    db: Session, user_id: int, month: datetime.date
) -> dict[str, tuple[Decimal, Literal["month", "default"]]]:
    """For each currency with a budget: the amount that applies, and where it's from.
    A month's own amount wins; otherwise the default; otherwise no budget at all."""
    defaults = db.scalars(
        select(DefaultBudget).where(DefaultBudget.user_id == user_id)
    ).all()
    own = db.scalars(
        select(Budget).where(Budget.user_id == user_id, Budget.month == month)
    ).all()

    applies: dict[str, tuple[Decimal, Literal["month", "default"]]] = {
        d.currency: (d.amount, "default") for d in defaults
    }
    for b in own:
        applies[b.currency] = (b.amount, "month")  # overrides the default
    return applies


def budget_statuses(
    db: Session, user_id: int, month: datetime.date, today: datetime.date
) -> list[dict]:
    """One entry per currency that has a budget this month. Currencies are never
    mixed: GBP spending only ever counts against the GBP budget."""
    spent_by_currency = monthly_currency_totals(db, user_id, month, next_month(month))
    statuses = []
    for currency, (amount, source) in sorted(month_budgets(db, user_id, month).items()):
        spent = spent_by_currency.get(currency, Decimal("0.00"))
        statuses.append(
            {
                "currency": currency,
                "amount": amount,
                "source": source,
                "spent": spent,
                "outlook": outlook(spent, amount, month, today),
            }
        )
    return statuses
