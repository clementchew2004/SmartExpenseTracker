"""Stream a week's one-sentence gist, checking it before it's saved.

The LLM only phrases: it's handed numbers that code already worked out
(services/weekly.py), and the prompt tells it to repeat none of them.

Streaming means the words are on screen before the reply is complete, so
"validate every LLM output" moves to where it protects the database:
- while streaming, the text is cut off past SUMMARY_MAX_CHARS;
- when it ends, the whole sentence is checked with SummaryReply;
- only a complete, valid sentence is handed to `save`.
"""

import json
import logging
from collections.abc import Callable, Iterator

from pydantic import ValidationError

from app.llm.client import LLMClient, LLMError
from app.llm.prompts import WEEKLY_SUMMARY_PROMPT
from app.schemas import SUMMARY_MAX_CHARS, SummaryReply, WeekFacts

logger = logging.getLogger(__name__)

NO_SPENDING = "No spending this week."
FAILED = "Couldn't write a summary right now"


def event(kind: str, text: str = "") -> str:
    """One Server-Sent Event. The payload is JSON so a sentence containing a
    newline can't break the "data: ..." line format."""
    return f"data: {json.dumps({'type': kind, 'text': text})}\n\n"


def saved_events(text: str) -> Iterator[str]:
    """An already-written sentence: all at once, no AI call."""
    yield event("text", text)
    yield event("done")


def summary_events(
    facts: WeekFacts, llm: LLMClient, save: Callable[[str], None]
) -> Iterator[str]:
    """Events for the browser: "text" pieces as the AI writes, then "done"
    (checked and saved) or "error" (nothing saved)."""
    pieces: list[str] = []
    length = 0
    try:
        for piece in llm.stream(WEEKLY_SUMMARY_PROMPT, facts.model_dump_json()):
            length += len(piece)
            if length > SUMMARY_MAX_CHARS:
                # Far longer than one short sentence: stop showing it.
                logger.warning("Weekly summary for %s ran too long", facts.week_start)
                yield event("error", FAILED)
                return
            pieces.append(piece)
            yield event("text", piece)
    except LLMError as e:
        logger.warning("Weekly summary for %s failed: %s", facts.week_start, e)
        yield event("error", FAILED)
        return

    try:
        reply = SummaryReply(summary="".join(pieces).strip())
    except ValidationError:
        yield event("error", FAILED)  # e.g. an empty reply
        return
    save(reply.summary)
    yield event("done")
