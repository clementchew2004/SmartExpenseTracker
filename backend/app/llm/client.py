import logging
import time
from collections.abc import Callable
from functools import lru_cache

import openai
from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]  # wait before retry 1, 2 and 3

# Temporary problems: the same request may work if we wait and try again.
RETRYABLE_ERRORS = (
    openai.RateLimitError,  # 429
    openai.InternalServerError,  # 500, 503, ...
    openai.APIConnectionError,  # timeout or dropped connection
)


class LLMError(Exception):
    """The LLM call failed and retrying won't help."""


class LLMClient:
    def __init__(
        self,
        sdk: OpenAI,
        model: str,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.sdk = sdk
        self.model = model
        self.sleep = sleep

    def complete(self, system_prompt: str, user_message: str) -> str:
        """Send one prompt and return the model's reply, which must be JSON.

        JSON mode requires the word "JSON" to appear in the prompt.
        """
        started = time.perf_counter()  # includes any retries and backoff waits
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.sdk.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,  # consistent answers: extraction, not creativity
                )
            except RETRYABLE_ERRORS as e:
                if attempt == MAX_RETRIES:
                    raise LLMError(
                        f"OpenAI still failing after {MAX_RETRIES} retries: {e}"
                    ) from e
                wait = BACKOFF_SECONDS[attempt]
                logger.warning(
                    "LLM call failed (%s), retrying in %ss", type(e).__name__, wait
                )
                self.sleep(wait)
                continue
            except openai.AuthenticationError as e:  # 401
                raise LLMError(
                    "OpenAI rejected the API key - check OPENAI_API_KEY in .env"
                ) from e
            except openai.APIStatusError as e:  # 400 and other request problems
                raise LLMError(
                    f"OpenAI rejected the request ({e.status_code}): {e.message}"
                ) from e

            usage = response.usage
            if usage is not None:
                logger.info(
                    "LLM call model=%s input_tokens=%s output_tokens=%s "
                    "attempts=%s duration_ms=%d",
                    self.model,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    attempt + 1,
                    (time.perf_counter() - started) * 1000,
                )
            return response.choices[0].message.content or ""

        raise AssertionError("unreachable")


@lru_cache
def get_llm_client() -> LLMClient:
    settings = get_settings()
    sdk = OpenAI(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        timeout=TIMEOUT_SECONDS,
        max_retries=0,  # our retry loop above is the only one
    )
    return LLMClient(sdk, settings.OPENAI_MODEL)
