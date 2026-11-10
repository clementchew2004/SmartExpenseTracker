import datetime
from typing import Annotated

from fastapi import Depends


def get_today() -> datetime.date:
    """A dependency, so tests can swap in a fixed date (like they swap get_db)."""
    return datetime.date.today()


Today = Annotated[datetime.date, Depends(get_today)]
