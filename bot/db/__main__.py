"""Создать или обновить схему БД без запуска бота: python -m bot.db"""

import asyncio

from bot.config import Settings
from bot.db.connection import connect


async def main() -> None:
    settings = Settings()
    conn = await connect(settings.db_path, settings.migrations_dir)
    await conn.close()
    print(f"БД готова: {settings.db_path}")


if __name__ == "__main__":
    asyncio.run(main())
