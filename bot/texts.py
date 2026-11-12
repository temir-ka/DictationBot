"""Все тексты бота. Разметка — HTML (parse_mode задан у Bot по умолчанию)."""

import html
import random
from datetime import date

from aiogram.types import BotCommand

from bot.content.models import ControlText, RoutineBlock
from bot.domain.measurement import Measurement, days_until_measurement, is_measurement_due
from bot.domain.user import Member, User
from bot.domain.workout import Workout

def escape(text: str) -> str:
    # Кавычки в тексте сообщения экранировать не нужно — только <, > и &.
    return html.escape(text, quote=False)


COMMANDS = [
    BotCommand(command="today", description="Сет упражнений на сегодня"),
    BotCommand(command="streak", description="Текущий и лучший стрик"),
    BotCommand(command="progress", description="Замеры и голосовые"),
    BotCommand(command="measure", description="Пройти замер"),
    BotCommand(command="schedule", description="Время напоминания"),
    BotCommand(command="cancel", description="Прервать текущий диалог"),
    BotCommand(command="help", description="Список команд"),
]

# Видны только владельцу (scope его чата).
ADMIN_COMMANDS = [
    BotCommand(command="users", description="Кто имеет доступ"),
    BotCommand(command="allow", description="Дать доступ: /allow ID"),
    BotCommand(command="deny", description="Забрать доступ: /deny ID"),
]


def plural(n: int, forms: tuple[str, str, str]) -> str:
    n = abs(n) % 100
    if 10 < n < 20:
        return forms[2]
    if n % 10 == 1:
        return forms[0]
    if 2 <= n % 10 <= 4:
        return forms[1]
    return forms[2]


def days(n: int) -> str:
    return f"{n} {plural(n, ('день', 'дня', 'дней'))}"


def hhmm(user: User) -> str:
    return user.reminder_time.strftime("%H:%M")


# --- общие ---

NEED_START = "👋 Сначала зарегистрируйся: /start"
CANCELLED = "👌 Ок, отменил."
NOTHING_TO_CANCEL = "🤷 Отменять нечего."

WELCOME = (
    "👋 Привет! Я помогу каждый день тренировать дикцию.\n\n"
    "🗓 Каждый день — короткий сет минут на 12: дыхание, разминка, согласные, окончания "
    "и чтение вслух.\n"
    "📏 Раз в 2 недели — замер: читаешь один и тот же контрольный текст и записываешь "
    "голосовое, чтобы слышать прогресс.\n\n"
    "⏰ Во сколько присылать напоминание? Напиши время в формате ЧЧ:ММ, например 08:30."
)
BAD_TIME = "🤔 Не понял время. Напиши в формате ЧЧ:ММ, например 08:30."

HELP = (
    "<b>📋 Команды</b>\n"
    "🎯 /today — сет упражнений на сегодня\n"
    "🔥 /streak — текущий и лучший стрик, когда следующий замер\n"
    "📈 /progress — все замеры, можно переслушать голосовые\n"
    "📏 /measure — пройти замер (раз в 14 дней)\n"
    "⏰ /schedule — поменять время напоминания\n"
    "✖️ /cancel — прервать текущий диалог\n\n"
    "Пропустил день — стрик обнуляется. Больше ничего не сгорает 😌"
)


def registered(user: User) -> str:
    return (
        f"🎉 Готово! Напоминание — каждый день в {hhmm(user)}.\n\n"
        "Перед стартом стоит записать стартовый замер — потом будет с чем сравнить."
    )


def welcome_back(user: User) -> str:
    return (
        f"👋 С возвращением! 🔥 Стрик: {days(user.current_streak)}.\n\n"
        "Сет на сегодня: /today, все команды: /help"
    )


# --- сет ---

ALREADY_DONE_TODAY = "✅ Сегодня уже выполнено! Следующий сет — завтра 🌙"
STALE_REMINDER = "⏳ Это сет за другой день. Сегодняшний: /today"
NUMBERS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣")
NO_TIME = "Нет времени? Прочитай хотя бы блок 5 и нажми «Выполнил ✅» — день засчитан."


def minutes(seconds: int) -> str:
    """90 → «≈1,5 мин», 60 → «≈1 мин»: блоки короткие, точнее полминуты не нужно."""
    halves = round(seconds / 30)
    whole, half = divmod(max(halves, 1), 2)
    if not whole:
        return "≈0,5 мин"
    return f"≈{whole},5 мин" if half else f"≈{whole} мин"


def format_block(number: int, block: RoutineBlock) -> str:
    lines = [f"{NUMBERS[number - 1]} <b>{escape(block.title)}</b> · {minutes(block.duration_sec)}"]
    lines += [escape(line) for line in block.instructions]
    return "\n".join(lines)


def format_workout(workout: Workout, routine: list[RoutineBlock]) -> str:
    """Сет на день: фиксированные блоки из daily_routine.json и чтение вслух последним."""
    blocks = [format_block(number, block) for number, block in enumerate(routine, start=1)]
    reading = "\n".join(
        [
            f"{NUMBERS[len(routine)]} <b>Чтение вслух</b> · ≈3–4 мин — главный блок",
            "Первую минуту читай с карандашом или пробкой в зубах (закусить за клыки), затем без "
            "неё. Читай медленно и чётко, контролируй каждое слово, особенно окончания "
            "(не «Наташ», а «Наташа»).",
            f"<blockquote>{escape(workout.reading.text)}</blockquote>",
        ]
    )
    return "\n\n".join(
        [
            f"🎯 <b>Сет на {workout.date:%d.%m}</b> · ≈12 минут",
            *blocks,
            reading,
            "Когда закончишь — жми кнопку 👇",
            f"⏱ {NO_TIME}",
        ]
    )


PRAISE = (
    "✅ Сет засчитан! Отличная работа 💪",
    "✅ Готово! Ещё один шаг к чистой речи 🗣",
    "✅ Засчитано! Так держать 🙌",
    "✅ Есть! Сегодняшняя тренировка в копилке 🏦",
    "✅ Сделано! Голос скажет спасибо 🎙",
    "✅ Принято! Маленькие шаги — большой результат 🚀",
)
MILESTONES = {
    3: "🌱 Три дня подряд — привычка начинает прорастать!",
    7: "🎉 Целая неделя без пропусков!",
    14: "🎉 Две недели подряд — самое время сравнить себя на замере!",
    21: "🏅 21 день — говорят, за столько формируется привычка!",
    30: "🏆 Месяц подряд! Это уже серьёзно.",
    50: "🌟 50 дней подряд!",
    100: "💯 Сто дней подряд! Легендарно.",
    200: "👑 200 дней подряд!",
    365: "🎂 Год без пропусков! Невероятно.",
}


def milestone(user: User) -> str | None:
    return MILESTONES.get(user.current_streak)


def completed(user: User) -> str:
    lines = [
        random.choice(PRAISE),
        f"🔥 Стрик: {days(user.current_streak)} (лучший: {days(user.best_streak)})",
    ]
    if text := milestone(user):
        lines += ["", text]
    return "\n".join(lines)


def streak_lost(previous_streak: int) -> str:
    return (
        f"😕 Вчера без тренировки — стрик обнулён (был {days(previous_streak)}).\n"
        "Ничего страшного — начнём заново сегодня 💪 /today"
    )


# --- стрик ---

def streak(user: User, today: date) -> str:
    lines = [
        f"🔥 Текущий стрик: {days(user.current_streak)}",
        f"🏆 Лучший: {days(user.best_streak)}",
    ]
    if is_measurement_due(user, today):
        lines.append("📏 Пора делать замер: /measure")
    else:
        lines.append(f"📏 Следующий замер через {days(days_until_measurement(user, today))}")
    return "\n".join(lines)


# --- расписание ---

def schedule(user: User) -> str:
    return (
        f"⏰ Напоминание приходит каждый день в {hhmm(user)}.\n\n"
        "Чтобы поменять — напиши новое время в формате ЧЧ:ММ. /cancel — оставить как есть."
    )


def time_updated(user: User) -> str:
    return f"⏰ Готово, напоминание теперь в {hhmm(user)}."


# --- замеры ---

MEASUREMENT_DUE = "📏 Пора сделать замер — займёт пару минут."
MEASUREMENT_LATER = "👌 Ок. Начать замер можно в любой момент: /measure"


def measurement_not_due(user: User, today: date) -> str:
    return (
        f"⏳ До следующего замера {days(days_until_measurement(user, today))}. "
        "Я напомню, когда придёт время."
    )


def measurement_material(control: ControlText) -> str:
    return "\n".join(
        [
            "📏 <b>Замер</b>",
            "",
            "Прочитай контрольный текст и пришли голосовым 🎙",
            f"<blockquote>{escape(control.text)}</blockquote>",
            "/cancel — прервать замер",
        ]
    )


WAITING_VOICE = "Жду голосовое сообщение 🎙 (/cancel — прервать замер)"
MEASUREMENT_NOTES = (
    "👍 Записал голосовое. 📝 Хочешь добавить заметку о самочувствии или прогрессе? "
    "Напиши текстом — или нажми «Пропустить»."
)


def measurement_saved(number: int) -> str:
    return (
        f"🎉 Замер №{number} сохранён!\n"
        "🎧 Переслушать и сравнить с прошлыми: /progress\n"
        "📅 Следующий замер — через 14 дней."
    )


NO_MEASUREMENTS = "📭 Замеров пока нет. Сделай стартовый, чтобы было с чем сравнивать: /measure"
MEASUREMENT_NOT_FOUND = "🤷 Замер не найден"


def progress(measurements: list[Measurement]) -> str:
    lines = ["📈 <b>Замеры</b>", ""]
    for number, m in enumerate(measurements, start=1):
        lines.append(f"<b>№{number}</b> · {m.date:%d.%m.%Y}")
        if m.notes:
            lines.append(f"   <i>{escape(m.notes)}</i>")
    lines += ["", "🎧 Нажми на номер, чтобы переслушать голосовое."]
    return "\n".join(lines)


def voice_caption(number: int, m: Measurement) -> str:
    return f"№{number} · {m.date:%d.%m.%Y}"


def sticker_file_id(file_id: str) -> str:
    return (
        "🏷 file_id этого стикера:\n"
        f"<code>{escape(file_id)}</code>\n\n"
        "Добавь его в <code>data/stickers.json</code> в нужный список "
        "(completed, milestone, measurement_saved, streak_lost) и перезапусти бота."
    )


# --- доступ ---

ACCESS_REQUESTED = (
    "🔒 Это закрытый бот. Я отправил владельцу запрос на доступ — "
    "как только его одобрят, я тебе напишу."
)
ACCESS_GRANTED = "🎉 Доступ открыт! Жми /start, чтобы начать."
ALLOW_USAGE = "Формат: <code>/allow 123456789</code> — telegram ID (узнать можно у @userinfobot)."
DENY_USAGE = "Формат: <code>/deny 123456789</code>"
CANT_DENY_OWNER = "🙅 Владельца из списка убрать нельзя."
ACCESS_REJECTED = "🚫 Отклонено"


def display_name(full_name: str, username: str | None) -> str:
    return f"{full_name} (@{username})" if username else full_name


def _member_label(user_id: int, name: str | None) -> str:
    return f"{escape(name)} (<code>{user_id}</code>)" if name else f"<code>{user_id}</code>"


def access_request(user_id: int, name: str) -> str:
    return f"🙋 Просит доступ: {_member_label(user_id, name)}"


def access_allowed(user_id: int, name: str | None, *, newly: bool) -> str:
    if not newly:
        return f"👌 У {_member_label(user_id, name)} доступ уже был."
    return f"✅ Доступ выдан: {_member_label(user_id, name)}"


def access_denied(user_id: int, *, existed: bool) -> str:
    if not existed:
        return f"🤷 <code>{user_id}</code> и так нет в списке."
    return f"🚫 Доступ забран: <code>{user_id}</code>. Данные сохранены — /allow вернёт всё как было."


def members(items: list[Member]) -> str:
    lines = [f"<b>👥 Доступ ({len(items)})</b>"]
    for m in items:
        status = "не нажал /start" if m.current_streak is None else f"🔥 {m.current_streak}"
        lines.append(f"• {_member_label(m.id, m.name)} — {status}")
    lines.append("\nУбрать: <code>/deny ID</code>")
    return "\n".join(lines)
