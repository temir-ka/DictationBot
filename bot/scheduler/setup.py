from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.content.models import Content
from bot.db.repo import Repo
from bot.domain.user import User
from bot.scheduler.jobs import midnight_job, reminder_job


class ReminderScheduler:
    """Обёртка над APScheduler: задачи живут в памяти и пересоздаются из БД при старте."""

    def __init__(
        self, scheduler: AsyncIOScheduler, *, bot: Bot, repo: Repo, content: Content, timezone: str
    ) -> None:
        self._scheduler = scheduler
        self._bot = bot
        self._repo = repo
        self._content = content
        self._timezone = timezone

    async def start(self) -> None:
        for user in await self._repo.list_users():
            self.schedule_user(user)
        self._scheduler.add_job(
            midnight_job,
            CronTrigger(hour=0, minute=0, second=30, timezone=self._timezone),
            id="midnight",
            kwargs={
                "bot": self._bot,
                "repo": self._repo,
                "content": self._content,
                "timezone": self._timezone,
            },
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=6 * 3600,
        )
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def schedule_user(self, user: User) -> None:
        """Создаёт или пересоздаёт ежедневное напоминание — вызывать после смены времени."""
        self._scheduler.add_job(
            reminder_job,
            CronTrigger(
                hour=user.reminder_time.hour,
                minute=user.reminder_time.minute,
                timezone=self._timezone,
            ),
            id=f"reminder:{user.id}",
            kwargs={
                "user_id": user.id,
                "bot": self._bot,
                "repo": self._repo,
                "content": self._content,
                "timezone": self._timezone,
            },
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=3600,
        )
