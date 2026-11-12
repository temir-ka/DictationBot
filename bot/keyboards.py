from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot.domain.measurement import Measurement
from bot.domain.workout import Workout


class DoneCb(CallbackData, prefix="done"):
    day: str  # ISO-дата сета: кнопка под вчерашним напоминанием не засчитывает сегодняшний день


class StepCb(CallbackData, prefix="step"):
    day: str  # ISO-дата сета: шаги вчерашнего сообщения не листаются
    step: int  # на какой шаг перейти (с нуля)


class SnoozeCb(CallbackData, prefix="snooze"):
    day: str


class MeasureCb(CallbackData, prefix="measure"):
    action: str  # start | later | skip_notes


class PlayCb(CallbackData, prefix="play"):
    measurement_id: int


class AccessCb(CallbackData, prefix="access"):
    allow: bool
    user_id: int


def step_kb(workout: Workout, step: int, total: int, *, snooze: bool = False) -> InlineKeyboardMarkup:
    """Первый шаг: «Дальше» + «сразу к чтению» (+ «через час» у напоминания);
    средние: «Назад»/«Дальше»; последний: «Назад»/«Выполнил»."""
    day = workout.date.isoformat()
    builder = InlineKeyboardBuilder()
    if step > 0:
        builder.button(text="◀️ Назад", callback_data=StepCb(day=day, step=step - 1))
    if step < total - 1:
        builder.button(text="Дальше ▶️", callback_data=StepCb(day=day, step=step + 1))
    else:
        builder.button(text="Выполнил ✅", callback_data=DoneCb(day=day))
    if step == 0:
        builder.button(text="⏩ Нет времени — сразу к чтению", callback_data=StepCb(day=day, step=total - 1))
        if snooze:
            builder.button(text="⏰ Напомни через час", callback_data=SnoozeCb(day=day))
    builder.adjust(2 if step > 0 else 1)
    return builder.as_markup()


def evening_kb(workout: Workout, total: int) -> InlineKeyboardMarkup:
    day = workout.date.isoformat()
    builder = InlineKeyboardBuilder()
    builder.button(text="⏩ Сразу к чтению", callback_data=StepCb(day=day, step=total - 1))
    builder.button(text="🎯 Весь сет", callback_data=StepCb(day=day, step=0))
    builder.adjust(1)
    return builder.as_markup()


def without_snooze(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    prefix = SnoozeCb.__prefix__ + SnoozeCb.__separator__
    rows = [[b for b in row if not (b.callback_data or "").startswith(prefix)] for row in markup.inline_keyboard]
    return InlineKeyboardMarkup(inline_keyboard=[row for row in rows if row])


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
