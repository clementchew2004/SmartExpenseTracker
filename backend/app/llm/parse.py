import datetime

from pydantic import ValidationError

from app.llm.client import LLMClient
from app.llm.prompts import DEFAULT_CURRENCY, build_parse_prompt
from app.schemas import Currency, ParsedExpense


class ExpenseParseError(Exception):
    """The LLM's reply couldn't be turned into a valid expense."""


class MissingAmountError(ExpenseParseError):
    """The user's text doesn't mention an amount, so they need to add one."""


def parse_expense_text(
    text: str,
    llm: LLMClient,
    today: datetime.date,
    default_currency: Currency = DEFAULT_CURRENCY,
) -> ParsedExpense:
    system_prompt = build_parse_prompt(today, default_currency)

    reply = llm.complete(system_prompt, text)
    try:
        parsed = ParsedExpense.model_validate_json(reply)
    except ValidationError as first_error:
        # The model made a mistake: retry once, telling it exactly what was wrong.
        reply = llm.complete(system_prompt + rejection_note(first_error), text)
        try:
            parsed = ParsedExpense.model_validate_json(reply)
        except ValidationError as second_error:
            raise ExpenseParseError(
                "Couldn't understand that expense - try rephrasing it"
            ) from second_error

    # The model did its job but the text has no amount: only the user can fix that.
    if parsed.amount is None:
        raise MissingAmountError(
            "No amount found - include how much you spent, e.g. 4.50"
        )
    return parsed


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
