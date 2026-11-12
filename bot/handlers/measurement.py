"""Замер: контрольный текст → голосовое → необязательная заметка."""

from dataclasses import replace

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import texts
from bot.config import Settings
from bot.content.models import Content
from bot.db.repo import Repo
from bot.domain.measurement import Measurement, is_measurement_due
from bot.domain.user import User
from bot.handlers.common import NOT_COMMAND, load_user, remove_markup
from bot.services import send_sticker
from bot.timeutils import local_today

router = Router(name="measurement")


class MeasurementFlow(StatesGroup):
    voice = State()
    notes = State()


@router.message(Command("measure"))
async def cmd_measure(
    message: Message,
    state: FSMContext,
    bot: Bot,
    repo: Repo,
    content: Content,
    settings: Settings,
) -> None:
    user = await load_user(message, repo)
    if user is not None:
        await _start(user, state, bot, content, settings)


@router.callback_query(kb.MeasureCb.filter(F.action == "start"))
async def on_measure_start(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    repo: Repo,
    content: Content,
    settings: Settings,
) -> None:
    user = await load_user(callback, repo)
    if user is None:
        return
    await callback.answer()
    await remove_markup(callback)
    await _start(user, state, bot, content, settings)


@router.callback_query(kb.MeasureCb.filter(F.action == "later"))
async def on_measure_later(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    await remove_markup(callback)
    await bot.send_message(callback.from_user.id, texts.MEASUREMENT_LATER)


async def _start(
    user: User, state: FSMContext, bot: Bot, content: Content, settings: Settings
) -> None:
    today = local_today(settings.timezone)
    if not is_measurement_due(user, today):
        await bot.send_message(user.id, texts.measurement_not_due(user, today))
        return

    await state.set_state(MeasurementFlow.voice)
    await state.set_data({"control_text_id": content.control_text.id})
    await bot.send_message(user.id, texts.measurement_material(content.control_text))


@router.message(MeasurementFlow.voice, F.voice)
async def on_voice(message: Message, state: FSMContext) -> None:
    await state.update_data(voice_file_id=message.voice.file_id)
    await state.set_state(MeasurementFlow.notes)
    await message.answer(texts.MEASUREMENT_NOTES, reply_markup=kb.skip_notes_kb())


@router.message(MeasurementFlow.notes, NOT_COMMAND)
async def on_notes(
    message: Message,
    state: FSMContext,
    bot: Bot,
    repo: Repo,
    content: Content,
    settings: Settings,
) -> None:
    await _finish(message.from_user.id, state, bot, repo, content, settings, notes=message.text)


@router.callback_query(MeasurementFlow.notes, kb.MeasureCb.filter(F.action == "skip_notes"))
async def on_skip_notes(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    repo: Repo,
    content: Content,
    settings: Settings,
) -> None:
    await callback.answer()
    await remove_markup(callback)
    await _finish(callback.from_user.id, state, bot, repo, content, settings, notes=None)


async def _finish(
    user_id: int,
    state: FSMContext,
    bot: Bot,
    repo: Repo,
    content: Content,
    settings: Settings,
    notes: str | None,
) -> None:
    data = await state.get_data()
    today = local_today(settings.timezone)
    async with repo.lock:
        user = await repo.get_user(user_id)
        if user is None:
            await state.clear()
            return
        measurement = Measurement(
            user_id=user.id,
            date=today,
            control_text_id=data["control_text_id"],
            voice_file_id=data["voice_file_id"],
            notes=notes,
        )
        await repo.add_measurement(measurement, replace(user, last_measurement_at=today))
    await state.clear()
    number = len(await repo.list_measurements(user_id))
    await bot.send_message(user_id, texts.measurement_saved(number))
    await send_sticker(bot, user_id, content.stickers.measurement_saved)


# --- всё остальное во время записи голосового ---

@router.message(MeasurementFlow.voice)
async def on_waiting_voice(message: Message) -> None:
    await message.answer(texts.WAITING_VOICE)
