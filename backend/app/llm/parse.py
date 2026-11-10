import datetime
from collections.abc import Callable

from pydantic import BaseModel, ValidationError

from app.llm.client import LLMClient
from app.llm.dates import resolve_weekday
from app.llm.prompts import (
    DEFAULT_CURRENCY,
    build_parse_prompt,
    build_receipt_prompt,
)
from app.schemas import Currency, ParsedExpense, ParseResult, ReceiptReply

MAX_EXPENSES = 10


# --- Model problems: the reply was unusable even after a retry. ---


class ExpenseParseError(Exception):
    """The LLM's reply couldn't be turned into valid expenses."""


# --- User problems: the text can't become an expense as written. No retry. ---


class UserInputError(Exception):
    """Only the user can fix this, by changing what they typed."""


class NotAnExpenseError(UserInputError):
    pass


class MissingAmountError(UserInputError):
    pass


class InvalidAmountError(UserInputError):
    pass


class TooManyExpensesError(UserInputError):
    pass


class NotAReceiptError(UserInputError):
    pass


def parse_expense_text(
    text: str,
    llm: LLMClient,
    today: datetime.date,
    default_currency: Currency = DEFAULT_CURRENCY,
) -> list[ParsedExpense]:
    result = ask_and_validate(
        lambda prompt: llm.complete(prompt, text),
        build_parse_prompt(today, default_currency),
        ParseResult,
        "Couldn't understand that expense - try rephrasing it",
    )

    # Weekday dates are arithmetic, so code works them out, not the model.
    for expense in result.expenses:
        resolved = resolve_weekday(expense.date_text, today)
        if resolved is not None:
            expense.date = resolved

    # The model did its job; now check what it found in the user's text.
    check_user_input(result.expenses)
    return result.expenses


def parse_receipt(
    jpeg: bytes,
    llm: LLMClient,
    today: datetime.date,
    default_currency: Currency = DEFAULT_CURRENCY,
) -> list[ParsedExpense]:
    """Read a receipt photo (already checked by images.prepare_receipt).

    Unlike text, a missing total isn't an error: like a passport scanner,
    the card shows what was read and you fill in the amount box yourself.
    """
    result = ask_and_validate(
        lambda prompt: llm.complete_with_image(prompt, jpeg),
        build_receipt_prompt(today, default_currency),
        ReceiptReply,
        "Couldn't read that receipt - try another photo or type it instead",
    )

    if not result.expenses:
        raise NotAReceiptError(
            "That doesn't look like a receipt - try a clear photo of the whole receipt"
        )
    expense = result.expenses[0]
    if expense.amount is not None and expense.amount <= 0:
        raise InvalidAmountError(
            f"The total on that receipt is {expense.amount} - "
            "amounts must be more than 0 (refunds aren't supported yet)"
        )
    return result.expenses


def ask_and_validate[Reply: BaseModel](
    ask: Callable[[str], str],
    system_prompt: str,
    reply_model: type[Reply],
    failure_message: str,
) -> Reply:
    """Call the model and validate its JSON. On a model mistake, retry once,
    telling it exactly what was wrong; after that, give up cleanly."""
    try:
        return reply_model.model_validate_json(ask(system_prompt))
    except ValidationError as first_error:
        retry_prompt = system_prompt + rejection_note(first_error)
        try:
            return reply_model.model_validate_json(ask(retry_prompt))
        except ValidationError as second_error:
            raise ExpenseParseError(failure_message) from second_error


def check_user_input(expenses: list[ParsedExpense]) -> None:
    if not expenses:
        raise NotAnExpenseError(
            "That doesn't look like an expense - try something like '4.50 bubble tea'"
        )
    if len(expenses) > MAX_EXPENSES:
        raise TooManyExpensesError(
            f"Too many expenses in one message - enter at most {MAX_EXPENSES}"
        )
    for expense in expenses:
        if expense.amount is None:
            raise MissingAmountError(
                f"No amount found for '{expense.merchant}' - "
                "include how much you spent, e.g. 4.50"
            )
        if expense.amount <= 0:
            raise InvalidAmountError(
                f"'{expense.merchant}' has an amount of {expense.amount} - "
                "amounts must be more than 0 (refunds aren't supported yet)"
            )


def rejection_note(error: ValidationError) -> str:
    problems = "\n".join(
        f"- {'.'.join(str(part) for part in e['loc']) or 'reply'}: {e['msg']} "
        f"(you sent {str(e['input'])[:100]!r})"
        for e in error.errors()
    )
    return (
        f"\n\nYour previous reply was rejected:\n{problems}\n"
        "Reply again with corrected JSON."
    )
