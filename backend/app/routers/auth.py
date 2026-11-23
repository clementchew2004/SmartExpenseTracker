import datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    DUMMY_PASSWORD_HASH,
    CurrentUser,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    utcnow,
    verify_password,
)
from app.config import get_settings
from app.db import get_db
from app.models import (
    Budget,
    DefaultBudget,
    Expense,
    InviteCode,
    RefreshToken,
    RepeatingExpense,
    User,
    WeeklySummary,
)
from app.schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]
RefreshCookie = Annotated[str | None, Cookie(alias="refresh_token")]

REFRESH_COOKIE = "refresh_token"
# The cookie is only ever sent to the auth endpoints: COOKIE_PATH in config.py
# ("/auth" on your laptop, "/api/auth" behind the production proxy).


# --- Cookie helpers ------------------------------------------------------------


def set_refresh_cookie(
    response: Response, token: str, expires_at: datetime.datetime
) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=int((expires_at - utcnow()).total_seconds()),
        httponly=True,  # JavaScript can't read it, so an XSS bug can't steal it
        secure=get_settings().COOKIE_SECURE,
        samesite="lax",  # other websites can't make the browser send it
        path=get_settings().COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=get_settings().COOKIE_PATH,
        httponly=True,
        secure=get_settings().COOKIE_SECURE,
        samesite="lax",
    )


def issue_tokens(
    db: Session, user_id: int, expires_at: datetime.datetime
) -> tuple[TokenResponse, str]:
    """Store a new refresh token (hash only) and make a fresh access token."""
    token, token_hash = new_refresh_token()
    db.add(RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
    return TokenResponse(access_token=create_access_token(user_id)), token


def refresh_failed(message: str) -> JSONResponse:
    # Returned rather than raised: HTTPException can't carry the "delete this
    # cookie" header, and a dead refresh cookie should be cleared.
    response = JSONResponse(
        {"detail": message},
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )
    clear_refresh_cookie(response)
    return response


# --- Endpoints -------------------------------------------------------------------


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: DbSession) -> UserRead:
    # 1. Invite code FIRST: without a valid one, nothing else is checked or revealed.
    #    FOR UPDATE locks the row so two people can't redeem the same code at once.
    invite = db.scalar(
        select(InviteCode)
        .where(InviteCode.code == body.invite_code.strip().upper())
        .where(InviteCode.used_at.is_(None))
        .with_for_update()
    )
    if invite is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "That invite code isn't valid - ask for a new one",
        )

    # 2. One account per email, ignoring case.
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have an account - log in instead"
        )

    # 3. Create the user and use up the code in the SAME commit: both happen or neither.
    user = User(
        email=email,
        hashed_password=hash_password(body.password),
        default_currency=body.default_currency,
    )
    db.add(user)
    db.flush()  # sends the INSERT now so user.id exists for the invite row
    invite.used_by_user_id = user.id
    invite.used_at = utcnow()
    try:
        db.commit()
    except IntegrityError as e:  # the same email registered a split second earlier
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have an account - log in instead"
        ) from e
    db.refresh(user)
    return user


@router.post("/login")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    response: Response,
    db: DbSession,
) -> TokenResponse:
    """OAuth2 password flow: a form with `username` (your email) and `password`."""
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    if user is None:
        verify_password(form.password, DUMMY_PASSWORD_HASH)  # same time as a real check
        password_ok = False
    else:
        password_ok = verify_password(form.password, user.hashed_password)
    if not password_ok:
        # One message for both cases, so login never reveals which emails exist.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_at = utcnow() + datetime.timedelta(days=get_settings().REFRESH_TOKEN_DAYS)
    tokens, refresh_token = issue_tokens(db, user.id, expires_at)
    db.commit()
    set_refresh_cookie(response, refresh_token, expires_at)
    return tokens


@router.post("/refresh")
def refresh(
    response: Response, db: DbSession, refresh_token: RefreshCookie = None
) -> TokenResponse:
    """Swap a valid refresh cookie for a new access token AND a new refresh cookie."""
    if not refresh_token:
        return refresh_failed("Not logged in")

    # The cookie itself identifies the user: find its hash, and the row says whose it is.
    row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
        .with_for_update()
    )
    if row is None:
        return refresh_failed("Not logged in")

    if row.revoked_at is not None:
        # A token that was already rotated or logged out has come back: someone is
        # replaying a stolen copy. Log that user out everywhere.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == row.user_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        db.commit()
        return refresh_failed("Session ended - please log in again")

    if row.expires_at <= utcnow():
        return refresh_failed("Session expired - please log in again")

    # Rotate: retire this token, issue a new one with the SAME end date (30 days
    # after login), so refreshing never extends the session.
    row.revoked_at = utcnow()
    tokens, new_token = issue_tokens(db, row.user_id, row.expires_at)
    db.commit()
    set_refresh_cookie(response, new_token, row.expires_at)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: DbSession, refresh_token: RefreshCookie = None) -> Response:
    """Revoke the token on the server (a stolen copy dies too), then clear the cookie."""
    if refresh_token:
        row = db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh_token)
            )
        )
        if row is not None and row.revoked_at is None:
            row.revoked_at = utcnow()
            db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.get("/me")
def me(user: CurrentUser) -> UserRead:
    """Who the access token belongs to. The app shows this on the Settings tab."""
    return user


@router.patch("/me")
def update_me(body: UserUpdate, db: DbSession, user: CurrentUser) -> UserRead:
    """Change your default currency. Saved expenses keep their own currency."""
    user.default_currency = body.default_currency
    db.commit()
    return user


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest, response: Response, db: DbSession, user: CurrentUser
) -> TokenResponse:
    """Check the current password, set the new one, and log out every other
    device: if you're changing it because it leaked, whoever has it is out.
    This device gets a fresh login so you stay in.

    The other logins are DELETED, not revoked: a revoked token that comes back
    looks like theft to /refresh and logs out everyone - including you, the
    moment your other device tries to refresh. An unknown token is just
    "not logged in"."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Your current password is incorrect"
        )
    user.hashed_password = hash_password(body.new_password)
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    expires_at = utcnow() + datetime.timedelta(days=get_settings().REFRESH_TOKEN_DAYS)
    tokens, refresh_token = issue_tokens(db, user.id, expires_at)
    db.commit()
    set_refresh_cookie(response, refresh_token, expires_at)
    return tokens


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(body: DeleteAccountRequest, db: DbSession, user: CurrentUser) -> Response:
    """Delete your account and everything that's yours. Can't be undone.

    The invite code goes too: if it were only unlinked, it would look unused
    and work again for someone else.
    """
    for table in (WeeklySummary, RepeatingExpense, Budget, DefaultBudget, Expense):
        db.execute(delete(table).where(table.user_id == user.id))
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    db.execute(delete(InviteCode).where(InviteCode.used_by_user_id == user.id))
    db.delete(user)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response
