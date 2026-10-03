import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot import texts
from bot.content.models import Content
from bot.db.repo import Repo
from bot.domain.streak import reset_if_missed
from bot.services import send_sticker, send_workout
from bot.timeutils import local_today

log = logging.getLogger(__name__)


async def reminder_job(user_id: int, bot: Bot, repo: Repo, content: Content, timezone: str) -> None:
    """Ежедневное напоминание; если подошёл срок замера — вместе с ним приходит приглашение."""
    user = await repo.get_user(user_id)
    if user is None:
        return
    today = local_today(timezone)
    if user.last_completed_at == today:
        return
    await send_workout(bot, user, repo, content, today)


async def midnight_job(bot: Bot, repo: Repo, content: Content, timezone: str) -> None:
    """Обнуляет стрик, если вчера сет не был выполнен."""
    today = local_today(timezone)
    for user in await repo.list_users():
        async with repo.lock:
            current = await repo.get_user(user.id)
            if current is None:
                continue
            updated = reset_if_missed(current, today)
            if updated == current:
                continue
            await repo.save_user(updated)
        try:
            await bot.send_message(user.id, texts.streak_lost(current.current_streak))
            await send_sticker(bot, user.id, content.stickers.streak_lost)
        except TelegramAPIError:
            log.exception("Failed to notify user %s about lost streak", user.id)
