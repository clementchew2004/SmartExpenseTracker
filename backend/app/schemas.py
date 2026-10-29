import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

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


class ParseTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)


class ParsedExpense(BaseModel):
    """What the LLM extracted from a sentence. Never saved until the user confirms."""

    # Any sign, and None if not mentioned: code rejects those afterwards
    # (only the user can fix them, so they must not trigger a model retry).
    amount: Annotated[Decimal, Field(max_digits=12, decimal_places=2)] | None
    currency: Currency
    date: datetime.date
    # The model's copy of the date words, e.g. "last friday". Used to work out
    # weekday dates in code; never sent back to the client.
    date_text: str | None = Field(default=None, exclude=True)
    merchant: Merchant
    category: Category
    note: str | None = None


class ParseResult(BaseModel):
    expenses: list[ParsedExpense]


class MonthlyStats(BaseModel):
    month: str
    totals: dict[Currency, dict[Category, Decimal]]
    currency_totals: dict[Currency, Decimal]


# --- Auth ---


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr  # checks it's a real email format, e.g. me@gmail.co.uk
    # 8+ characters, no symbol rules (length matters most); 128 max so nobody can
    # make the deliberately slow hasher chew on a megabyte "password".
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=1, max_length=64)
    default_currency: Currency


class UserRead(BaseModel):
    """What the API shows about a user - never the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    default_currency: Currency


class TokenResponse(BaseModel):
    """OAuth2's standard shape: the app sends "Authorization: Bearer <access_token>"."""

    access_token: str
    token_type: str = "bearer"


# --- Budgets ---


class BudgetAmount(BaseModel):
    """Body for setting a budget: just the amount (currency is in the URL)."""

    model_config = ConfigDict(extra="forbid")

    amount: Amount  # > 0, at most 2 decimal places


class BudgetStatus(BaseModel):
    currency: Currency
    amount: Decimal  # the budget that applies this month
    source: Literal["month", "default"]  # this month's own amount, or your usual one
    spent: Decimal  # SQL total of this month's expenses in this currency
    outlook: Literal[
        "upcoming", "too_early", "on_track", "likely_over", "over", "under"
    ]


class MonthBudgets(BaseModel):
    month: str
    budgets: list[BudgetStatus]  # only currencies that have a budget
    defaults: dict[Currency, Decimal]  # your usual amounts; empty = not set up yet


# --- Repeating expenses ---

Frequency = Literal["daily", "weekly", "monthly"]


class RepeatCreate(ExpenseCreate):
    """Repeat an expense you just saved. `date` is that first expense's date;
    the first reminder is the date after it (e.g. a month later)."""

    frequency: Frequency
    end_date: datetime.date | None = None  # empty = until you stop it

    @model_validator(mode="after")
    def end_not_before_start(self) -> "RepeatCreate":
        if self.end_date is not None and self.end_date < self.date:
            raise ValueError("end_date can't be before the first date")
        return self


class RepeatDetails(BaseModel):
    """What a repeat's future copies look like; used to check an edit's result."""

    amount: Amount
    currency: Currency
    merchant: Merchant
    category: Category
    note: str | None = None
    end_date: datetime.date | None = None


class RepeatUpdate(BaseModel):
    """Changes future reminders only; expenses already saved are never touched."""

    model_config = ConfigDict(extra="forbid")

    amount: Amount | None = None
    currency: Currency | None = None
    merchant: Merchant | None = None
    category: Category | None = None
    note: str | None = None
    end_date: datetime.date | None = None


class RepeatRead(RepeatDetails):
    model_config = ConfigDict(from_attributes=True)

    id: int
    frequency: Frequency
    day_of_month: int
    next_due: datetime.date
    finished: bool = False  # past its end date: no more reminders


class DueReminder(BaseModel):
    """One reminder card: a repeat's date that hasn't been saved or skipped."""

    repeat_id: int
    due_date: datetime.date
    amount: Decimal
    currency: Currency
    merchant: str
    category: Category
    note: str | None


class RepeatSave(ExpenseCreate):
    """Save a reminder: the card's (possibly edited) expense, plus which due
    date it's for, so the same card can never be saved twice."""

    due_date: datetime.date


class RepeatSkip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    due_date: datetime.date
