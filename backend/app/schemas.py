import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

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


class ExpenseBase(BaseModel):
    """The fields every expense has. Repeats reuse these, but not `source`:
    the server labels repeat copies itself."""

    model_config = ConfigDict(extra="forbid")

    amount: Amount
    currency: Currency
    date: datetime.date
    merchant: Merchant
    category: Category
    note: str | None = None


# Where an expense came from. Only the browser knows (parsing and saving are
# separate requests), so it says - but never "repeat", which only the server sets.
ClientSource = Literal["manual", "text", "receipt"]
Source = Literal["manual", "text", "receipt", "repeat"]


class ExpenseCreate(ExpenseBase):
    source: ClientSource = "manual"
    # What you typed, kept for building eval cases later; "receipt" for photos.
    raw_input: Annotated[str, Field(max_length=500)] | None = None


class ExpenseRead(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: Source
    raw_input: str | None


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


class ReceiptReply(BaseModel):
    """The model's reply for a receipt: one expense (the total), or none if
    the photo isn't a receipt. A second entry is a model mistake, so it fails
    validation and triggers the retry."""

    expenses: Annotated[list[ParsedExpense], Field(max_length=1)]


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


class UserUpdate(BaseModel):
    """Settings you can change about yourself. Only new expenses typed without
    a currency use the default; saved ones keep their own."""

    model_config = ConfigDict(extra="forbid")
    default_currency: Currency


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)  # same rule as register


class DeleteAccountRequest(BaseModel):
    """You must type DELETE. Checked here on the server too, not only on screen,
    so no stray request (or bug) can delete an account by accident."""

    model_config = ConfigDict(extra="forbid")
    confirm: Literal["DELETE"]


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


class RepeatCreate(ExpenseBase):
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


class RepeatSave(ExpenseBase):
    """Save a reminder: the card's (possibly edited) expense, plus which due
    date it's for, so the same card can never be saved twice."""

    due_date: datetime.date


class RepeatSkip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    due_date: datetime.date


# --- Weekly summary ---


class MerchantTotal(BaseModel):
    merchant: str
    spent: Decimal


class CurrencyWeek(BaseModel):
    """One currency's week. Every number is worked out in code before the LLM
    sees it; the LLM only puts them into sentences."""

    currency: Currency
    spent: Decimal
    # The same days of the week before (Mon-Wed vs Mon-Wed while a week is in
    # progress). None in your first week, when there's nothing to compare with.
    previous: Decimal | None
    change: Decimal | None  # spent - previous
    # None if there's no previous, it was 0, or the rise is over 100% (noise).
    change_pct: int | None
    # The budget of the month whose list this is (a week crossing two months
    # shows a different share in each list). None if that currency has no budget.
    budget: Decimal | None
    budget_share_pct: int | None
    top_merchants: list[MerchantTotal]


class WeekFacts(BaseModel):
    week_start: datetime.date  # always a Monday
    week_end: datetime.date  # always a Sunday
    in_progress: bool
    days_counted: int  # 7, or the days so far (Mon..today) for this week
    # What "previous" covers, in words written by code ("the same 2 days last
    # week") for the card to show as-is. None in your first week.
    compared_with: str | None
    currencies: list[CurrencyWeek]


class WeekSummary(WeekFacts):
    # A saved sentence that still matches these numbers, else None: the list
    # never calls the AI. Tapping the card streams one (insights.weekly_summary).
    summary: str | None


class WeeklyInsights(BaseModel):
    month: str
    weeks: list[WeekSummary]  # newest first


SUMMARY_MAX_CHARS = 160


class SummaryReply(BaseModel):
    """The finished, streamed sentence, checked before it's saved."""

    # The prompt asks for one short sentence; this guarantees it. The stream
    # is also cut off past this length, so nothing longer is ever shown.
    summary: Annotated[str, Field(min_length=1, max_length=SUMMARY_MAX_CHARS)]


# --- Ask a question ---


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: Annotated[str, Field(min_length=1, max_length=300)]
    # Set when you tapped GBP or MYR after "which currency?"; code then forces
    # it into every tool call.
    currency: Currency | None = None


class AskResponse(BaseModel):
    # None when the AI's sentence failed the checks: the numbers still show.
    answer: str | None
    # Set instead of an answer when both currencies were used: show buttons.
    needs_currency: list[Currency] | None
    # The tool results the answer was built from, for the numbers on screen.
    facts: list[dict[str, Any]]


# --- Spending trend (Insights graphs) ---


class TrendMonth(BaseModel):
    month: str  # "2026-10"
    # None for a month that hasn't started yet: drawn as no line, not £0.
    total: Decimal | None
    by_category: dict[Category, Decimal]
    # That month's own budget, else your usual one, else None (no line).
    budget: Decimal | None


class CurrencyTrend(BaseModel):
    currency: Currency
    months: list[TrendMonth]  # oldest first


class SpendingTrend(BaseModel):
    month: str  # the last month shown
    currencies: list[CurrencyTrend]  # GBP and MYR, never mixed


# --- Budget pace: this month's spending, day by day, against an even pace ------------


class PaceDay(BaseModel):
    date: datetime.date
    # Everything spent from the 1st up to and including this day. None for a day
    # that hasn't come yet: drawn as no point, not as a flat line.
    spent: Decimal | None
    # Where you'd be if the budget were spread evenly: budget x day / days in the
    # month. None when this currency has no budget.
    on_pace: Decimal | None


class CurrencyPace(BaseModel):
    currency: Currency
    budget: Decimal | None
    days: list[PaceDay]  # every day of the month, 1st first


class BudgetPace(BaseModel):
    month: str
    currencies: list[CurrencyPace]  # GBP and MYR, never mixed


# --- Changes vs usual: each category this month against your recent average ----------


class CategoryChange(BaseModel):
    category: Category
    now: Decimal  # this month (up to the same day, while it's in progress)
    usual: Decimal  # the average of the months compared, over the same days
    change: Decimal  # now - usual: positive = spending more than usual


class CurrencyChanges(BaseModel):
    currency: Currency
    changes: list[CategoryChange]  # biggest change first, up or down


class CategoryChanges(BaseModel):
    month: str
    # The months averaged into "usual" ("2026-10", ...): up to 3, and only from your
    # first expense on, so empty months before you started don't drag it down.
    # Empty = no history yet, nothing to compare.
    compared_months: list[str]
    # While the month is in progress, only days 1..this are compared in every month
    # (a fair "by this point"). None = whole months.
    up_to_day: int | None
    currencies: list[CurrencyChanges]
