from pydantic import BaseModel, ConfigDict, Field


class RoutineBlock(BaseModel):
    """Фиксированный блок ежедневного сета; instructions — строки, выводятся каждая с новой строки."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    duration_sec: int = Field(ge=1)
    instructions: list[str] = Field(min_length=1)


class DailyRoutine(BaseModel):
    """Формат daily_routine.json; служебные поля вроде _readme игнорируются."""

    blocks: list[RoutineBlock] = Field(min_length=1)


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
    routine: list[RoutineBlock]
    reading_texts: list[ReadingText]
    control_text: ControlText
    stickers: Stickers = Stickers()
