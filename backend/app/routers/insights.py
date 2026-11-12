import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.llm.client import LLMClient, get_llm_client
from app.llm.prompts import WEEKLY_SUMMARY_PROMPT_VERSION
from app.llm.summary import NO_SPENDING, write_summary
from app.models import WeeklySummary
from app.schemas import WeekFacts, WeeklyInsights, WeekSentence, WeekSummary
from app.services.weekly import spent_anything, week_facts, weeks_in_month
from app.today import Today

router = APIRouter(prefix="/insights", tags=["insights"])

DbSession = Annotated[Session, Depends(get_db)]
LLM = Annotated[LLMClient, Depends(get_llm_client)]


def parse_month(month: str) -> datetime.date:
    try:
        return datetime.datetime.strptime(month, "%Y-%m").date()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="month must be in YYYY-MM format, e.g. 2026-11",
        ) from e


@router.get("/weekly")
def weekly(
    month: str, db: DbSession, user: CurrentUser, today: Today
) -> WeeklyInsights:
    """Every week touching the month, newest first: numbers only (cheap SQL).

    Never calls the AI, so it's instant. A week's sentence is included only
    if one was already written for exactly these numbers.
    """
    start = parse_month(month)
    weeks = []
    for week_start in weeks_in_month(start, today):
        facts = week_facts(db, user.id, week_start, start, today)
        saved = saved_summary(db, user.id, start, facts.week_start)
        fresh = saved is not None and saved.facts == fingerprint(facts)
        weeks.append(
            WeekSummary(**facts.model_dump(), summary=saved.text if fresh else None)
        )
    return WeeklyInsights(month=month, weeks=weeks)


@router.get("/weekly/{week_start}/summary")
def weekly_summary(
    week_start: datetime.date,
    month: str,
    db: DbSession,
    user: CurrentUser,
    llm: LLM,
    today: Today,
) -> WeekSentence:
    """One week's sentence, written when you tap the card (or reused for free
    if its numbers haven't changed since it was written)."""
    start = parse_month(month)
    if week_start not in weeks_in_month(start, today):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That week isn't in this month's list",
        )

    facts = week_facts(db, user.id, week_start, start, today)
    if not spent_anything(facts):
        return WeekSentence(week_start=week_start, summary=NO_SPENDING)

    numbers = fingerprint(facts)
    saved = saved_summary(db, user.id, start, week_start)
    if saved is not None and saved.facts == numbers:
        return WeekSentence(week_start=week_start, summary=saved.text)

    text = write_summary(facts, llm)
    if text is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't write a summary right now - try again shortly",
        )
    if saved is None:
        db.add(
            WeeklySummary(
                user_id=user.id,
                month=start,
                week_start=week_start,
                facts=numbers,
                text=text,
            )
        )
    else:
        saved.facts, saved.text = numbers, text
    db.commit()
    return WeekSentence(week_start=week_start, summary=text)


def fingerprint(facts: WeekFacts) -> dict:
    """What a saved sentence was written from: the numbers AND the prompt.
    If either changes, the sentence is out of date."""
    return facts.model_dump(mode="json") | {
        "prompt_version": WEEKLY_SUMMARY_PROMPT_VERSION
    }


def saved_summary(
    db: Session, user_id: int, month: datetime.date, week_start: datetime.date
) -> WeeklySummary | None:
    return db.scalar(
        select(WeeklySummary).where(
            WeeklySummary.user_id == user_id,
            WeeklySummary.month == month,
            WeeklySummary.week_start == week_start,
        )
    )
