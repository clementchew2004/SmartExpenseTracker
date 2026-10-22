import json

import pytest

from app.llm.client import LLMError, get_llm_client
from app.main import app

# These tests never call the real OpenAI API: get_llm_client is overridden.

GOOD = {
    "amount": "4.50",
    "currency": "GBP",
    "date": "2026-10-21",
    "merchant": "Bubble tea",
    "category": "Food",
    "note": None,
}


class FakeLLM:
    """Pretends to be LLMClient. Each call returns (or raises) the next scripted item."""

    def __init__(self, replies):
        self.replies = list(replies)

    def complete(self, system_prompt, user_message):
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def use_llm(client):
    """Make POST /parse/text use a FakeLLM with the given replies."""

    def _use(*replies):
        fake = FakeLLM(replies)
        app.dependency_overrides[get_llm_client] = lambda: fake
        return fake

    yield _use
    app.dependency_overrides.pop(get_llm_client, None)


def test_returns_the_parsed_expense(client, use_llm):
    use_llm(json.dumps(GOOD))

    response = client.post("/parse/text", json={"text": "4.50 bubble tea yesterday"})

    assert response.status_code == 200
    assert response.json() == GOOD


def test_does_not_save_anything(client, use_llm):
    use_llm(json.dumps(GOOD))

    client.post("/parse/text", json={"text": "4.50 bubble tea yesterday"})

    assert client.get("/expenses").json() == []


def test_missing_amount_returns_422(client, use_llm):
    use_llm(json.dumps(GOOD | {"amount": None}))

    response = client.post("/parse/text", json={"text": "bubble tea yesterday"})

    assert response.status_code == 422
    assert "include how much you spent" in response.json()["detail"]


def test_unusable_model_reply_returns_502(client, use_llm):
    bad = json.dumps(GOOD | {"category": "Drinks"})
    use_llm(bad, bad)

    response = client.post("/parse/text", json={"text": "4.50 bubble tea"})

    assert response.status_code == 502
    assert "rephrasing" in response.json()["detail"]


def test_llm_failure_returns_502_without_leaking_details(client, use_llm):
    use_llm(LLMError("OpenAI rejected the API key - check OPENAI_API_KEY in .env"))

    response = client.post("/parse/text", json={"text": "4.50 bubble tea"})

    assert response.status_code == 502
    assert "OPENAI_API_KEY" not in response.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [{"text": ""}, {"text": "x" * 501}, {}, {"text": "4.50 tea", "extra": "no"}],
)
def test_invalid_request_body_returns_422(client, use_llm, body):
    use_llm()  # the LLM must not be called at all

    response = client.post("/parse/text", json=body)

    assert response.status_code == 422
