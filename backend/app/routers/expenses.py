import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/expenses", tags=["expenses"])

Currency = Literal["GBP", "MYR"]
Category = Literal[
    "Food",
    "Groceries",
    "Transport",
    "Shopping",
    "Subscriptions",
    "Entertainment",
    "Bills",
    "Health",
    "Travel",
    "Other",
]


class Expense(BaseModel):
    id: int | None = None  # the client doesn't send this; the server sets it
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Currency
    date: datetime.date
    merchant: str
    category: Category
    note: str | None = None


# Our fake database for now. Lost every time the server restarts.
expenses: list[Expense] = []
next_id = 1


def find_expense(expense_id: int) -> Expense:
    for expense in expenses:
        if expense.id == expense_id:
            return expense
    raise HTTPException(status_code=404, detail="Expense not found")


@router.get("")
def list_expenses() -> list[Expense]:
    return expenses


@router.post("", status_code=status.HTTP_201_CREATED)
def create_expense(expense: Expense) -> Expense:
    global next_id
    expense.id = next_id
    next_id += 1
    expenses.append(expense)
    return expense


@router.get("/{expense_id}")
def get_expense(expense_id: int) -> Expense:
    return find_expense(expense_id)


@router.put("/{expense_id}")
def replace_expense(expense_id: int, new_expense: Expense) -> Expense:
    old_expense = find_expense(expense_id)
    new_expense.id = expense_id
    expenses[expenses.index(old_expense)] = new_expense
    return new_expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int) -> None:
    expenses.remove(find_expense(expense_id))
