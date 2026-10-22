import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import MonthlyStats
from app.services.stats import monthly_totals

router = APIRouter(prefix="/stats", tags=["stats"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/monthly")
def monthly_stats(month: str, db: DbSession) -> MonthlyStats:
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

    return MonthlyStats(month=month, totals=monthly_totals(db, start, end))
