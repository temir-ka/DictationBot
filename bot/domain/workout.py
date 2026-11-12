import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol, TypeVar

from bot.content.models import Content, ReadingText


class _HasId(Protocol):
    id: str


T = TypeVar("T", bound=_HasId)


@dataclass(frozen=True, slots=True)
class History:
    """Абзацы из выполненных сетов до сегодняшнего дня (в хронологическом порядке)."""

    reading_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Workout:
    """Сет на день: блоки 1-4 фиксированы (content.routine), меняется только абзац для чтения."""

    date: date
    reading: ReadingText


def build_workout(user_id: int, today: date, content: Content, history: History) -> Workout:
    """Сет на день.

    Генератор засеян пользователем и датой, а история берётся только до сегодняшнего дня,
    поэтому напоминание, /today и кнопка «Выполнил» в течение дня видят один и тот же абзац.
    """
    rng = random.Random(f"{user_id}:{today.isoformat()}")
    return Workout(date=today, reading=pick_unused(content.reading_texts, history.reading_ids, rng))


def pick_unused(pool: Sequence[T], used_ids: Sequence[str], rng: random.Random) -> T:
    """Элемент, который ещё не выпадал.

    Когда пул исчерпан, начинается новый круг: выбор идёт среди выпадавших реже всего,
    и последний показанный элемент не повторяется сразу же.
    """
    usage = Counter(used_ids)
    least = min(usage[item.id] for item in pool)
    candidates = [item for item in pool if usage[item.id] == least]
    if used_ids and len(candidates) > 1:
        candidates = [item for item in candidates if item.id != used_ids[-1]]
    return rng.choice(candidates)
