import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.llm.client import LLMClient, get_llm_client
from app.llm.summary import NO_SPENDING, write_summary
from app.models import WeeklySummary
from app.schemas import WeekFacts, WeeklyInsights, WeekSummary
from app.services.weekly import spent_anything, week_facts, weeks_in_month
from app.today import Today

router = APIRouter(prefix="/insights", tags=["insights"])

DbSession = Annotated[Session, Depends(get_db)]
LLM = Annotated[LLMClient, Depends(get_llm_client)]


@router.get("/weekly")
def weekly(
    month: str, db: DbSession, user: CurrentUser, llm: LLM, today: Today
) -> WeeklyInsights:
    """A summary for every week touching the month, newest first.

    Numbers are recomputed on every request (cheap SQL). The AI is only asked
    to write when a week's numbers differ from the ones its saved text was
    written from: a new week, or an expense added, edited or deleted.
    """
    try:
        start = datetime.datetime.strptime(month, "%Y-%m").date()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="month must be in YYYY-MM format, e.g. 2026-11",
        ) from e

    weeks = []
    for week_start in weeks_in_month(start, today):
        facts = week_facts(db, user.id, week_start, start, today)
        weeks.append(
            WeekSummary(
                **facts.model_dump(),
                summary=summary_for(db, user.id, start, facts, llm),
            )
        )
    return WeeklyInsights(month=month, weeks=weeks)


def summary_for(
    db: Session, user_id: int, month: datetime.date, facts: WeekFacts, llm: LLMClient
) -> str | None:
    if not spent_anything(facts):
        return NO_SPENDING  # nothing to phrase, so no paid call

    saved = db.scalar(
        select(WeeklySummary).where(
            WeeklySummary.user_id == user_id,
            WeeklySummary.month == month,
            WeeklySummary.week_start == facts.week_start,
        )
    )
    numbers = facts.model_dump(mode="json")  # Decimals and dates as strings
    if saved is not None and saved.facts == numbers:
        return saved.text  # same numbers -> same summary, for free

    text = write_summary(facts, llm)
    if text is None:
        return None  # keep any old text out of sight: it describes old numbers
    if saved is None:
        db.add(
            WeeklySummary(
                user_id=user_id,
                month=month,
                week_start=facts.week_start,
                facts=numbers,
                text=text,
            )
        )
    else:
        saved.facts, saved.text = numbers, text
    db.commit()
    return text
