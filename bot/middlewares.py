import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import TelegramObject, Update
from aiogram.types import User as TgUser

from bot import keyboards as kb
from bot import texts
from bot.db.repo import Repo

log = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    """Пропускает только белый список. Чужому в личке — один запрос доступа владельцу."""

    def __init__(self, repo: Repo, owner_id: int) -> None:
        self._repo = repo
        self._owner_id = owner_id
        # Кто уже просил доступ с момента запуска: не спамим владельцу на каждое сообщение.
        self._requested: set[int] = set()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return None
        if await self._repo.is_allowed(user.id):
            return await handler(event, data)

        message = event.message if isinstance(event, Update) else None
        if (
            message is not None
            and message.chat.type == ChatType.PRIVATE
            and user.id not in self._requested
        ):
            self._requested.add(user.id)
            await self._request_access(data["bot"], user)
        return None

    async def _request_access(self, bot: Bot, user: TgUser) -> None:
        try:
            await bot.send_message(
                self._owner_id,
                texts.access_request(user.id, texts.display_name(user.full_name, user.username)),
                reply_markup=kb.access_request_kb(user.id),
            )
            await bot.send_message(user.id, texts.ACCESS_REQUESTED)
        except TelegramAPIError:
            log.exception("Failed to send access request for user %s", user.id)
