"""Passwords, access tokens and refresh tokens. No HTTP here - routers/auth.py uses these."""

import datetime
import hashlib
import secrets

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

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
