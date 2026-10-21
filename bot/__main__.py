import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommandScopeChat
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import texts
from bot.config import Settings
from bot.content.loader import load_content
from bot.db.connection import connect
from bot.db.repo import Repo
from bot.handlers import routers
from bot.keyboards import ensure_callbacks_fit
from bot.middlewares import AccessMiddleware
from bot.scheduler.jobs import midnight_job
from bot.scheduler.setup import ReminderScheduler
from bot.timeutils import local_today


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = Settings()
    content = load_content(settings.data_dir)
    ensure_callbacks_fit(content)
    conn = await connect(settings.db_path, settings.migrations_dir)
    repo = Repo(conn)
    await repo.allow_user(settings.owner_id, None, local_today(settings.timezone))

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    reminders = ReminderScheduler(
        AsyncIOScheduler(timezone=settings.timezone),
        bot=bot,
        repo=repo,
        content=content,
        timezone=settings.timezone,
    )
    dp = Dispatcher(
        storage=MemoryStorage(),
        repo=repo,
        content=content,
        reminders=reminders,
        settings=settings,
    )
    dp.update.outer_middleware(AccessMiddleware(repo, settings.owner_id))
    dp.include_routers(*routers)

    try:
        await midnight_job(bot, repo, content, settings.timezone)  # на случай, если бот был выключен в полночь
        await reminders.start()
        await bot.set_my_commands(texts.COMMANDS)
        with suppress(TelegramBadRequest):  # владелец ещё ни разу не писал боту
            await bot.set_my_commands(
                texts.COMMANDS + texts.ADMIN_COMMANDS,
                scope=BotCommandScopeChat(chat_id=settings.owner_id),
            )
        await dp.start_polling(bot)
    finally:
        reminders.shutdown()
        await conn.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
