import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol, TypeVar

from bot.content.models import MUSCLE_GROUPS, Content, Exercise, ReadingText, TongueTwister


class _HasId(Protocol):
    id: str


T = TypeVar("T", bound=_HasId)


@dataclass(frozen=True, slots=True)
class History:
    """Что было в выполненных сетах до сегодняшнего дня (в хронологическом порядке)."""

    last_exercise_ids: frozenset[str] = frozenset()
    twister_ids: tuple[str, ...] = ()
    reading_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Workout:
    date: date
    exercises: tuple[Exercise, ...]  # по одному на группу, в порядке MUSCLE_GROUPS
    reading: ReadingText
    twister: TongueTwister


def build_workout(user_id: int, today: date, content: Content, history: History) -> Workout:
    """Случайный сет на день.

    Генератор засеян пользователем и датой, а история берётся только до сегодняшнего дня,
    поэтому напоминание, /today и кнопка «Выполнил» в течение дня видят один и тот же сет.
    """
    rng = random.Random(f"{user_id}:{today.isoformat()}")
    exercises = tuple(
        _pick_exercise(content.exercises_in(group), history.last_exercise_ids, rng)
        for group in MUSCLE_GROUPS
    )
    return Workout(
        date=today,
        exercises=exercises,
        reading=pick_unused(content.reading_texts, history.reading_ids, rng),
        twister=pick_unused(content.tongue_twisters, history.twister_ids, rng),
    )


def _pick_exercise(pool: Sequence[Exercise], last_ids: frozenset[str], rng: random.Random) -> Exercise:
    # Не повторяем упражнение из прошлого сета, если в группе есть из чего выбрать.
    fresh = [e for e in pool if e.id not in last_ids]
    return rng.choice(fresh or pool)


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
