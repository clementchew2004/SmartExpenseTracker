import datetime
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.llm.client import LLMClient, LLMError, get_llm_client
from app.llm.parse import ExpenseParseError, MissingAmountError, parse_expense_text
from app.schemas import ParsedExpense, ParseTextRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/parse", tags=["parse"])

LLM = Annotated[LLMClient, Depends(get_llm_client)]


@router.post("/text")
def parse_text(body: ParseTextRequest, llm: LLM) -> ParsedExpense:
    """Turn a sentence into an expense for the user to review. Saves nothing."""
    try:
        return parse_expense_text(body.text, llm, datetime.date.today())
    # MissingAmountError first: it's a kind of ExpenseParseError.
    except MissingAmountError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        ) from e
    except ExpenseParseError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
        ) from e
    except LLMError as e:
        logger.error("LLM call failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service is unavailable right now - try again shortly",
        ) from e
