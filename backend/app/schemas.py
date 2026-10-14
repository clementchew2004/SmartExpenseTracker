import datetime
from decimal import Decimal
from typing import Literal, Annotated

from pydantic import Field, BaseModel, ConfigDict

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
    id: int
