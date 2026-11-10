"""Turn a week's finished numbers into a few friendly sentences.

The LLM only phrases: it's handed numbers that code already worked out
(services/weekly.py) and told to copy them, never to calculate.
"""

import logging

from app.llm.client import LLMClient, LLMError
from app.llm.parse import ExpenseParseError, ask_and_validate
from app.llm.prompts import WEEKLY_SUMMARY_PROMPT
from app.schemas import SummaryReply, WeekFacts

logger = logging.getLogger(__name__)

NO_SPENDING = "No spending this week."


def write_summary(facts: WeekFacts, llm: LLMClient) -> str | None:
    """The summary text, or None if the AI couldn't write one right now.

    A failed summary isn't worth failing the whole page for: the numbers still
    show, and it's tried again next time the page opens.
    """
    try:
        reply = ask_and_validate(
            lambda prompt: llm.complete(prompt, facts.model_dump_json()),
            WEEKLY_SUMMARY_PROMPT,
            SummaryReply,
            "Couldn't write a summary",
        )
    except (ExpenseParseError, LLMError) as e:
        logger.warning("Weekly summary for %s failed: %s", facts.week_start, e)
        return None
    return reply.summary.strip()
