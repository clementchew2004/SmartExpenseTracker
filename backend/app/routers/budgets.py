import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.models import Budget, DefaultBudget
from app.schemas import BudgetAmount, Currency, MonthBudgets
from app.services.budgets import budget_statuses

router = APIRouter(prefix="/budgets", tags=["budgets"])

DbSession = Annotated[Session, Depends(get_db)]
MonthText = Annotated[str, Path(pattern=r"^\d{4}-\d{2}$", examples=["2026-10"])]


def first_of_month(month: str) -> datetime.date:
    """'2026-10' -> 2026-10-01, the way months are stored."""
    try:
        return datetime.datetime.strptime(month, "%Y-%m").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="month must be in YYYY-MM format, e.g. 2026-10",
        )


@router.get("")
def get_month_budgets(month: str, db: DbSession, user: CurrentUser) -> MonthBudgets:
    start = first_of_month(month)
    defaults = db.scalars(
        select(DefaultBudget).where(DefaultBudget.user_id == user.id)
    ).all()
    return MonthBudgets(
        month=month,
        budgets=budget_statuses(db, user.id, start, datetime.date.today()),
        defaults={d.currency: d.amount for d in defaults},
    )


# The /default routes come before /{month}: FastAPI tries routes in order, and
# "default" must not be read as a month.


@router.put("/default/{currency}")
def set_default_budget(
    currency: Currency, body: BudgetAmount, db: DbSession, user: CurrentUser
) -> BudgetAmount:
    """Your usual monthly budget in this currency (create or change it)."""
    row = db.scalar(
        select(DefaultBudget).where(
            DefaultBudget.user_id == user.id, DefaultBudget.currency == currency
        )
    )
    if row is None:
        row = DefaultBudget(user_id=user.id, currency=currency)
        db.add(row)
    row.amount = body.amount
    db.commit()
    return BudgetAmount(amount=row.amount)


@router.delete("/default/{currency}", status_code=status.HTTP_204_NO_CONTENT)
def delete_default_budget(currency: Currency, db: DbSession, user: CurrentUser) -> None:
    """Stop budgeting in this currency by default (e.g. MYR after a trip)."""
    row = db.scalar(
        select(DefaultBudget).where(
            DefaultBudget.user_id == user.id, DefaultBudget.currency == currency
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()


@router.put("/{month}/{currency}")
def set_month_budget(
    month: MonthText,
    currency: Currency,
    body: BudgetAmount,
    db: DbSession,
    user: CurrentUser,
) -> BudgetAmount:
    """This month's own budget in this currency; replaces the default for that month."""
    start = first_of_month(month)
    row = db.scalar(
        select(Budget).where(
            Budget.user_id == user.id,
            Budget.month == start,
            Budget.currency == currency,
        )
    )
    if row is None:
        row = Budget(user_id=user.id, month=start, currency=currency)
        db.add(row)
    row.amount = body.amount
    db.commit()
    return BudgetAmount(amount=row.amount)


@router.delete("/{month}/{currency}", status_code=status.HTTP_204_NO_CONTENT)
def delete_month_budget(
    month: MonthText, currency: Currency, db: DbSession, user: CurrentUser
) -> None:
    """Remove this month's own amount, so the default applies again."""
    row = db.scalar(
        select(Budget).where(
            Budget.user_id == user.id,
            Budget.month == first_of_month(month),
            Budget.currency == currency,
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()
