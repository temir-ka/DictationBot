from contextlib import suppress

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
from bot.handlers.common import load_user, remove_markup
from bot.scheduler.setup import ReminderScheduler
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
    await remove_markup(callback)
    await bot.send_message(user.id, texts.completed(user))
    stickers = content.stickers
    is_milestone = texts.milestone(user) is not None
    await send_sticker(
        bot, user.id, (is_milestone and stickers.milestone) or stickers.completed
    )


@router.callback_query(kb.StepCb.filter())
async def on_step(
    callback: CallbackQuery,
    callback_data: kb.StepCb,
    repo: Repo,
    content: Content,
    settings: Settings,
) -> None:
    """Листает шаги сета, перерисовывая то же сообщение."""
    message = callback.message
    today = local_today(settings.timezone)
    if callback_data.day != today.isoformat() or not isinstance(message, Message):
        await callback.answer(texts.STALE_REMINDER, show_alert=True)
        return
    user = await load_user(callback, repo)
    if user is None:
        return
    total = texts.step_count(content.routine)
    step = min(max(callback_data.step, 0), total - 1)
    workout = await build_today(user, repo, content, today)
    await callback.answer()
    with suppress(TelegramBadRequest):  # «message is not modified» при двойном нажатии
        await message.edit_text(
            texts.format_step(workout, content.routine, step),
            reply_markup=kb.step_kb(workout, step, total),
        )


@router.callback_query(kb.SnoozeCb.filter())
async def on_snooze(
    callback: CallbackQuery,
    callback_data: kb.SnoozeCb,
    repo: Repo,
    reminders: ReminderScheduler,
    settings: Settings,
) -> None:
    user = await load_user(callback, repo)
    if user is None:
        return
    today = local_today(settings.timezone)
    if callback_data.day != today.isoformat():
        await callback.answer(texts.STALE_REMINDER, show_alert=True)
        return
    if user.last_completed_at == today:
        await callback.answer(texts.ALREADY_DONE_TODAY, show_alert=True)
        return
    run_at = reminders.snooze(user.id)
    await callback.answer(texts.SNOOZED.format(at=run_at), show_alert=True)
    message = callback.message
    if isinstance(message, Message) and message.reply_markup is not None:
        with suppress(TelegramBadRequest):
            await message.edit_reply_markup(reply_markup=kb.without_snooze(message.reply_markup))
