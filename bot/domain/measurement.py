import random
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date

from bot.content.models import TongueTwister
from bot.domain.user import User

MEASUREMENT_INTERVAL_DAYS = 14
MEASUREMENT_TWISTERS = 3


@dataclass(frozen=True, slots=True)
class Measurement:
    user_id: int
    date: date
    control_text_id: str
    twister_ids: tuple[str, ...]
    voice_precise_file_id: str
    voice_casual_file_id: str
    notes: str | None = None
    id: int | None = None


def is_measurement_due(user: User, today: date) -> bool:
    """Первый (стартовый) замер — сразу, дальше раз в 14 календарных дней."""
    return days_until_measurement(user, today) == 0


def days_until_measurement(user: User, today: date) -> int:
    if user.last_measurement_at is None:
        return 0
    return max(0, MEASUREMENT_INTERVAL_DAYS - (today - user.last_measurement_at).days)


def pick_measurement_twisters(
    pool: Sequence[TongueTwister],
    previous_ids: Collection[str],
    rng: random.Random,
    count: int = MEASUREMENT_TWISTERS,
) -> list[TongueTwister]:
    """Случайные скороговорки, по возможности не те, что были в прошлом замере."""
    count = min(count, len(pool))
    fresh = [t for t in pool if t.id not in previous_ids]
    if len(fresh) >= count:
        return rng.sample(fresh, count)
    used = [t for t in pool if t.id in previous_ids]
    return fresh + rng.sample(used, count - len(fresh))
