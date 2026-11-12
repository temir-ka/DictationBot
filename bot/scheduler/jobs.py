import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot import texts
from bot.content.models import Content
from bot.db.repo import Repo
from bot import keyboards as kb
from bot.domain.digest import WeekSummary, week_start
from bot.domain.measurement import days_until_measurement
from bot.domain.streak import reset_if_missed
from bot.services import build_today, send_sticker, send_workout
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
    await send_workout(bot, user, repo, content, today, snooze=True)


async def evening_job(user_id: int, bot: Bot, repo: Repo, content: Content, timezone: str) -> None:
    """«Стрик под угрозой»: второе напоминание вечером, если сет за день так и не сделан."""
    user = await repo.get_user(user_id)
    if user is None or not user.evening_active:
        return
    today = local_today(timezone)
    if user.last_completed_at == today:
        return
    workout = await build_today(user, repo, content, today)
    await bot.send_message(
        user.id,
        texts.evening(user),
        reply_markup=kb.evening_kb(workout, texts.step_count(content.routine)),
    )


async def weekly_digest_job(bot: Bot, repo: Repo, timezone: str) -> None:
    """Воскресная сводка: сколько сетов за неделю, стрик, сколько до замера."""
    today = local_today(timezone)
    start = week_start(today)
    for user in await repo.list_users():
        summary = WeekSummary(
            start=start,
            end=today,
            done=await repo.count_completions(user.id, start, today),
            done_today=user.last_completed_at == today,
        )
        try:
            await bot.send_message(
                user.id, texts.weekly_digest(user, summary, days_until_measurement(user, today))
            )
        except TelegramAPIError:
            log.exception("Failed to send weekly digest to user %s", user.id)


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
