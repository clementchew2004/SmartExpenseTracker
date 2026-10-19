from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Expense
from app.schemas import ExpenseCreate, ExpenseRead, ExpenseUpdate

router = APIRouter(prefix="/expenses", tags=["expenses"])

DbSession = Annotated[Session, Depends(get_db)]


def find_expense(db: Session, expense_id: int) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.get("")
def list_expenses(db: DbSession) -> list[ExpenseRead]:
    stmt = select(Expense).order_by(Expense.date.desc(), Expense.id.desc())
    return db.scalars(stmt).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_expense(expense: ExpenseCreate, db: DbSession) -> ExpenseRead:
    new_expense = Expense(**expense.model_dump())
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    return new_expense


@router.get("/{expense_id}")
def get_expense(expense_id: int, db: DbSession) -> ExpenseRead:
    return find_expense(db, expense_id)


@router.patch("/{expense_id}")
def update_expense(
    expense_id: int, changes: ExpenseUpdate, db: DbSession
) -> ExpenseRead:
    # 1. Find
    expense = find_expense(db, expense_id)

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
def delete_expense(expense_id: int, db: DbSession) -> None:
    expense = find_expense(db, expense_id)
    db.delete(expense)
    db.commit()
