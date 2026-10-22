import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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

Amount = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Merchant = Annotated[str, Field(min_length=1, max_length=100)]


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Amount
    currency: Currency
    date: datetime.date
    merchant: Merchant
    category: Category
    note: str | None = None


class ExpenseRead(ExpenseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ExpenseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Amount | None = None
    currency: Currency | None = None
    date: datetime.date | None = None
    merchant: Merchant | None = None
    category: Category | None = None
    note: str | None = None


class ParsedExpense(BaseModel):
    """What the LLM extracted from a sentence. Never saved until the user confirms."""

    amount: Amount | None  # None = the text didn't mention an amount
    currency: Currency
    date: datetime.date
    merchant: Merchant
    category: Category
    note: str | None = None


class MonthlyStats(BaseModel):
    month: str
    totals: dict[Currency, dict[Category, Decimal]]
