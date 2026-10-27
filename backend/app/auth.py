"""Passwords, access tokens and refresh tokens, plus get_current_user: the
dependency every protected route uses to find out who is calling."""

import datetime
import hashlib
import secrets
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

JWT_ALGORITHM = "HS256"

# Argon2 with pwdlib's recommended (deliberately slow) settings.
password_hash = PasswordHash.recommended()

# A real hash of a random password. Login checks it when the email doesn't exist,
# so "no such account" takes as long as "wrong password" and timing reveals nothing.
DUMMY_PASSWORD_HASH = password_hash.hash(secrets.token_urlsafe(16))


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


# --- Passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    """Salt + Argon2. The salt and settings are stored inside the returned string."""
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Re-hash the typed password with the stored salt and compare. Never un-hashes."""
    return password_hash.verify(password, hashed)


# --- Access tokens (JWT, short-lived, kept in the app's memory) ---------------


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),  # "subject": who this token is about
        "iat": now,  # issued at
        "exp": now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=JWT_ALGORITHM
    )


def decode_access_token(token: str) -> int:
    """The user id inside a valid token. Raises jwt.InvalidTokenError if the
    signature is wrong, it was tampered with, or it has expired."""
    payload = jwt.decode(
        token,
        get_settings().JWT_SECRET_KEY.get_secret_value(),
        algorithms=[JWT_ALGORITHM],  # never let the token choose its own algorithm
    )
    return int(payload["sub"])


# --- Refresh tokens (random, long-lived, kept in an httpOnly cookie) ---------


def new_refresh_token() -> tuple[str, str]:
    """A random token for the cookie, and the hash we store instead of it."""
    token = secrets.token_urlsafe(32)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    # A fast hash is fine here: the token is 32 random bytes, so unlike a
    # human-chosen password there's nothing to guess. Passwords need slow Argon2.
    return hashlib.sha256(token.encode()).hexdigest()


# --- Who is calling? (the dependency every protected route uses) -------------

# Reads "Authorization: Bearer <token>" and hands over just the token string.
# No header -> 401 before get_current_user even runs. tokenUrl adds the
# Authorize button to /docs, which logs in through /auth/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    # One response for every failure: the client only needs "log in again".
    not_logged_in = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not logged in",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # 1. Signature and expiry: proves OUR server issued it, recently.
    try:
        user_id = decode_access_token(token)
    except (jwt.InvalidTokenError, KeyError, ValueError) as e:
        raise not_logged_in from e
    # 2. The token can't know if the account was deleted since; only the DB can.
    user = db.get(User, user_id)
    if user is None:
        raise not_logged_in
    # 3. The whole row, so routes have user.id AND user.default_currency.
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
