import datetime
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.llm.ask import answer_question
from app.llm.client import LLMClient, LLMError, get_llm_client
from app.llm.prompts import WEEKLY_SUMMARY_PROMPT_VERSION
from app.llm.summary import NO_SPENDING, saved_events, summary_events
from app.models import WeeklySummary
from app.schemas import (
    AskRequest,
    AskResponse,
    WeekFacts,
    WeeklyInsights,
    WeekSummary,
)
from app.services.weekly import spent_anything, week_facts, weeks_in_month
from app.today import Today

logger = logging.getLogger(__name__)

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


@router.get(
    "/weekly/{week_start}/summary",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def weekly_summary(
    week_start: datetime.date,
    month: str,
    db: DbSession,
    user: CurrentUser,
    llm: LLM,
    today: Today,
) -> StreamingResponse:
    """One week's sentence as Server-Sent Events, written when you tap the card.

    Events are JSON: {"type": "text", "text": "..."} as words arrive, then
    {"type": "done"} once it's checked and saved, or {"type": "error"} with
    nothing saved. A sentence already written for these numbers comes back
    in one "text" event with no AI call.
    """
    # Everything that can fail with a status code happens BEFORE streaming:
    # once the first event is sent, the response is already a 200.
    start = parse_month(month)
    if week_start not in weeks_in_month(start, today):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That week isn't in this month's list",
        )

    facts = week_facts(db, user.id, week_start, start, today)
    numbers = fingerprint(facts)
    saved = saved_summary(db, user.id, start, week_start)

    if not spent_anything(facts):
        events = saved_events(NO_SPENDING)  # nothing to phrase, so no paid call
    elif saved is not None and saved.facts == numbers:
        events = saved_events(saved.text)  # same numbers and prompt: free
    else:

        def save(text: str) -> None:
            # Runs only after the whole sentence passed SummaryReply. The
            # session is still open: FastAPI closes `yield` dependencies only
            # after a streaming response has finished.
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

        events = summary_events(facts, llm, save)

    return StreamingResponse(
        events,
        media_type="text/event-stream",
        # Proxies (e.g. on Render later) may otherwise hold the events back
        # and deliver them all at once, which defeats the point.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ask")
def ask(
    body: AskRequest, db: DbSession, user: CurrentUser, llm: LLM, today: Today
) -> AskResponse:
    """Answer a question about your spending with the agent loop (llm/ask.py).

    The AI only picks tools and their arguments; code runs fixed SQL, always
    for the logged-in user. Nothing is saved.
    """
    try:
        return answer_question(
            body.question,
            llm,
            db,
            user.id,
            today,
            user.default_currency,
            body.currency,
        )
    except LLMError as e:
        logger.error("Ask failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service is unavailable right now - try again shortly",
        ) from e


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
