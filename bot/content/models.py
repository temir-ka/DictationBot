from collections.abc import Sequence
from typing import Literal, Protocol, Self, TypeVar, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Порядок важен: в нём упражнения выводятся в сете — от крупных мышц к тонким движениям языка.
MuscleGroup = Literal["jaw", "lips", "cheeks", "tongue"]
MUSCLE_GROUPS: tuple[MuscleGroup, ...] = get_args(MuscleGroup)


class Exercise(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    muscle_group: MuscleGroup
    instructions: str
    # reps — дискретные повторы (reps — их число); continuous — одно слитное действие
    # на всё duration_sec, reps = null.
    mode: Literal["reps", "continuous"]
    reps: int | None = Field(default=None, ge=1)
    duration_sec: int | None = Field(default=None, ge=1)
    caution: str | None = None

    @model_validator(mode="after")
    def _check_mode(self) -> Self:
        if self.mode == "reps" and self.reps is None:
            raise ValueError(f"{self.id}: для mode=reps нужно указать reps")
        if self.mode == "continuous" and (self.reps is not None or self.duration_sec is None):
            raise ValueError(f"{self.id}: для mode=continuous нужен duration_sec, а reps = null")
        return self


class ExercisePool(BaseModel):
    """Формат articulation_exercises.json; служебные поля вроде _readme игнорируются."""

    exercises: list[Exercise]


class TongueTwister(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    text: str


class TwisterPool(BaseModel):
    """Формат tongue_twisters.json; служебные поля вроде _readme игнорируются."""

    twisters: list[TongueTwister]


class ReadingText(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    text: str


class ReadingPool(BaseModel):
    """Формат reading_texts.json; служебные поля вроде _readme игнорируются."""

    texts: list[ReadingText]


class ControlText(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    text: str


class Stickers(BaseModel):
    """file_id стикеров по событиям (stickers.json); пустой список — без стикера."""

    completed: list[str] = []
    milestone: list[str] = []
    measurement_saved: list[str] = []
    streak_lost: list[str] = []


class Content(BaseModel):
    exercises: list[Exercise]
    tongue_twisters: list[TongueTwister]
    reading_texts: list[ReadingText]
    control_text: ControlText
    stickers: Stickers = Stickers()

    def exercises_in(self, group: MuscleGroup) -> list[Exercise]:
        return [e for e in self.exercises if e.muscle_group == group]

    def find_exercise(self, item_id: str) -> Exercise | None:
        return _find(self.exercises, item_id)

    def find_twister(self, item_id: str) -> TongueTwister | None:
        return _find(self.tongue_twisters, item_id)

    def find_reading(self, item_id: str) -> ReadingText | None:
        return _find(self.reading_texts, item_id)


class _HasId(Protocol):
    id: str


T = TypeVar("T", bound=_HasId)


def _find(items: Sequence[T], item_id: str) -> T | None:
    return next((item for item in items if item.id == item_id), None)
