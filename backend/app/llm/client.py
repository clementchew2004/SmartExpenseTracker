import base64
import logging
import time
from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Any

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
        return self._send(system_prompt, user_message)

    def complete_with_image(self, system_prompt: str, jpeg: bytes) -> str:
        """Like complete(), but the user's message is a photo.

        The image travels inside the request as base64 text (a "data URL"),
        not as a link: our receipts aren't on the public internet for OpenAI
        to fetch, and shouldn't be.
        """
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        content = [
            {"type": "text", "text": "Here is the receipt."},
            # "high" detail reads small print; it costs more tokens than "low".
            {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
        ]
        return self._send(system_prompt, content)

    def stream(self, system_prompt: str, user_message: str) -> Iterator[str]:
        """Yield the model's reply piece by piece, as plain text (not JSON:
        half a JSON object can't be parsed, so it couldn't be shown).

        Opening the stream is retried like any call. Once text has been
        handed out it can't be taken back, so a failure after that isn't
        retried: it raises LLMError and the caller decides what to show.
        """
        started = time.perf_counter()
        chunks, attempts = self._create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            stream=True,
            # Ask for a last chunk with the token counts, for the cost log.
            stream_options={"include_usage": True},
        )
        try:
            for chunk in chunks:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                if chunk.usage is not None:
                    self._log_usage(chunk.usage, attempts, started)
        except openai.APIError as e:
            raise LLMError(f"OpenAI stream broke off: {e}") from e

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> Any:
        """One lap of the agent loop: send the conversation so far plus the
        tool descriptions, get back the AI's next message - either tool calls
        (`.tool_calls`) or a text answer (`.content`).

        tool_choice="none" makes it answer in text with what it already has.
        """
        started = time.perf_counter()
        response, attempts = self._create(
            messages=messages, tools=tools, tool_choice=tool_choice
        )
        if response.usage is not None:
            self._log_usage(response.usage, attempts, started)
        return response.choices[0].message

    def _send(self, system_prompt: str, user_content: str | list[dict]) -> str:
        started = time.perf_counter()  # includes any retries and backoff waits
        response, attempts = self._create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        if response.usage is not None:
            self._log_usage(response.usage, attempts, started)
        return response.choices[0].message.content or ""

    def _create(self, **request: Any) -> tuple[Any, int]:
        """One chat.completions call with retries on temporary errors.
        Returns the SDK's response (or stream) and how many attempts it took."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.sdk.chat.completions.create(
                    model=self.model,
                    temperature=0,  # consistent answers: extraction, not creativity
                    **request,
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
            return response, attempt + 1

        raise AssertionError("unreachable")

    def _log_usage(self, usage: Any, attempts: int, started: float) -> None:
        logger.info(
            "LLM call model=%s input_tokens=%s output_tokens=%s "
            "attempts=%s duration_ms=%d",
            self.model,
            usage.prompt_tokens,
            usage.completion_tokens,
            attempts,
            (time.perf_counter() - started) * 1000,
        )


@lru_cache
def get_llm_client() -> LLMClient:
    settings = get_settings()
    sdk = OpenAI(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        timeout=TIMEOUT_SECONDS,
        max_retries=0,  # our retry loop above is the only one
    )
    return LLMClient(sdk, settings.OPENAI_MODEL)
