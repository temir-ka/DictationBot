from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True)
class User:
    id: int
    reminder_time: time
    current_streak: int = 0
    best_streak: int = 0
    last_completed_at: date | None = None
    last_measurement_at: date | None = None


@dataclass(frozen=True, slots=True)
class Member:
    """Запись белого списка; current_streak=None — доступ есть, но /start ещё не нажат."""

    id: int
    name: str | None
    added_at: date
    current_streak: int | None
