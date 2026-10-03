import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

_TIME_RE = re.compile(r"^\s*(\d{1,2})[:.\s](\d{2})\s*$")


def parse_time(text: str) -> time | None:
    """Разбирает «8:30», «08.30», «8 30» → time. None, если формат неверный."""
    match = _TIME_RE.match(text)
    if match is None:
        return None
    hour, minute = int(match[1]), int(match[2])
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def local_now(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz))


def local_today(tz: str) -> date:
    return local_now(tz).date()
