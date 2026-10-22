import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense


def monthly_totals(
    db: Session, start: datetime.date, end: datetime.date
) -> dict[str, dict[str, Decimal]]:
    stmt = (
        select(Expense.currency, Expense.category, func.sum(Expense.amount))
        .where(Expense.date >= start, Expense.date < end)
        .group_by(Expense.currency, Expense.category)
        .order_by(Expense.currency, Expense.category)
    )

    totals: dict[str, dict[str, Decimal]] = {}
    for currency, category, total in db.execute(stmt).all():
        if currency not in totals:
            totals[currency] = {}
        totals[currency][category] = total
    return totals
