import datetime
import re

WEEKDAYS = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "weds": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}

# Optional "last" or "on", then one word: "last friday", "on fri", "wednesday".
WEEKDAY_PHRASE = re.compile(r"^(last|on)?\s*([a-z]+)$")


def resolve_weekday(
    date_text: str | None, today: datetime.date
) -> datetime.date | None:
    """Work out the date for weekday phrases like "last friday" or "on fri".

    Returns None for anything else, so the caller keeps the model's date.
    Weeks run Monday to Sunday. LLMs get this arithmetic wrong; code doesn't.
    """
    if not date_text:
        return None
    cleaned = " ".join(date_text.lower().strip(" .,!").split())
    match = WEEKDAY_PHRASE.match(cleaned)
    if match is None or match.group(2) not in WEEKDAYS:
        return None

    prefix, day = match.groups()
    weekday = WEEKDAYS[day]  # Monday = 0 ... Sunday = 6

    if prefix == "last":
        # That weekday in last week.
        this_monday = today - datetime.timedelta(days=today.weekday())
        last_monday = this_monday - datetime.timedelta(days=7)
        return last_monday + datetime.timedelta(days=weekday)

    # "friday" or "on friday": the most recent one on or before today.
    days_back = (today.weekday() - weekday) % 7
    return today - datetime.timedelta(days=days_back)
