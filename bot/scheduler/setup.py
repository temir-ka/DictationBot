from contextlib import suppress
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from bot.content.models import Content
from bot.db.repo import Repo
from bot.domain.user import User
from bot.scheduler.jobs import evening_job, midnight_job, reminder_job, weekly_digest_job

SNOOZE = timedelta(hours=1)
WEEKLY_DIGEST = {"day_of_week": "sun", "hour": 20, "minute": 0}


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
        self._scheduler.add_job(
            weekly_digest_job,
            CronTrigger(**WEEKLY_DIGEST, timezone=self._timezone),
            id="weekly_digest",
            kwargs={"bot": self._bot, "repo": self._repo, "timezone": self._timezone},
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=2 * 3600,
        )
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _user_kwargs(self, user_id: int) -> dict:
        return {
            "user_id": user_id,
            "bot": self._bot,
            "repo": self._repo,
            "content": self._content,
            "timezone": self._timezone,
        }

    def _daily(self, job, job_id: str, at, user_id: int) -> None:
        self._scheduler.add_job(
            job,
            CronTrigger(hour=at.hour, minute=at.minute, timezone=self._timezone),
            id=job_id,
            kwargs=self._user_kwargs(user_id),
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=3600,
        )

    def schedule_user(self, user: User) -> None:
        """Создаёт или пересоздаёт напоминания пользователя — вызывать после смены времени."""
        self._daily(reminder_job, f"reminder:{user.id}", user.reminder_time, user.id)
        if user.evening_active:
            self._daily(evening_job, f"evening:{user.id}", user.evening_time, user.id)
        else:
            self._remove(f"evening:{user.id}")

    def snooze(self, user_id: int) -> datetime:
        """Повторит утреннее напоминание через час; повторное нажатие переносит его заново."""
        run_at = datetime.now(ZoneInfo(self._timezone)) + SNOOZE
        self._scheduler.add_job(
            reminder_job,
            DateTrigger(run_date=run_at),
            id=f"snooze:{user_id}",
            kwargs=self._user_kwargs(user_id),
            replace_existing=True,
            misfire_grace_time=3600,
        )
        return run_at

    def unschedule_user(self, user_id: int) -> None:
        for prefix in ("reminder", "evening", "snooze"):
            self._remove(f"{prefix}:{user_id}")

    def _remove(self, job_id: str) -> None:
        with suppress(JobLookupError):
            self._scheduler.remove_job(job_id)
