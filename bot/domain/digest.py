from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class WeekSummary:
    start: date  # понедельник
    end: date  # день сводки (воскресенье)
    done: int
    done_today: bool

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


def week_start(today: date) -> date:
    return today - timedelta(days=today.weekday())
