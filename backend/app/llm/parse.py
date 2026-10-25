import datetime

from pydantic import ValidationError

from app.llm.client import LLMClient
from app.llm.dates import resolve_weekday
from app.llm.prompts import DEFAULT_CURRENCY, build_parse_prompt
from app.schemas import Currency, ParsedExpense, ParseResult

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


def parse_expense_text(
    text: str,
    llm: LLMClient,
    today: datetime.date,
    default_currency: Currency = DEFAULT_CURRENCY,
) -> list[ParsedExpense]:
    system_prompt = build_parse_prompt(today, default_currency)

    reply = llm.complete(system_prompt, text)
    try:
        result = ParseResult.model_validate_json(reply)
    except ValidationError as first_error:
        # The model made a mistake: retry once, telling it exactly what was wrong.
        reply = llm.complete(system_prompt + rejection_note(first_error), text)
        try:
            result = ParseResult.model_validate_json(reply)
        except ValidationError as second_error:
            raise ExpenseParseError(
                "Couldn't understand that expense - try rephrasing it"
            ) from second_error

    # Weekday dates are arithmetic, so code works them out, not the model.
    for expense in result.expenses:
        resolved = resolve_weekday(expense.date_text, today)
        if resolved is not None:
            expense.date = resolved

    # The model did its job; now check what it found in the user's text.
    check_user_input(result.expenses)
    return result.expenses


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
