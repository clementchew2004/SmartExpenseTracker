import datetime
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.auth import CurrentUser
from app.llm.client import LLMClient, LLMError, get_llm_client
from app.llm.images import (
    MAX_UPLOAD_BYTES,
    ImageTooLargeError,
    UnsupportedImageError,
    prepare_receipt,
)
from app.llm.parse import (
    ExpenseParseError,
    UserInputError,
    parse_expense_text,
    parse_receipt,
)
from app.schemas import ParseResult, ParseTextRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/parse", tags=["parse"])

LLM = Annotated[LLMClient, Depends(get_llm_client)]


@contextmanager
def parse_errors_as_http() -> Iterator[None]:
    """Turn the parsing errors both routes share into HTTP responses."""
    try:
        yield
    except UserInputError as e:
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


@router.post("/text")
def parse_text(body: ParseTextRequest, llm: LLM, user: CurrentUser) -> ParseResult:
    """Turn a sentence into expenses for the user to review. Saves nothing."""
    with parse_errors_as_http():
        expenses = parse_expense_text(
            body.text, llm, datetime.date.today(), user.default_currency
        )
    return ParseResult(expenses=expenses)


@router.post("/receipt")
def parse_receipt_photo(
    receipt: UploadFile, llm: LLM, user: CurrentUser
) -> ParseResult:
    """Read a receipt photo into one expense for the user to review.

    Saves nothing, and the photo is never stored: it only lives in memory for
    this request.
    """
    # Read one byte past the limit: if it's there, the file is too big. The
    # declared type (receipt.content_type) is ignored - prepare_receipt checks
    # what the bytes really are.
    data = receipt.file.read(MAX_UPLOAD_BYTES + 1)
    try:
        jpeg = prepare_receipt(data)
    except ImageTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(e)
        ) from e
    except UnsupportedImageError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(e)
        ) from e

    with parse_errors_as_http():
        expenses = parse_receipt(
            jpeg, llm, datetime.date.today(), user.default_currency
        )
    return ParseResult(expenses=expenses)
