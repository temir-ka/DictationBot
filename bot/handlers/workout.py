from contextlib import suppress
from zoneinfo import ZoneInfo

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import texts
from bot.config import Settings
from bot.content.models import Content
from bot.db.repo import Repo
from bot.domain.streak import complete_day
from bot.handlers.common import load_user
from bot.services import build_today, send_sticker, send_workout
from bot.timeutils import local_today

router = Router(name="workout")


@router.message(Command("today"))
async def cmd_today(
    message: Message, bot: Bot, repo: Repo, content: Content, settings: Settings
) -> None:
    user = await load_user(message, repo)
    if user is None:
        return
    today = local_today(settings.timezone)
    if user.last_completed_at == today:
        await message.answer(texts.ALREADY_DONE_TODAY)
        return
    await send_workout(bot, user, repo, content, today)


@router.callback_query(kb.DoneCb.filter())
async def on_done(
    callback: CallbackQuery,
    callback_data: kb.DoneCb,
    bot: Bot,
    repo: Repo,
    content: Content,
    settings: Settings,
) -> None:
    async with repo.lock:
        user = await load_user(callback, repo)
        if user is None:
            return
        today = local_today(settings.timezone)
        if user.last_completed_at == today:
            await callback.answer(texts.ALREADY_DONE_TODAY, show_alert=True)
            return
        if callback_data.day != today.isoformat():
            await callback.answer(texts.STALE_REMINDER, show_alert=True)
            return

        workout = await build_today(user, repo, content, today)
        user = complete_day(user, today)
        await repo.record_completion(user, workout)

    await callback.answer("✅")
    await _drop_done_button(callback)
    await bot.send_message(user.id, texts.completed(user))
    stickers = content.stickers
    is_milestone = texts.milestone(user) is not None
    await send_sticker(
        bot, user.id, (is_milestone and stickers.milestone) or stickers.completed
    )


@router.callback_query(kb.InstructionsCb.filter())
async def on_toggle_instructions(
    callback: CallbackQuery,
    callback_data: kb.InstructionsCb,
    content: Content,
    settings: Settings,
) -> None:
    message = callback.message
    if not isinstance(message, Message):  # сообщение старше 48 часов — редактировать нельзя
        await callback.answer(texts.STALE_REMINDER, show_alert=True)
        return
    day = message.date.astimezone(ZoneInfo(settings.timezone)).date()
    workout = kb.workout_from_callback(callback_data, content, day)
    if workout is None:
        await callback.answer(texts.STALE_REMINDER, show_alert=True)
        return

    await callback.answer()
    with suppress(TelegramBadRequest):  # «message is not modified» при двойном нажатии
        await message.edit_text(
            texts.format_workout(workout, with_instructions=callback_data.show),
            reply_markup=kb.workout_kb(
                workout,
                showing_instructions=callback_data.show,
                with_done=kb.has_done_button(message.reply_markup),
            ),
        )


async def _drop_done_button(callback: CallbackQuery) -> None:
    """Убирает «Выполнил ✅», оставляя переключатель инструкций."""
    message = callback.message
    if not isinstance(message, Message) or message.reply_markup is None:
        return
    with suppress(TelegramBadRequest):
        await message.edit_reply_markup(reply_markup=kb.without_done_button(message.reply_markup))
