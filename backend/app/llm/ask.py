"""The agent loop behind POST /insights/ask.

Each lap: send the conversation so far plus the tool descriptions. The AI
replies either with tool calls - code checks and runs them, adds the results,
and goes round again - or with text, which is the answer. Code stays in
charge throughout:
- at most MAX_TOOL_CALLS tool calls, then one last lap with tools switched off;
- a bad call's error goes back to the AI to fix (that still counts);
- "which currency?" stops the loop at once: the browser shows GBP/MYR buttons;
- every £/RM amount and % in the answer must come from a tool result, so the
  AI can't invent or calculate one (retry once, then numbers only).
"""

import datetime
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.prompts import build_ask_prompt
from app.llm.tools import ToolError, run_tool, tool_schemas
from app.schemas import AskResponse, Currency

MAX_TOOL_CALLS = 5
MAX_ANSWER_CHARS = 600

MONEY = re.compile(r"(?:£|RM\s?)(-?\d[\d,]*(?:\.\d+)?)")
PERCENT = re.compile(r"(-?\d+(?:\.\d+)?)\s?%")
MONEY_VALUE = re.compile(r"^-?\d+\.\d{2}$")


def answer_question(
    question: str,
    llm: LLMClient,
    db: Session,
    user_id: int,
    today: datetime.date,
    default_currency: Currency,
    currency: Currency | None = None,
) -> AskResponse:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_ask_prompt(today)},
        {"role": "user", "content": question},
    ]
    if currency is not None:
        messages.append({"role": "system", "content": f"The user chose {currency}."})
    tools = tool_schemas()
    facts: list[dict[str, Any]] = []
    calls = 0

    while True:
        out_of_calls = calls >= MAX_TOOL_CALLS
        reply = llm.chat(
            messages, tools, tool_choice="none" if out_of_calls else "auto"
        )
        if not reply.tool_calls or out_of_calls:
            break  # text, not tool calls: that's the answer

        messages.append(
            {
                "role": "assistant",
                "content": reply.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in reply.tool_calls
                ],
            }
        )
        for call in reply.tool_calls:
            # Every call needs a reply message, even ones past the limit.
            if calls >= MAX_TOOL_CALLS:
                result: dict[str, Any] = {"error": "Tool call limit reached"}
            else:
                calls += 1
                try:
                    result = run_tool(
                        call.function.name,
                        call.function.arguments,
                        db,
                        user_id,  # from the login, never from the AI
                        today,
                        default_currency,
                        currency,
                    )
                except ToolError as e:
                    result = {"error": str(e)}  # back to the AI to fix
                else:
                    if "needs_currency" in result:
                        # Stop here: the browser asks with buttons, then
                        # sends the same question again with the currency.
                        return AskResponse(
                            answer=None,
                            needs_currency=result["needs_currency"],
                            facts=[],
                        )
                    facts.append({"tool": call.function.name, **result})
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
            )

    answer = checked(reply.content, facts)
    if answer is None:
        # One retry, saying exactly what was wrong, with tools switched off.
        made_up = sorted(invented_amounts(reply.content or "", facts))
        messages.append({"role": "assistant", "content": reply.content or ""})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Your answer used amounts that aren't in the tool results: "
                    f"{', '.join(made_up) or 'none'}. Rewrite it in 1 to 3 short "
                    "sentences using only amounts from the tool results, "
                    "without calculating anything. For a difference or a "
                    "percentage, use difference_a_minus_b and change_pct_a_vs_b "
                    "from compare; if there's no compare result, leave them out."
                ),
            }
        )
        retry = llm.chat(messages, tools, tool_choice="none")
        answer = checked(retry.content, facts)

    # Still no good: show the numbers alone rather than a wrong sentence.
    return AskResponse(answer=answer, needs_currency=None, facts=facts)


def checked(text: str | None, facts: list[dict[str, Any]]) -> str | None:
    """The answer, if it's non-empty, short enough and invents no numbers."""
    text = (text or "").strip()
    if not text or len(text) > MAX_ANSWER_CHARS or invented_amounts(text, facts):
        return None
    return text


def invented_amounts(text: str, facts: list[dict[str, Any]]) -> set[str]:
    """£/RM amounts and percentages in the text that no tool returned."""
    money, percents = allowed_numbers(facts)
    bad = set()
    for match in MONEY.finditer(text):
        if as_decimal(match.group(1)) not in money:
            bad.add(match.group(0))
    for match in PERCENT.finditer(text):
        if as_decimal(match.group(1)) not in percents:
            bad.add(match.group(0))
    return bad


def allowed_numbers(facts: Any) -> tuple[set[Decimal], set[Decimal]]:
    """Every amount and percentage the tools returned, without their signs
    ("£23.40 less" is fine when the difference was -23.40)."""
    money: set[Decimal] = set()
    percents: set[Decimal] = set()

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for v in value:
                walk(v, key)
        elif isinstance(value, str) and MONEY_VALUE.match(value):
            money.add(abs(Decimal(value)))
        elif isinstance(value, int) and "pct" in key:
            percents.add(abs(Decimal(value)))

    walk(facts)
    return money, percents


def as_decimal(text: str) -> Decimal | None:
    try:
        return abs(Decimal(text.replace(",", "")))
    except InvalidOperation:
        return None
