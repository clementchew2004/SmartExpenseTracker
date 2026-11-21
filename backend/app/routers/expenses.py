import csv
import datetime
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.models import Expense
from app.schemas import Category, ExpenseCreate, ExpenseRead, ExpenseUpdate

router = APIRouter(prefix="/expenses", tags=["expenses"])

DbSession = Annotated[Session, Depends(get_db)]


def find_expense(db: Session, expense_id: int, user_id: int) -> Expense:
    # Matching on the owner too means someone else's expense looks exactly like
    # one that doesn't exist: a 404 that reveals nothing about other users.
    expense = db.scalar(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    )
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.get("")
def list_expenses(
    db: DbSession,
    user: CurrentUser,
    date_from: Annotated[datetime.date | None, Query(alias="from")] = None,
    date_to: Annotated[datetime.date | None, Query(alias="to")] = None,
    category: Category | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ExpenseRead]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'from' must be on or before 'to'",
        )

    stmt = select(Expense).where(Expense.user_id == user.id)
    if date_from is not None:
        stmt = stmt.where(Expense.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Expense.date <= date_to)
    if category is not None:
        stmt = stmt.where(Expense.category == category)

    stmt = stmt.order_by(Expense.date.desc(), Expense.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    return db.scalars(stmt).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_expense(
    expense: ExpenseCreate, db: DbSession, user: CurrentUser
) -> ExpenseRead:
    # The owner comes from the token, never from the request body.
    new_expense = Expense(**expense.model_dump(), user_id=user.id)
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    return new_expense


# Excel treats a cell starting with one of these as a formula, so a merchant
# like "=HYPERLINK(...)" could run when the file is opened ("CSV injection").
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
CSV_COLUMNS = ["date", "amount", "currency", "merchant", "category", "note", "source"]


def safe_cell(value: object) -> str:
    """Text a spreadsheet won't run: a leading ' makes formula-like text plain."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_START) else text


# Declared before /{expense_id}, or "export.csv" would be read as an id (422).
@router.get("/export.csv")
def export_csv(db: DbSession, user: CurrentUser) -> Response:
    """Every expense of yours as a spreadsheet file, oldest first."""
    expenses = db.scalars(
        select(Expense)
        .where(Expense.user_id == user.id)
        .order_by(Expense.date, Expense.id)
    ).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for e in expenses:
        # Amounts are written as-is (Decimal text), never as formulas or floats.
        writer.writerow(
            [e.date.isoformat(), str(e.amount), e.currency]
            + [safe_cell(v) for v in (e.merchant, e.category, e.note, e.source)]
        )
    filename = f"expenses-{datetime.date.today().isoformat()}.csv"
    return Response(
        # A byte-order mark tells Excel the file is UTF-8 (for £ and accents).
        content="\ufeff" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{expense_id}")
def get_expense(expense_id: int, db: DbSession, user: CurrentUser) -> ExpenseRead:
    return find_expense(db, expense_id, user.id)


@router.patch("/{expense_id}")
def update_expense(
    expense_id: int, changes: ExpenseUpdate, db: DbSession, user: CurrentUser
) -> ExpenseRead:
    # 1. Find
    expense = find_expense(db, expense_id, user.id)

    # 2. Only what the client sent
    sent_fields = changes.model_dump(exclude_unset=True)

    # 3. Validate the merged result before touching the row
    current = ExpenseRead.model_validate(expense).model_dump()
    try:
        ExpenseRead.model_validate(current | sent_fields)
    except ValidationError as e:
        raise RequestValidationError(e.errors()) from e

    # 4. Apply each change to the tracked object
    for field, value in sent_fields.items():
        setattr(expense, field, value)

    # 5. Save
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: DbSession, user: CurrentUser) -> None:
    expense = find_expense(db, expense_id, user.id)
    db.delete(expense)
    db.commit()
