from dataclasses import dataclass
from datetime import date, time

DEFAULT_EVENING_TIME = time(21, 0)


@dataclass(frozen=True, slots=True)
class User:
    id: int
    reminder_time: time
    current_streak: int = 0
    best_streak: int = 0
    last_completed_at: date | None = None
    last_measurement_at: date | None = None
    # Вечернее «стрик под угрозой», если сет не сделан; None — выключено.
    evening_time: time | None = DEFAULT_EVENING_TIME

    @property
    def evening_active(self) -> bool:
        """Вечернее напоминание имеет смысл, только если оно позже основного."""
        return self.evening_time is not None and self.evening_time > self.reminder_time


@dataclass(frozen=True, slots=True)
class Member:
    """Запись белого списка; current_streak=None — доступ есть, но /start ещё не нажат."""

    id: int
    name: str | None
    added_at: date
    current_streak: int | None
