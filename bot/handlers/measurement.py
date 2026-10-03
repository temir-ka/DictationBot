"""Замер: контрольный текст + скороговорки → голосовое precise → голосовое casual → заметка."""

import random
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
from bot.domain.measurement import Measurement, is_measurement_due, pick_measurement_twisters
from bot.domain.user import User
from bot.handlers.common import NOT_COMMAND, load_user, remove_markup
from bot.services import send_sticker
from bot.timeutils import local_today

router = Router(name="measurement")


class MeasurementFlow(StatesGroup):
    precise = State()
    casual = State()
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
        await _start(user, state, bot, repo, content, settings)


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
    await _start(user, state, bot, repo, content, settings)


@router.callback_query(kb.MeasureCb.filter(F.action == "later"))
async def on_measure_later(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    await remove_markup(callback)
    await bot.send_message(callback.from_user.id, texts.MEASUREMENT_LATER)


async def _start(
    user: User, state: FSMContext, bot: Bot, repo: Repo, content: Content, settings: Settings
) -> None:
    today = local_today(settings.timezone)
    if not is_measurement_due(user, today):
        await bot.send_message(user.id, texts.measurement_not_due(user, today))
        return

    last = await repo.last_measurement(user.id)
    twisters = pick_measurement_twisters(
        content.tongue_twisters,
        previous_ids=last.twister_ids if last else (),
        rng=random.Random(),
    )
    await state.set_state(MeasurementFlow.precise)
    await state.set_data(
        {
            "control_text_id": content.control_text.id,
            "twister_ids": [t.id for t in twisters],
        }
    )
    await bot.send_message(user.id, texts.measurement_material(content.control_text, twisters))
    await bot.send_message(user.id, texts.MEASUREMENT_STEP_PRECISE)


@router.message(MeasurementFlow.precise, F.voice)
async def on_precise_voice(message: Message, state: FSMContext) -> None:
    await state.update_data(voice_precise_file_id=message.voice.file_id)
    await state.set_state(MeasurementFlow.casual)
    await message.answer(texts.MEASUREMENT_STEP_CASUAL)


@router.message(MeasurementFlow.casual, F.voice)
async def on_casual_voice(message: Message, state: FSMContext) -> None:
    await state.update_data(voice_casual_file_id=message.voice.file_id)
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
            twister_ids=tuple(data["twister_ids"]),
            voice_precise_file_id=data["voice_precise_file_id"],
            voice_casual_file_id=data["voice_casual_file_id"],
            notes=notes,
        )
        await repo.add_measurement(measurement, replace(user, last_measurement_at=today))
    await state.clear()
    number = len(await repo.list_measurements(user_id))
    await bot.send_message(user_id, texts.measurement_saved(number))
    await send_sticker(bot, user_id, content.stickers.measurement_saved)


# --- всё остальное во время записи голосовых ---

@router.message(MeasurementFlow.precise)
@router.message(MeasurementFlow.casual)
async def on_waiting_voice(message: Message) -> None:
    await message.answer(texts.WAITING_VOICE)
