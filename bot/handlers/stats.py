from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import texts
from bot.config import Settings
from bot.db.repo import Repo
from bot.handlers.common import load_user
from bot.timeutils import local_today

router = Router(name="stats")


@router.message(Command("streak"))
async def cmd_streak(message: Message, repo: Repo, settings: Settings) -> None:
    user = await load_user(message, repo)
    if user is not None:
        await message.answer(texts.streak(user, local_today(settings.timezone)))


@router.message(Command("progress"))
async def cmd_progress(message: Message, repo: Repo) -> None:
    user = await load_user(message, repo)
    if user is None:
        return
    measurements = await repo.list_measurements(user.id)
    if not measurements:
        await message.answer(texts.NO_MEASUREMENTS)
        return
    await message.answer(texts.progress(measurements), reply_markup=kb.progress_kb(measurements))


@router.callback_query(kb.PlayCb.filter())
async def on_play(callback: CallbackQuery, callback_data: kb.PlayCb, bot: Bot, repo: Repo) -> None:
    measurements = await repo.list_measurements(callback.from_user.id)
    found = [
        (number, m)
        for number, m in enumerate(measurements, start=1)
        if m.id == callback_data.measurement_id
    ]
    if not found:
        await callback.answer(texts.MEASUREMENT_NOT_FOUND, show_alert=True)
        return
    number, measurement = found[0]
    await callback.answer()
    chat_id = callback.from_user.id
    await bot.send_voice(
        chat_id,
        measurement.voice_precise_file_id,
        caption=texts.voice_caption(number, measurement, "precise"),
    )
    await bot.send_voice(
        chat_id,
        measurement.voice_casual_file_id,
        caption=texts.voice_caption(number, measurement, "casual"),
    )
