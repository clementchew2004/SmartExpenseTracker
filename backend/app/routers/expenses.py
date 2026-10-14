from fastapi import APIRouter, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.schemas import ExpenseCreate, ExpenseRead, ExpenseUpdate

router = APIRouter(prefix="/expenses", tags=["expenses"])


# Our fake database for now. Lost every time the server restarts.
expenses: list[ExpenseRead] = []
next_id = 1


def find_expense(expense_id: int) -> ExpenseRead:
    for expense in expenses:
        if expense.id == expense_id:
            return expense
    raise HTTPException(status_code=404, detail="Expense not found")


@router.get("")
def list_expenses() -> list[ExpenseRead]:
    return expenses


@router.post("", status_code=status.HTTP_201_CREATED)
def create_expense(expense: ExpenseCreate) -> ExpenseRead:
    global next_id
    new_expense = ExpenseRead(id=next_id, **expense.model_dump())
    next_id += 1
    expenses.append(new_expense)
    return new_expense


@router.get("/{expense_id}")
def get_expense(expense_id: int) -> ExpenseRead:
    return find_expense(expense_id)


@router.patch("/{expense_id}")
def update_expense(expense_id: int, changes: ExpenseUpdate) -> ExpenseRead:
    old_expense = find_expense(expense_id)
    sent_fields = changes.model_dump(exclude_unset=True)
    try:
        updated = ExpenseRead.model_validate(old_expense.model_dump() | sent_fields)
    except ValidationError as e:
        raise RequestValidationError(e.errors()) from e
    expenses[expenses.index(old_expense)] = updated
    return updated


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int) -> None:
    expenses.remove(find_expense(expense_id))
