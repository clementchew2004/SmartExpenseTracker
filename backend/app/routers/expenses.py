from fastapi import APIRouter, HTTPException, status

from app.schemas import ExpenseCreate, ExpenseRead

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


@router.put("/{expense_id}")
def replace_expense(expense_id: int, new_expense: ExpenseCreate) -> ExpenseRead:
    old_expense = find_expense(expense_id)
    updated = ExpenseRead(id=expense_id, **new_expense.model_dump())
    expenses[expenses.index(old_expense)] = updated
    return updated


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int) -> None:
    expenses.remove(find_expense(expense_id))
