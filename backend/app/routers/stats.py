import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.schemas import BudgetPace, CategoryChanges, MonthlyStats, SpendingTrend
from app.services.changes import category_changes
from app.services.pace import budget_pace
from app.services.stats import monthly_currency_totals, monthly_totals
from app.services.trend import spending_trend
from app.today import Today

router = APIRouter(prefix="/stats", tags=["stats"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/monthly")
def monthly_stats(month: str, db: DbSession, user: CurrentUser) -> MonthlyStats:
    try:
        start = datetime.datetime.strptime(month, "%Y-%m").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="month must be in YYYY-MM format, e.g. 2026-10",
        )

    if start.month == 12:
        end = datetime.date(start.year + 1, 1, 1)
    else:
        end = datetime.date(start.year, start.month + 1, 1)

    return MonthlyStats(
        month=month,
        totals=monthly_totals(db, user.id, start, end),
        currency_totals=monthly_currency_totals(db, user.id, start, end),
    )


def parse_month(month: str) -> datetime.date:
    """ "2026-10" -> 1 Oct 2026, or a 422 the screen can show."""
    try:
        return datetime.datetime.strptime(month, "%Y-%m").date()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="month must be in YYYY-MM format, e.g. 2026-10",
        ) from e


@router.get("/trend")
def trend(month: str, db: DbSession, user: CurrentUser, today: Today) -> SpendingTrend:
    """The six months ending at `month`, per currency: totals, per-category
    totals and each month's budget. For the Insights graphs."""
    return spending_trend(db, user.id, parse_month(month), today)


@router.get("/pace")
def pace(month: str, db: DbSession, user: CurrentUser, today: Today) -> BudgetPace:
    """`month` day by day, per currency: the running total spent and the even pace
    that would land on the budget. For the Insights budget pace graph."""
    return budget_pace(db, user.id, parse_month(month), today)


@router.get("/changes")
def changes(
    month: str, db: DbSession, user: CurrentUser, today: Today
) -> CategoryChanges:
    """Each category in `month` against your average of the previous months (over
    the same days while `month` is in progress). For the Insights changes graph."""
    return category_changes(db, user.id, parse_month(month), today)
