from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import texts
from bot.config import Settings
from bot.content.models import Content
from bot.db.repo import Repo
from bot.domain.streak import complete_day
from bot.handlers.common import load_user, remove_markup
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
