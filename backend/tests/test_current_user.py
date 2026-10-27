import datetime

import jwt
import pytest

from app.auth import JWT_ALGORITHM, create_access_token, utcnow
from app.config import get_settings
from app.llm.client import get_llm_client
from app.main import app

PROTECTED = [
    ("GET", "/expenses"),
    ("POST", "/expenses"),
    ("GET", "/expenses/1"),
    ("PATCH", "/expenses/1"),
    ("DELETE", "/expenses/1"),
    ("GET", "/stats/monthly?month=2026-10"),
    ("POST", "/parse/text"),
]


def expired_token(user_id: int) -> str:
    past = utcnow() - datetime.timedelta(minutes=1)
    return jwt.encode(
        {"sub": str(user_id), "iat": past, "exp": past},
        get_settings().JWT_SECRET_KEY.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def assert_not_logged_in(response):
    assert response.status_code == 401
    assert response.json() == {"detail": "Not logged in"}
    assert response.headers["www-authenticate"] == "Bearer"


# --- Every way of not being logged in gets the same 401 ----------------------


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_every_protected_route_needs_a_token(anon_client, method, path):
    response = anon_client.request(method, path)

    assert_not_logged_in(response)


def test_a_junk_token_is_refused(anon_client):
    response = anon_client.get(
        "/expenses", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert_not_logged_in(response)


def test_a_tampered_token_is_refused(anon_client, make_user):
    me = make_user()
    header, payload, signature = create_access_token(me.id).split(".")
    flipped = signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")

    response = anon_client.get(
        "/expenses", headers={"Authorization": f"Bearer {header}.{payload}.{flipped}"}
    )

    assert_not_logged_in(response)


def test_an_expired_token_is_refused(anon_client, make_user):
    me = make_user()

    response = anon_client.get(
        "/expenses", headers={"Authorization": f"Bearer {expired_token(me.id)}"}
    )

    assert_not_logged_in(response)


def test_a_valid_token_for_a_deleted_account_is_refused(
    make_user, client_for, db_session
):
    me = make_user()
    client = client_for(me)  # token signed while the account existed
    db_session.delete(me)
    db_session.commit()

    assert_not_logged_in(client.get("/expenses"))


def test_open_routes_need_no_token(anon_client):
    assert anon_client.get("/health").status_code == 200
    # /auth routes can't need an access token: they're how you get one.
    assert anon_client.post("/auth/refresh").json()["detail"] == "Not logged in"


def test_me_returns_the_logged_in_user(client):
    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "email": "me@example.com",
        "default_currency": "GBP",
    }


def test_me_needs_a_token(anon_client):
    assert_not_logged_in(anon_client.get("/auth/me"))


# --- User A can never see or touch user B's expenses ------------------------


@pytest.fixture
def a_and_b(make_user, client_for):
    """Two logged-in clients; B owns one expense."""
    a = client_for(make_user("a@example.com"))
    b = client_for(make_user("b@example.com"))
    created = b.post(
        "/expenses",
        json={
            "amount": "9.99",
            "currency": "GBP",
            "date": "2026-10-15",
            "merchant": "B's lunch",
            "category": "Food",
        },
    )
    assert created.status_code == 201
    return a, b, created.json()["id"]


def test_a_does_not_see_bs_expenses_in_the_list(a_and_b):
    a, b, _ = a_and_b

    assert a.get("/expenses").json() == []
    assert len(b.get("/expenses").json()) == 1


def test_a_cannot_read_bs_expense(a_and_b):
    a, _, b_expense = a_and_b

    response = a.get(f"/expenses/{b_expense}")

    # The same 404 as a made-up id: A can't even tell that it exists.
    assert response.status_code == 404
    assert a.get("/expenses/99999").json() == response.json()


def test_a_cannot_edit_bs_expense(a_and_b):
    a, b, b_expense = a_and_b

    response = a.patch(f"/expenses/{b_expense}", json={"amount": "0.01"})

    assert response.status_code == 404
    assert b.get(f"/expenses/{b_expense}").json()["amount"] == "9.99"


def test_a_cannot_delete_bs_expense(a_and_b):
    a, b, b_expense = a_and_b

    response = a.delete(f"/expenses/{b_expense}")

    assert response.status_code == 404
    assert b.get(f"/expenses/{b_expense}").status_code == 200


def test_stats_only_count_your_own_expenses(a_and_b):
    a, b, _ = a_and_b

    a_stats = a.get("/stats/monthly", params={"month": "2026-10"}).json()
    b_stats = b.get("/stats/monthly", params={"month": "2026-10"}).json()

    assert a_stats["totals"] == {}
    assert a_stats["currency_totals"] == {}
    assert b_stats["currency_totals"] == {"GBP": "9.99"}


def test_new_expenses_belong_to_the_caller_not_the_body(a_and_b):
    a, b, _ = a_and_b

    # A field for the owner is refused outright (extra="forbid"), so a client
    # can't save an expense into someone else's account.
    response = a.post(
        "/expenses",
        json={
            "amount": "1.00",
            "currency": "GBP",
            "date": "2026-10-15",
            "merchant": "Sneaky",
            "category": "Food",
            "user_id": 2,
        },
    )

    assert response.status_code == 422
    assert len(b.get("/expenses").json()) == 1


# --- Parsing uses the caller's own default currency --------------------------


class PromptSpy:
    """A fake LLM that records the system prompt it was given."""

    def complete(self, system_prompt, user_message):
        self.system_prompt = system_prompt
        return (
            '{"expenses": [{"amount": "12.00", "currency": "MYR", '
            '"date": "2026-10-27", "merchant": "Nasi lemak", "category": "Food"}]}'
        )


def test_parse_uses_the_users_default_currency(make_user, client_for):
    client = client_for(make_user(currency="MYR"))
    spy = PromptSpy()
    app.dependency_overrides[get_llm_client] = lambda: spy
    try:
        response = client.post("/parse/text", json={"text": "12 nasi lemak"})
    finally:
        app.dependency_overrides.pop(get_llm_client, None)

    assert response.status_code == 200
    assert 'use "MYR", even if' in spy.system_prompt
