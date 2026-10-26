"""Create a one-use invite code and print it.

Run from backend/ with the venv active:
    python -m app.create_invite
"""

import secrets

from app.db import SessionLocal
from app.models import InviteCode

# No look-alikes (0/O, 1/I/L), so a code read out or texted can't be mistyped.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def main() -> None:
    with SessionLocal() as db:
        code = new_code()
        db.add(InviteCode(code=code))
        db.commit()
    print(f"Invite code: {code}  (works once)")


if __name__ == "__main__":
    main()
