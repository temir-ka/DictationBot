from dataclasses import dataclass
from datetime import date

from bot.domain.user import User

MEASUREMENT_INTERVAL_DAYS = 14


@dataclass(frozen=True, slots=True)
class Measurement:
    user_id: int
    date: date
    control_text_id: str
    voice_file_id: str
    notes: str | None = None
    id: int | None = None


def is_measurement_due(user: User, today: date) -> bool:
    """Первый (стартовый) замер — сразу, дальше раз в 14 календарных дней."""
    return days_until_measurement(user, today) == 0


def days_until_measurement(user: User, today: date) -> int:
    if user.last_measurement_at is None:
        return 0
    return max(0, MEASUREMENT_INTERVAL_DAYS - (today - user.last_measurement_at).days)
