import datetime

import pytest
from sqlalchemy import select

from app.auth import decode_access_token, hash_refresh_token, utcnow
from app.models import InviteCode, RefreshToken, User


def register(
    anon_client, code, email="me@example.com", password="correct horse", currency="GBP"
):
    return anon_client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "invite_code": code,
            "default_currency": currency,
        },
    )


def login(anon_client, email="me@example.com", password="correct horse"):
    # OAuth2 password flow: a form, with the email in the "username" field.
    return anon_client.post(
        "/auth/login", data={"username": email, "password": password}
    )


@pytest.fixture
def user(anon_client, make_invite):
    response = register(anon_client, make_invite())
    assert response.status_code == 201, response.text
    return response.json()


# --- Register -----------------------------------------------------------------


def test_register_creates_user_and_uses_up_the_code(
    anon_client, make_invite, db_session
):
    code = make_invite()

    response = register(anon_client, code, email="Me@Example.com", currency="MYR")

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "email": "me@example.com",
        "default_currency": "MYR",
    }
    assert "password" not in str(body)
    invite = db_session.scalar(select(InviteCode).where(InviteCode.code == code))
    assert invite.used_by_user_id == body["id"]
    assert invite.used_at is not None


def test_password_is_stored_hashed(anon_client, user, db_session):
    stored = db_session.scalar(select(User)).hashed_password

    assert "correct horse" not in stored
    assert stored.startswith("$argon2")


def test_register_rejects_an_unknown_code(anon_client):
    response = register(anon_client, "NOPE-NOPE")

    assert response.status_code == 400
    assert "ask for a new one" in response.json()["detail"]


def test_a_code_works_only_once(anon_client, make_invite):
    code = make_invite()
    assert register(anon_client, code).status_code == 201

    response = register(anon_client, code, email="friend@example.com")

    assert response.status_code == 400


def test_code_is_case_and_space_insensitive(anon_client, make_invite):
    code = make_invite()

    response = register(anon_client, f"  {code.lower()} ")

    assert response.status_code == 201


def test_register_rejects_an_existing_email_ignoring_case(
    anon_client, user, make_invite
):
    response = register(anon_client, make_invite(), email="ME@example.com")

    assert response.status_code == 409
    assert "log in instead" in response.json()["detail"]


def test_without_a_valid_code_it_never_reveals_existing_emails(anon_client, user):
    # Invite is checked first: a bad code gets 400, not "already registered".
    response = register(anon_client, "NOPE-NOPE", email="me@example.com")

    assert response.status_code == 400


@pytest.mark.parametrize(
    "changes",
    [{"password": "short"}, {"password": "x" * 129}, {"email": "not-an-email"}],
)
def test_register_validates_input(anon_client, make_invite, changes):
    args = {"email": "me@example.com", "password": "correct horse"} | changes

    response = register(anon_client, make_invite(), **args)

    assert response.status_code == 422


# --- Login ----------------------------------------------------------------------


def test_login_returns_access_token_and_sets_refresh_cookie(anon_client, user):
    response = login(anon_client, email="ME@example.com")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) == user["id"]
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("refresh_token=")
    assert "HttpOnly" in cookie
    assert "Path=/auth" in cookie
    assert "SameSite=lax" in cookie


@pytest.mark.parametrize(
    "email,password",
    [("me@example.com", "wrong password"), ("nobody@example.com", "correct horse")],
)
def test_login_failures_all_look_the_same(anon_client, user, email, password):
    response = login(anon_client, email, password)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
    assert "set-cookie" not in response.headers


# --- Refresh ----------------------------------------------------------------------


def test_refresh_rotates_the_token_and_keeps_the_end_date(
    anon_client, user, db_session
):
    first = login(anon_client).cookies["refresh_token"]

    response = anon_client.post("/auth/refresh")

    assert response.status_code == 200
    assert decode_access_token(response.json()["access_token"]) == user["id"]
    second = response.cookies["refresh_token"]
    assert second != first
    old = db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(first))
    )
    new = db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(second)
        )
    )
    assert old.revoked_at is not None
    assert new.revoked_at is None
    assert new.expires_at == old.expires_at  # refreshing never extends the 30 days


def test_refresh_without_a_cookie_is_refused(anon_client):
    response = anon_client.post("/auth/refresh")

    assert response.status_code == 401


def test_a_reused_old_token_logs_the_user_out_everywhere(anon_client, user):
    old = login(anon_client).cookies["refresh_token"]
    assert (
        anon_client.post("/auth/refresh").status_code == 200
    )  # rotates; jar has the new one

    anon_client.cookies.clear()
    anon_client.cookies.set("refresh_token", old)
    replay = anon_client.post("/auth/refresh")

    assert replay.status_code == 401
    assert "log in again" in replay.json()["detail"]
    # The legitimate new token died too: every session for this user was revoked.
    anon_client.cookies.clear()
    assert anon_client.post("/auth/refresh").status_code == 401


def test_an_expired_session_must_log_in_again(anon_client, user, db_session):
    login(anon_client)
    row = db_session.scalar(select(RefreshToken))
    row.expires_at = utcnow() - datetime.timedelta(seconds=1)
    db_session.commit()

    response = anon_client.post("/auth/refresh")

    assert response.status_code == 401
    assert "expired" in response.json()["detail"]


# --- Logout ---------------------------------------------------------------------


def test_logout_revokes_the_token_on_the_server(anon_client, user, db_session):
    token = login(anon_client).cookies["refresh_token"]

    response = anon_client.post("/auth/logout")

    assert response.status_code == 204
    row = db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    db_session.refresh(row)
    assert row.revoked_at is not None
    # Even a copy of the cookie kept from before logout no longer works.
    anon_client.cookies.set("refresh_token", token)
    assert anon_client.post("/auth/refresh").status_code == 401


def test_logout_without_a_cookie_is_harmless(anon_client):
    assert anon_client.post("/auth/logout").status_code == 204
