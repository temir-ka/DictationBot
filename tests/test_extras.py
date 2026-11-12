"""Вечернее напоминание, «через час», сводка недели, «было → стало», FSM в SQLite."""

import asyncio
import shutil
from datetime import date, time, timedelta

import pytest
from aiogram.fsm.storage.base import StorageKey
from apscheduler.schedulers.background import BackgroundScheduler

from bot import keyboards as kb
from bot import texts
from bot.db.connection import connect
from bot.db.fsm import SQLiteStorage
from bot.domain.digest import WeekSummary, week_start
from bot.domain.measurement import Measurement
from bot.domain.streak import complete_day
from bot.domain.workout import History, build_workout
from bot.scheduler.setup import ReminderScheduler
from tests.conftest import TODAY, make_user
from tests.test_access import MIGRATIONS, run_with_repo

# --- вечернее напоминание ---


def test_evening_is_on_by_default_at_21():
    assert make_user().evening_time == time(21, 0)
    assert make_user().evening_active


@pytest.mark.parametrize(
    ("reminder", "evening", "active"),
    [(time(9), time(21), True), (time(21), time(21), False), (time(22), time(21), False), (time(9), None, False)],
)
def test_evening_only_after_main_reminder(reminder, evening, active):
    assert make_user(reminder_time=reminder, evening_time=evening).evening_active is active


def test_evening_text_mentions_streak_only_when_there_is_one():
    assert "под угрозой" in texts.evening(make_user(current_streak=12))
    assert "12 дней" in texts.evening(make_user(current_streak=12))
    assert "под угрозой" not in texts.evening(make_user(current_streak=0))


def test_evening_buttons_open_reading_or_whole_set(content):
    workout = build_workout(1, TODAY, content, History())
    buttons = [b for row in kb.evening_kb(workout, 5).inline_keyboard for b in row]
    assert [kb.StepCb.unpack(b.callback_data).step for b in buttons] == [4, 0]


def test_evening_settings_texts():
    assert "выключено" in texts.evening_settings(make_user(evening_time=None))
    assert "не приходит" in texts.evening_settings(make_user(reminder_time=time(22), evening_time=time(21)))
    assert "21:00" in texts.evening_updated(make_user())


def test_moving_main_reminder_after_evening_warns():
    assert "не будет" in texts.time_updated(make_user(reminder_time=time(22)))
    assert "/evening" not in texts.time_updated(make_user(reminder_time=time(8)))


# --- «напомни через час» ---


def test_snooze_button_only_on_reminder_first_step(content):
    workout = build_workout(1, TODAY, content, History())

    def texts_of(markup):
        return [b.text for row in markup.inline_keyboard for b in row]

    assert "⏰ Напомни через час" in texts_of(kb.step_kb(workout, 0, 5, snooze=True))
    assert "⏰ Напомни через час" not in texts_of(kb.step_kb(workout, 0, 5))
    assert "⏰ Напомни через час" not in texts_of(kb.step_kb(workout, 1, 5, snooze=True))
    stripped = kb.without_snooze(kb.step_kb(workout, 0, 5, snooze=True))
    assert texts_of(stripped) == ["Дальше ▶️", "⏩ Нет времени — сразу к чтению"]


def test_scheduler_jobs_follow_user_settings():
    # Запущенный на паузе: незапущенный APScheduler не заменяет задачи с тем же id, а копит дубли.
    jobs = BackgroundScheduler(timezone="Asia/Almaty")
    jobs.start(paused=True)
    reminders = ReminderScheduler(jobs, bot=None, repo=None, content=None, timezone="Asia/Almaty")
    reminders.schedule_user(make_user(id=7))
    assert jobs.get_job("reminder:7") and jobs.get_job("evening:7")

    reminders.schedule_user(make_user(id=7, evening_time=None))
    assert jobs.get_job("evening:7") is None

    reminders.snooze(7)
    assert jobs.get_job("snooze:7")
    reminders.schedule_user(make_user(id=7))  # повторное расписание не плодит дубли
    assert len([j for j in jobs.get_jobs() if j.id == "reminder:7"]) == 1
    reminders.unschedule_user(7)
    assert not [j for j in jobs.get_jobs() if j.id.endswith(":7")]
    jobs.shutdown(wait=False)


# --- сводка недели ---


def test_week_starts_on_monday():
    sunday = date(2026, 11, 15)
    assert week_start(sunday) == date(2026, 11, 9)
    assert week_start(date(2026, 11, 9)) == date(2026, 11, 9)


def _week(done, done_today=True):
    return WeekSummary(start=date(2026, 11, 9), end=date(2026, 11, 15), done=done, done_today=done_today)


def test_weekly_digest_texts():
    user = make_user(current_streak=12, best_streak=15)
    perfect = texts.weekly_digest(user, _week(7), 5)
    assert "7 из 7" in perfect and "Идеальная" in perfect and "До замера 5 дней" in perfect
    assert "/today" in texts.weekly_digest(user, _week(4, done_today=False), 5)
    assert "/measure" in texts.weekly_digest(user, _week(5), 0)


def test_count_completions_for_week(tmp_path, content):
    async def scenario(repo):
        user = make_user(id=1)
        await repo.create_user(user)
        for shift in (8, 3, 1, 0):  # 8 дней назад — прошлая неделя
            day = TODAY - timedelta(days=shift)
            user = complete_day(user, day)
            await repo.record_completion(user, build_workout(1, day, content, History()))
        return await repo.count_completions(1, TODAY - timedelta(days=6), TODAY)

    assert run_with_repo(tmp_path, scenario) == 3


# --- «было → стало» ---


def test_then_caption_has_date():
    m = Measurement(user_id=1, date=date(2026, 11, 14), control_text_id="c", voice_file_id="v")
    assert "14.11.2026" in texts.then_caption(m)


# --- БД ---


def test_evening_time_round_trip(tmp_path):
    async def scenario(repo):
        await repo.create_user(make_user(id=1, evening_time=None))
        await repo.create_user(make_user(id=2, evening_time=time(20, 30)))
        return (await repo.get_user(1)).evening_time, (await repo.get_user(2)).evening_time

    assert run_with_repo(tmp_path, scenario) == (None, time(20, 30))


def test_migration_from_v1_keeps_users_and_turns_evening_on(tmp_path):
    v1 = tmp_path / "v1"
    v1.mkdir()
    shutil.copy(MIGRATIONS / "001_init.sql", v1)
    db = tmp_path / "bot.db"

    async def main():
        conn = await connect(db, v1)
        await conn.execute("INSERT INTO users (id, reminder_time, current_streak) VALUES (1, '09:00', 5)")
        await conn.commit()
        await conn.close()
        conn = await connect(db, MIGRATIONS)
        async with conn.execute("SELECT current_streak, evening_time FROM users") as cur:
            row = tuple(await cur.fetchone())
        await conn.close()
        return row

    assert asyncio.run(main()) == (5, "21:00")


def test_fsm_survives_reconnect(tmp_path):
    key = StorageKey(bot_id=1, chat_id=2, user_id=2)
    db = tmp_path / "bot.db"

    async def main():
        storage = SQLiteStorage(await connect(db, MIGRATIONS))
        await storage.set_state(key, "MeasurementFlow:notes")
        await storage.update_data(key, {"voice_file_id": "v1", "note": "Привет"})
        await storage.close()
        await storage.close()  # повторный вызов безопасен

        storage = SQLiteStorage(await connect(db, MIGRATIONS))
        result = await storage.get_state(key), await storage.get_data(key)
        await storage.set_state(key, None)
        cleared = await storage.get_state(key)
        other = await storage.get_data(StorageKey(bot_id=1, chat_id=3, user_id=3))
        await storage.close()
        return result, cleared, other

    (state, data), cleared, other = asyncio.run(main())
    assert state == "MeasurementFlow:notes"
    assert data == {"voice_file_id": "v1", "note": "Привет"}
    assert cleared is None and other == {}
