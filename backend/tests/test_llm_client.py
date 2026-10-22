import logging
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.llm.client import LLMClient, LLMError, get_llm_client

# These tests never call the real OpenAI API: FakeSDK stands in for it.

REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def status_error(error_class, status_code):
    response = httpx.Response(status_code, request=REQUEST)
    return error_class("boom", response=response, body=None)


def ok_response(text='{"ok": true}'):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=5),
    )


class FakeSDK:
    """Pretends to be OpenAI(). Each call returns or raises the next scripted outcome."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_client(outcomes):
    sdk = FakeSDK(outcomes)
    waits = []
    client = LLMClient(sdk, "test-model", sleep=waits.append)
    return client, sdk, waits


def test_returns_reply_on_first_try():
    client, sdk, waits = make_client([ok_response('{"amount": "4.50"}')])

    reply = client.complete("Reply in JSON.", "4.50 bubble tea")

    assert reply == '{"amount": "4.50"}'
    assert len(sdk.calls) == 1
    assert waits == []
    sent = sdk.calls[0]
    assert sent["model"] == "test-model"
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["messages"][1] == {"role": "user", "content": "4.50 bubble tea"}


@pytest.mark.parametrize(
    "temporary_error",
    [
        status_error(openai.RateLimitError, 429),
        status_error(openai.InternalServerError, 500),
        status_error(openai.InternalServerError, 503),
        openai.APITimeoutError(request=REQUEST),
        openai.APIConnectionError(request=REQUEST),
    ],
)
def test_retries_temporary_errors(temporary_error):
    client, sdk, waits = make_client([temporary_error, ok_response()])

    reply = client.complete("Reply in JSON.", "hi")

    assert reply == '{"ok": true}'
    assert len(sdk.calls) == 2
    assert waits == [1]


def test_backs_off_then_gives_up_after_three_retries():
    errors = [status_error(openai.RateLimitError, 429) for _ in range(4)]
    client, sdk, waits = make_client(errors)

    with pytest.raises(LLMError, match="after 3 retries"):
        client.complete("Reply in JSON.", "hi")

    assert len(sdk.calls) == 4  # first try + 3 retries
    assert waits == [1, 2, 4]


def test_gives_up_immediately_on_bad_api_key():
    client, sdk, waits = make_client([status_error(openai.AuthenticationError, 401)])

    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        client.complete("Reply in JSON.", "hi")

    assert len(sdk.calls) == 1
    assert waits == []


def test_gives_up_immediately_on_bad_request():
    client, sdk, waits = make_client([status_error(openai.BadRequestError, 400)])

    with pytest.raises(LLMError, match="400"):
        client.complete("Reply in JSON.", "hi")

    assert len(sdk.calls) == 1
    assert waits == []


def test_logs_token_usage(caplog):
    client, _, _ = make_client([ok_response()])

    with caplog.at_level(logging.INFO, logger="app.llm.client"):
        client.complete("Reply in JSON.", "hi")

    assert "input_tokens=12 output_tokens=5" in caplog.text


def test_real_client_has_sdk_retries_turned_off():
    client = get_llm_client()

    assert client.sdk.max_retries == 0
    assert client.sdk.timeout == 30
