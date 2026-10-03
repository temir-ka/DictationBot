"""Действия, общие для хендлеров и задач планировщика."""

import logging
import random
from datetime import date

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot import keyboards as kb
from bot import texts
from bot.content.models import Content
from bot.db.repo import Repo
from bot.domain.measurement import is_measurement_due
from bot.domain.user import User
from bot.domain.workout import Workout, build_workout

log = logging.getLogger(__name__)


async def build_today(user: User, repo: Repo, content: Content, today: date) -> Workout:
    history = await repo.workout_history(user.id, before=today)
    return build_workout(user.id, today, content, history)


async def send_workout(bot: Bot, user: User, repo: Repo, content: Content, today: date) -> None:
    workout = await build_today(user, repo, content, today)
    await bot.send_message(
        user.id,
        texts.format_workout(workout),
        reply_markup=kb.workout_kb(workout, showing_instructions=False, with_done=True),
    )
    if is_measurement_due(user, today):
        await bot.send_message(
            user.id, texts.MEASUREMENT_DUE, reply_markup=kb.measurement_invite_kb()
        )


async def send_sticker(bot: Bot, chat_id: int, file_ids: list[str]) -> None:
    """Случайный стикер из списка; неверный file_id не должен ломать основной сценарий."""
    if not file_ids:
        return
    try:
        await bot.send_sticker(chat_id, random.choice(file_ids))
    except TelegramAPIError:
        log.exception("Failed to send sticker")
