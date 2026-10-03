from contextlib import suppress

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.db.repo import Repo
from bot.domain.user import User

# Для хендлеров текста внутри FSM: команды не должны приниматься за ответ.
NOT_COMMAND = F.text & ~F.text.startswith("/")


async def load_user(event: Message | CallbackQuery, repo: Repo) -> User | None:
    """Пользователь из БД; если он не зарегистрирован — просит сделать /start."""
    user = await repo.get_user(event.from_user.id)
    if user is None:
        if isinstance(event, CallbackQuery):
            await event.answer(texts.NEED_START, show_alert=True)
        else:
            await event.answer(texts.NEED_START)
    return user


async def remove_markup(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=None)
