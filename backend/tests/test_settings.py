import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models import Expense, InviteCode, RefreshToken, User

PASSWORD = "correct horse"  # the password conftest gives every test user


def login(email="me@example.com", password=PASSWORD) -> TestClient:
    """A separate "device": its own cookie jar, logged in for real."""
    device = TestClient(app)
    response = device.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200, response.text
    device.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return device


def refreshes(device: TestClient) -> bool:
    return device.post("/auth/refresh").status_code == 200


# --- Default currency -----------------------------------------------------------------


def test_change_default_currency(client):
    response = client.patch("/auth/me", json={"default_currency": "MYR"})

    assert response.status_code == 200
    assert response.json()["default_currency"] == "MYR"
    assert client.get("/auth/me").json()["default_currency"] == "MYR"


def test_saved_expenses_keep_their_currency(client, make_expense):
    make_expense(amount="4.50", currency="GBP")

    client.patch("/auth/me", json={"default_currency": "MYR"})

    assert client.get("/expenses").json()[0]["currency"] == "GBP"


@pytest.mark.parametrize(
    "body",
    [{"default_currency": "USD"}, {}, {"default_currency": "MYR", "email": "x@y.z"}],
    ids=["unknown-currency", "missing", "cannot-change-email"],
)
def test_change_default_currency_rejects_bad_input(client, body):
    assert client.patch("/auth/me", json=body).status_code == 422


# --- Change password ----------------------------------------------------------------


def test_change_password(make_user):
    make_user()
    phone = login()

    response = phone.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a brand new one"},
    )

    assert response.status_code == 200
    assert login(password="a brand new one")  # the new one works
    old = TestClient(app).post(
        "/auth/login", data={"username": "me@example.com", "password": PASSWORD}
    )
    assert old.status_code == 401  # the old one doesn't


def test_other_devices_are_logged_out_but_this_one_stays(make_user):
    make_user()
    laptop = login()
    phone = login()

    phone.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a brand new one"},
    )

    assert not refreshes(laptop)  # e.g. whoever had the leaked password
    assert refreshes(phone)  # you, still logged in


def test_wrong_current_password_changes_nothing(make_user):
    make_user()
    phone = login()

    response = phone.post(
        "/auth/change-password",
        json={"current_password": "not it", "new_password": "a brand new one"},
    )

    assert response.status_code == 400
    assert "current password" in response.json()["detail"]
    assert login()  # the original still works
    assert refreshes(phone)


@pytest.mark.parametrize(
    "body",
    [
        {"current_password": PASSWORD, "new_password": "short"},
        {"current_password": PASSWORD, "new_password": "x" * 129},
        {"current_password": PASSWORD},
    ],
    ids=["too-short", "too-long", "missing"],
)
def test_new_password_follows_the_register_rules(client, body):
    assert client.post("/auth/change-password", json=body).status_code == 422


# --- Export -------------------------------------------------------------------------


def read_csv(response):
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    return list(csv.reader(io.StringIO(response.text.lstrip("﻿"))))


def test_export_lists_my_expenses_oldest_first(client, make_expense):
    make_expense(amount="12.50", date="2026-11-04", merchant="Pret", note="lunch")
    make_expense(amount="4.50", date="2026-10-01", merchant="Chatime")

    rows = read_csv(client.get("/expenses/export.csv"))

    assert rows[0] == [
        "date",
        "amount",
        "currency",
        "merchant",
        "category",
        "note",
        "source",
    ]
    assert rows[1] == ["2026-10-01", "4.50", "GBP", "Chatime", "Food", "", "manual"]
    assert rows[2] == ["2026-11-04", "12.50", "GBP", "Pret", "Food", "lunch", "manual"]


@pytest.mark.parametrize("text", ['=HYPERLINK("http://evil")', "+1", "-1", "@SUM(A1)"])
def test_export_makes_formula_like_text_plain(client, make_expense, text):
    make_expense(merchant=text, note=text)

    row = read_csv(client.get("/expenses/export.csv"))[1]

    assert row[3] == "'" + text
    assert row[5] == "'" + text


def test_export_never_includes_another_users_expenses(
    client, make_user, client_for, make_expense
):
    make_expense(merchant="Mine")
    other = client_for(make_user("other@example.com"))

    assert read_csv(other.get("/expenses/export.csv")) == [
        ["date", "amount", "currency", "merchant", "category", "note", "source"]
    ]


# --- Delete account -----------------------------------------------------------------


def test_delete_needs_the_word_delete(client):
    for body in [{}, {"confirm": "delete"}, {"confirm": "yes"}]:
        assert client.request("DELETE", "/auth/me", json=body).status_code == 422
    assert client.get("/auth/me").status_code == 200  # still here


def test_delete_removes_everything_of_mine_and_nothing_else(
    anon_client, make_invite, make_user, client_for, db_session
):
    # Register for real, so there's an invite code and a login session too.
    code = make_invite()
    anon_client.post(
        "/auth/register",
        json={
            "email": "me@example.com",
            "password": PASSWORD,
            "invite_code": code,
            "default_currency": "GBP",
        },
    )
    me = login()
    me.post(
        "/expenses",
        json={
            "amount": "4.50",
            "currency": "GBP",
            "date": "2026-11-01",
            "merchant": "Mine",
            "category": "Food",
        },
    )
    me.put("/budgets/default/GBP", json={"amount": "750"})
    other = client_for(make_user("other@example.com"))
    other.post(
        "/expenses",
        json={
            "amount": "9.00",
            "currency": "GBP",
            "date": "2026-11-01",
            "merchant": "Theirs",
            "category": "Food",
        },
    )

    assert db_session.scalar(
        select(InviteCode).where(InviteCode.code == code)
    ).used_by_user_id

    response = me.request("DELETE", "/auth/me", json={"confirm": "DELETE"})

    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.scalar(select(User).where(User.email == "me@example.com")) is None
    assert db_session.scalar(select(func.count()).select_from(RefreshToken)) == 0
    assert db_session.scalars(select(Expense.merchant)).all() == ["Theirs"]
    assert me.get("/expenses").status_code == 401  # the old access token is dead
    # The invite is gone, not just unlinked: it can't be used again.
    assert db_session.scalar(select(InviteCode).where(InviteCode.code == code)) is None
    again = anon_client.post(
        "/auth/register",
        json={
            "email": "new@example.com",
            "password": PASSWORD,
            "invite_code": code,
            "default_currency": "GBP",
        },
    )
    assert again.status_code != 201


def test_settings_routes_need_login(anon_client):
    assert (
        anon_client.patch("/auth/me", json={"default_currency": "MYR"}).status_code
        == 401
    )
    assert (
        anon_client.post(
            "/auth/change-password",
            json={"current_password": PASSWORD, "new_password": "a brand new one"},
        ).status_code
        == 401
    )
    assert anon_client.get("/expenses/export.csv").status_code == 401
    assert (
        anon_client.request(
            "DELETE", "/auth/me", json={"confirm": "DELETE"}
        ).status_code
        == 401
    )
