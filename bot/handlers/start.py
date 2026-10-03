from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove

from bot import keyboards as kb
from bot import texts
from bot.db.repo import Repo
from bot.domain.user import User
from bot.handlers.common import NOT_COMMAND
from bot.scheduler.setup import ReminderScheduler
from bot.timeutils import parse_time

router = Router(name="start")


class Setup(StatesGroup):
    reminder_time = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, repo: Repo) -> None:
    await state.clear()
    user = await repo.get_user(message.from_user.id)
    if user is not None:
        await message.answer(texts.welcome_back(user))
        return
    await state.set_state(Setup.reminder_time)
    await message.answer(texts.WELCOME, reply_markup=kb.time_presets_kb())


@router.message(Setup.reminder_time, NOT_COMMAND)
async def on_reminder_time(
    message: Message, state: FSMContext, repo: Repo, reminders: ReminderScheduler
) -> None:
    reminder_time = parse_time(message.text)
    if reminder_time is None:
        await message.answer(texts.BAD_TIME)
        return

    user = User(id=message.from_user.id, reminder_time=reminder_time)
    await repo.create_user(user)
    reminders.schedule_user(user)
    await state.clear()
    await message.answer(texts.registered(user), reply_markup=ReplyKeyboardRemove())
    await message.answer(texts.MEASUREMENT_DUE, reply_markup=kb.measurement_invite_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOTHING_TO_CANCEL, reply_markup=ReplyKeyboardRemove())
        return
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=ReplyKeyboardRemove())


@router.message(StateFilter(None), F.sticker)
async def on_sticker(message: Message) -> None:
    """Подсказывает file_id присланного стикера — для заполнения data/stickers.json."""
    await message.answer(texts.sticker_file_id(message.sticker.file_id))
