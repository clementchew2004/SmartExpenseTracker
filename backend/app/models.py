import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stored lowercase so "Me@x.com" and "me@x.com" are the same account.
    email: Mapped[str] = mapped_column(String(254), unique=True)
    # An Argon2 hash, never the password itself.
    hashed_password: Mapped[str] = mapped_column(String(255))
    default_currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InviteCode(Base):
    """A one-use code needed to register. Empty used_* = still available."""

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    used_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    """One refresh token. Only its hash is stored, like a password."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # 30 days after LOGIN; rotation copies this forward rather than extending it.
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Every expense has an owner; routes set it from the logged-in user.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    date: Mapped[datetime.date]
    merchant: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None]
    raw_input: Mapped[str | None]
    source: Mapped[str] = mapped_column(String(10), default="manual")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DefaultBudget(Base):
    """Your usual monthly budget in one currency; used for any month without its own."""

    __tablename__ = "default_budgets"
    # One default per currency: a second GBP default is refused by the database.
    __table_args__ = (
        UniqueConstraint(
            "user_id", "currency", name="uq_default_budgets_user_currency"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Budget(Base):
    """One month's own budget in one currency; replaces the default for that month."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "month", "currency", name="uq_budgets_user_month_currency"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Always the 1st of the month (2026-10-01 = October 2026), so it's a real date
    # that SQL can compare, not a "2026-10" string.
    month: Mapped[datetime.date]
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class RepeatingExpense(Base):
    """An expense that comes back (rent, a subscription). It never saves itself:
    each due date becomes a reminder card you Save or Skip."""

    __tablename__ = "repeating_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # What each saved copy will look like (you can still edit it on the card).
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    merchant: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None]
    frequency: Mapped[str] = mapped_column(String(7))  # daily | weekly | monthly
    # The day it was set up on, e.g. 31. Monthly dates use the month's last day
    # when it's shorter (28 Feb), then go back to the 31st in March.
    day_of_month: Mapped[int]
    # The oldest date not yet saved or skipped: everything before it is handled.
    next_due: Mapped[datetime.date]
    end_date: Mapped[datetime.date | None]  # empty = until you stop it
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WeeklySummary(Base):
    """An AI-written summary of one week, kept with the numbers it was written
    from. Opening the app recomputes the numbers (cheap SQL); only if they
    changed is the (paid) LLM asked again."""

    __tablename__ = "weekly_summaries"
    # Per month too: a week crossing two months has a different budget share
    # in each month's list, so it gets a summary in each.
    __table_args__ = (
        UniqueConstraint(
            "user_id", "month", "week_start", name="uq_weekly_summaries_user_month_week"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    month: Mapped[datetime.date]  # always a 1st, like budgets
    week_start: Mapped[datetime.date]  # always a Monday
    facts: Mapped[dict] = mapped_column(JSON)
    text: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
