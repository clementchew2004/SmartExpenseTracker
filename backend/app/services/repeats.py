"""Repeating expenses: which dates are due. Pure date arithmetic in code.

Nothing runs on a timer. When the app opens it asks "anything due?", and the
answer is worked out from each repeat's next_due and today.
"""

import calendar
import datetime
from typing import Literal

from app.models import RepeatingExpense

Frequency = Literal["daily", "weekly", "monthly"]

# A daily repeat left alone for a year would be 365 cards; show at most this
# many at once. The rest appear as these are saved or skipped.
MAX_DUE = 31


def following(
    date: datetime.date, frequency: Frequency, day_of_month: int
) -> datetime.date:
    """The repeat date after `date`."""
    if frequency == "daily":
        return date + datetime.timedelta(days=1)
    if frequency == "weekly":
        return date + datetime.timedelta(days=7)

    # Monthly: the remembered day, or the month's last day if it's shorter.
    # Always from day_of_month, never from `date`, so 31 Jan -> 28 Feb -> 31 Mar
    # (using Feb's 28 as the new day would drift rent to the 28th forever).
    year, month = (
        (date.year + 1, 1) if date.month == 12 else (date.year, date.month + 1)
    )
    last_day = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, min(day_of_month, last_day))


def due_dates(repeat: RepeatingExpense, today: datetime.date) -> list[datetime.date]:
    """Every date from next_due up to today that hasn't been saved or skipped,
    oldest first, stopping at the end date."""
    dates = []
    date = repeat.next_due
    while date <= today and len(dates) < MAX_DUE:
        if repeat.end_date is not None and date > repeat.end_date:
            break
        dates.append(date)
        date = following(date, repeat.frequency, repeat.day_of_month)
    return dates


def is_finished(repeat: RepeatingExpense) -> bool:
    """Past its end date: no more reminders will ever come."""
    return repeat.end_date is not None and repeat.next_due > repeat.end_date
