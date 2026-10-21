"""Мини-админка владельца: белый список пользователей."""

import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as TgUser

from bot import keyboards as kb
from bot import texts
from bot.config import Settings
from bot.db.repo import Repo
from bot.handlers.common import remove_markup
from bot.scheduler.setup import ReminderScheduler
from bot.timeutils import local_today

log = logging.getLogger(__name__)


class IsOwner(BaseFilter):
    async def __call__(
        self, event: TelegramObject, event_from_user: TgUser | None, settings: Settings
    ) -> bool:
        return event_from_user is not None and event_from_user.id == settings.owner_id


router = Router(name="admin")
router.message.filter(IsOwner())
router.callback_query.filter(IsOwner())


def _parse_id(command: CommandObject) -> int | None:
    args = (command.args or "").strip()
    return int(args) if args.isdigit() else None


async def _fetch_name(bot: Bot, user_id: int) -> str | None:
    """Имя из Telegram; None — если человек ещё ни разу не писал боту."""
    try:
        chat = await bot.get_chat(user_id)
    except TelegramAPIError:
        return None
    return texts.display_name(chat.full_name, chat.username)


async def _grant(
    user_id: int, bot: Bot, repo: Repo, reminders: ReminderScheduler, settings: Settings
) -> str:
    name = await _fetch_name(bot, user_id)
    newly = await repo.allow_user(user_id, name, local_today(settings.timezone))
    if newly:
        # Вернули доступ уже зарегистрированному — напоминания снова нужны.
        user = await repo.get_user(user_id)
        if user is not None:
            reminders.schedule_user(user)
        try:
            await bot.send_message(user_id, texts.ACCESS_GRANTED)
        except TelegramAPIError:
            log.info("Can't notify user %s about access: they haven't started the bot", user_id)
    return texts.access_allowed(user_id, name, newly=newly)


@router.message(Command("allow"))
async def cmd_allow(
    message: Message,
    command: CommandObject,
    bot: Bot,
    repo: Repo,
    reminders: ReminderScheduler,
    settings: Settings,
) -> None:
    user_id = _parse_id(command)
    if user_id is None:
        await message.answer(texts.ALLOW_USAGE)
        return
    await message.answer(await _grant(user_id, bot, repo, reminders, settings))


@router.message(Command("deny"))
async def cmd_deny(
    message: Message,
    command: CommandObject,
    repo: Repo,
    reminders: ReminderScheduler,
    settings: Settings,
) -> None:
    user_id = _parse_id(command)
    if user_id is None:
        await message.answer(texts.DENY_USAGE)
        return
    if user_id == settings.owner_id:
        await message.answer(texts.CANT_DENY_OWNER)
        return
    existed = await repo.deny_user(user_id)
    reminders.unschedule_user(user_id)
    await message.answer(texts.access_denied(user_id, existed=existed))


@router.message(Command("users"))
async def cmd_users(message: Message, repo: Repo) -> None:
    await message.answer(texts.members(await repo.list_members()))


@router.callback_query(kb.AccessCb.filter())
async def on_access_decision(
    callback: CallbackQuery,
    callback_data: kb.AccessCb,
    bot: Bot,
    repo: Repo,
    reminders: ReminderScheduler,
    settings: Settings,
) -> None:
    await callback.answer()
    if callback_data.allow:
        result = await _grant(callback_data.user_id, bot, repo, reminders, settings)
    else:
        result = texts.ACCESS_REJECTED
    await remove_markup(callback)
    if isinstance(callback.message, Message):
        await callback.message.answer(result)
