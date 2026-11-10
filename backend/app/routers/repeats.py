import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.models import Expense, RepeatingExpense
from app.schemas import (
    DueReminder,
    ExpenseRead,
    RepeatCreate,
    RepeatDetails,
    RepeatRead,
    RepeatSave,
    RepeatSkip,
    RepeatUpdate,
)
from app.services.repeats import due_dates, following, is_finished
from app.today import Today, get_today  # noqa: F401 (tests override get_today)

router = APIRouter(prefix="/repeats", tags=["repeats"])

DbSession = Annotated[Session, Depends(get_db)]


def find_repeat(db: Session, repeat_id: int, user_id: int) -> RepeatingExpense:
    # Owner in the WHERE: someone else's repeat is a 404, like expenses.
    repeat = db.scalar(
        select(RepeatingExpense).where(
            RepeatingExpense.id == repeat_id, RepeatingExpense.user_id == user_id
        )
    )
    if repeat is None:
        raise HTTPException(status_code=404, detail="Repeating expense not found")
    return repeat


def read(repeat: RepeatingExpense) -> RepeatRead:
    return RepeatRead.model_validate(repeat).model_copy(
        update={"finished": is_finished(repeat)}
    )


def check_is_next(repeat: RepeatingExpense, due_date: datetime.date, today) -> None:
    """Cards are handled oldest first, once each. Anything else is a stale card
    (e.g. a double tap) and must not create a second expense."""
    if due_date != repeat.next_due or due_date > today or is_finished(repeat):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This reminder was already dealt with - refresh to see what's due",
        )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_repeat(body: RepeatCreate, db: DbSession, user: CurrentUser) -> RepeatRead:
    """Start repeating an expense you've just saved (its date = the first one)."""
    repeat = RepeatingExpense(
        user_id=user.id,
        amount=body.amount,
        currency=body.currency,
        merchant=body.merchant,
        category=body.category,
        note=body.note,
        frequency=body.frequency,
        day_of_month=body.date.day,
        next_due=following(body.date, body.frequency, body.date.day),
        end_date=body.end_date,
    )
    db.add(repeat)
    db.commit()
    db.refresh(repeat)
    return read(repeat)


@router.get("")
def list_repeats(db: DbSession, user: CurrentUser) -> list[RepeatRead]:
    """Every repeat you've set up, for Settings."""
    repeats = db.scalars(
        select(RepeatingExpense)
        .where(RepeatingExpense.user_id == user.id)
        .order_by(RepeatingExpense.merchant, RepeatingExpense.id)
    ).all()
    return [read(r) for r in repeats]


@router.get("/due")
def due_reminders(db: DbSession, user: CurrentUser, today: Today) -> list[DueReminder]:
    """The reminder cards: worked out now, from next_due and today. No cron."""
    repeats = db.scalars(
        select(RepeatingExpense).where(RepeatingExpense.user_id == user.id)
    ).all()
    reminders = [
        DueReminder(
            repeat_id=r.id,
            due_date=date,
            amount=r.amount,
            currency=r.currency,
            merchant=r.merchant,
            category=r.category,
            note=r.note,
        )
        for r in repeats
        for date in due_dates(r, today)
    ]
    return sorted(reminders, key=lambda d: (d.due_date, d.merchant))


@router.post("/{repeat_id}/save", status_code=status.HTTP_201_CREATED)
def save_reminder(
    repeat_id: int, body: RepeatSave, db: DbSession, user: CurrentUser, today: Today
) -> ExpenseRead:
    """You confirmed the card: save it as a real expense, then move on."""
    repeat = find_repeat(db, repeat_id, user.id)
    check_is_next(repeat, body.due_date, today)
    expense = Expense(
        **body.model_dump(exclude={"due_date"}), user_id=user.id, source="repeat"
    )
    db.add(expense)
    repeat.next_due = following(repeat.next_due, repeat.frequency, repeat.day_of_month)
    db.commit()  # the expense and the move-on together: both happen or neither
    db.refresh(expense)
    return expense


@router.post("/{repeat_id}/skip", status_code=status.HTTP_204_NO_CONTENT)
def skip_reminder(
    repeat_id: int, body: RepeatSkip, db: DbSession, user: CurrentUser, today: Today
) -> None:
    """You didn't pay this one (away, a free month): move on without saving."""
    repeat = find_repeat(db, repeat_id, user.id)
    check_is_next(repeat, body.due_date, today)
    repeat.next_due = following(repeat.next_due, repeat.frequency, repeat.day_of_month)
    db.commit()


@router.patch("/{repeat_id}")
def update_repeat(
    repeat_id: int, changes: RepeatUpdate, db: DbSession, user: CurrentUser
) -> RepeatRead:
    """Change future reminders. Expenses already saved are separate rows, so
    nothing here can touch them."""
    repeat = find_repeat(db, repeat_id, user.id)
    sent = changes.model_dump(exclude_unset=True)

    # Validate the merged result (the Phase 1 lesson): "amount": null is allowed
    # by RepeatUpdate but would break a NOT NULL column.
    current = RepeatDetails.model_validate(repeat, from_attributes=True).model_dump()
    try:
        RepeatDetails.model_validate(current | sent)
    except ValidationError as e:
        raise RequestValidationError(e.errors()) from e

    for field, value in sent.items():
        setattr(repeat, field, value)
    db.commit()
    db.refresh(repeat)
    return read(repeat)


@router.delete("/{repeat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repeat(repeat_id: int, db: DbSession, user: CurrentUser) -> None:
    """Stop repeating. Expenses already saved from it stay as they are."""
    repeat = find_repeat(db, repeat_id, user.id)
    db.delete(repeat)
    db.commit()
