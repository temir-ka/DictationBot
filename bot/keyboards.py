from datetime import date

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot.content.models import MUSCLE_GROUPS, Content
from bot.domain.measurement import Measurement
from bot.domain.workout import Workout


class DoneCb(CallbackData, prefix="done"):
    day: str  # ISO-дата сета: кнопка под вчерашним напоминанием не засчитывает сегодняшний день


class InstructionsCb(CallbackData, prefix="ins"):
    """Переключатель инструкций. Хранит сам сет, чтобы перерисовать сообщение без БД.

    Пример: ins:1:ex_028,ex_001,ex_021,ex_010:tw_001:txt_0231 — ~50 байт из 64.
    """

    show: bool  # в какое состояние переключить сообщение по нажатию
    ex: str  # id упражнений через запятую, в порядке MUSCLE_GROUPS
    tw: str
    rd: str


class MeasureCb(CallbackData, prefix="measure"):
    action: str  # start | later | skip_notes


class PlayCb(CallbackData, prefix="play"):
    measurement_id: int


class AccessCb(CallbackData, prefix="access"):
    allow: bool
    user_id: int


def workout_kb(workout: Workout, *, showing_instructions: bool, with_done: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Свернуть 🔼" if showing_instructions else "Показать инструкции 📖",
        callback_data=_instructions_cb(workout, show=not showing_instructions),
    )
    if with_done:
        builder.button(text="Выполнил ✅", callback_data=DoneCb(day=workout.date.isoformat()))
    builder.adjust(1)
    return builder.as_markup()


def _is_done_button(button: InlineKeyboardButton) -> bool:
    return (button.callback_data or "").startswith(DoneCb.__prefix__ + DoneCb.__separator__)


def has_done_button(markup: InlineKeyboardMarkup | None) -> bool:
    return markup is not None and any(
        _is_done_button(button) for row in markup.inline_keyboard for button in row
    )


def without_done_button(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    rows = [[b for b in row if not _is_done_button(b)] for row in markup.inline_keyboard]
    return InlineKeyboardMarkup(inline_keyboard=[row for row in rows if row])


def workout_from_callback(data: InstructionsCb, content: Content, day: date) -> Workout | None:
    """Восстанавливает сет из кнопки; None — если что-то из него уже удалено из контента."""
    exercises = [content.find_exercise(item_id) for item_id in data.ex.split(",")]
    twister = content.find_twister(data.tw)
    reading = content.find_reading(data.rd)
    if None in exercises or twister is None or reading is None:
        return None
    return Workout(date=day, exercises=tuple(exercises), reading=reading, twister=twister)


def ensure_callbacks_fit(content: Content) -> None:
    """Падает при старте, если кнопка инструкций с самыми длинными id не влезает в 64 байта."""
    def longest(ids: list[str]) -> str:
        return max(ids, key=lambda i: len(i.encode()))

    worst = InstructionsCb(
        show=True,
        ex=",".join(longest([e.id for e in content.exercises_in(g)]) for g in MUSCLE_GROUPS),
        tw=longest([t.id for t in content.tongue_twisters]),
        rd=longest([t.id for t in content.reading_texts]),
    )
    worst.pack()  # ValueError, если длиннее 64 байт


def _instructions_cb(workout: Workout, *, show: bool) -> InstructionsCb:
    return InstructionsCb(
        show=show,
        ex=",".join(e.id for e in workout.exercises),
        tw=workout.twister.id,
        rd=workout.reading.id,
    )


def time_presets_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for preset in ("07:00", "08:00", "09:00", "12:00", "19:00", "21:00"):
        builder.button(text=preset)
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def measurement_invite_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📏 Начать замер", callback_data=MeasureCb(action="start"))
    builder.button(text="Позже", callback_data=MeasureCb(action="later"))
    return builder.as_markup()


def skip_notes_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить", callback_data=MeasureCb(action="skip_notes"))
    return builder.as_markup()


def progress_kb(measurements: list[Measurement]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for number, measurement in enumerate(measurements, start=1):
        builder.button(text=f"▶️ №{number}", callback_data=PlayCb(measurement_id=measurement.id))
    builder.adjust(4)
    return builder.as_markup()


def access_request_kb(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Разрешить", callback_data=AccessCb(allow=True, user_id=user_id))
    builder.button(text="🚫 Отклонить", callback_data=AccessCb(allow=False, user_id=user_id))
    return builder.as_markup()
