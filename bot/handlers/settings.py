"""/schedule — смена времени напоминания."""

from dataclasses import replace

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot import texts
from bot.db.repo import Repo
from bot.handlers.common import NOT_COMMAND, load_user
from bot.scheduler.setup import ReminderScheduler
from bot.timeutils import parse_time

router = Router(name="settings")


class ScheduleEdit(StatesGroup):
    reminder_time = State()


@router.message(Command("schedule"))
async def cmd_schedule(message: Message, state: FSMContext, repo: Repo) -> None:
    user = await load_user(message, repo)
    if user is None:
        return
    await state.set_state(ScheduleEdit.reminder_time)
    await message.answer(texts.schedule(user))


@router.message(ScheduleEdit.reminder_time, NOT_COMMAND)
async def on_new_time(
    message: Message, state: FSMContext, repo: Repo, reminders: ReminderScheduler
) -> None:
    reminder_time = parse_time(message.text)
    if reminder_time is None:
        await message.answer(texts.BAD_TIME)
        return
    async with repo.lock:
        user = await load_user(message, repo)
        if user is None:
            return
        user = replace(user, reminder_time=reminder_time)
        await repo.save_user(user)
    reminders.schedule_user(user)
    await state.clear()
    await message.answer(texts.time_updated(user))
