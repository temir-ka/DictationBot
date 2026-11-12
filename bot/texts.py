"""Все тексты бота. Разметка — HTML (parse_mode задан у Bot по умолчанию)."""

import html
import random
from datetime import date

from aiogram.types import BotCommand

from bot.content.models import ControlText, RoutineBlock
from bot.domain.digest import WeekSummary
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
    BotCommand(command="evening", description="Вечернее напоминание"),
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


def hhmm(user: User, field: str = "reminder_time") -> str:
    value = getattr(user, field)
    return value.strftime("%H:%M") if value else "—"


# --- общие ---

NEED_START = "👋 Сначала зарегистрируйся: /start"
CANCELLED = "👌 Ок, отменил."
NOTHING_TO_CANCEL = "🤷 Отменять нечего."

WELCOME = (
    "👋 Привет! Я помогу каждый день тренировать дикцию.\n\n"
    "🗓 Каждый день — короткий сет минут на 12: дыхание, разминка, согласные, окончания "
    "и чтение вслух.\n"
    "📏 Раз в 2 недели — замер: читаешь один и тот же контрольный текст и записываешь "
    "голосовое, а я присылаю твой первый замер — чтобы слышать прогресс.\n\n"
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
    "🌙 /evening — вечернее напоминание, если сет не сделан\n"
    "✖️ /cancel — прервать текущий диалог\n\n"
    "Пропустил день — стрик обнуляется. Больше ничего не сгорает 😌"
)


def registered(user: User) -> str:
    lines = [f"🎉 Готово! Напоминание — каждый день в {hhmm(user)}."]
    if user.evening_active:
        lines.append(f"🌙 Если к {hhmm(user, 'evening_time')} сет не сделан — напомню ещё раз (/evening).")
    lines += ["", "Перед стартом стоит записать стартовый замер — потом будет с чем сравнить."]
    return "\n".join(lines)


def welcome_back(user: User) -> str:
    return (
        f"👋 С возвращением! 🔥 Стрик: {days(user.current_streak)}.\n\n"
        "Сет на сегодня: /today, все команды: /help"
    )


# --- сет ---

ALREADY_DONE_TODAY = "✅ Сегодня уже выполнено! Следующий сет — завтра 🌙"
STALE_REMINDER = "⏳ Это сет за другой день. Сегодняшний: /today"
NUMBERS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣")
READING_INSTRUCTIONS = (
    "Первую минуту — с карандашом или пробкой в зубах (закусить за клыки), затем без неё. "
    "Медленно и чётко, контролируй каждое слово, особенно окончания (не «Наташ», а «Наташа»)."
)


def minutes(seconds: int) -> str:
    """90 → «≈1,5 мин», 60 → «≈1 мин»: блоки короткие, точнее полминуты не нужно."""
    halves = round(seconds / 30)
    whole, half = divmod(max(halves, 1), 2)
    if not whole:
        return "≈0,5 мин"
    return f"≈{whole},5 мин" if half else f"≈{whole} мин"


def step_count(routine: list[RoutineBlock]) -> int:
    """Фиксированные блоки + чтение вслух последним шагом."""
    return len(routine) + 1


def _block(number: int, title: str, duration: str, instructions: str, material: str) -> str:
    return "\n".join(
        [
            f"{NUMBERS[number - 1]} <b>{escape(title)}</b> · {duration}",
            f"<i>{escape(instructions)}</i>",
            f"<blockquote>{material}</blockquote>",
        ]
    )


def format_step(workout: Workout, routine: list[RoutineBlock], step: int) -> str:
    """Один шаг сета (step — с нуля): шапка, блок, на последнем шаге — подсказка про кнопку."""
    total = step_count(routine)
    is_reading = step == total - 1
    if is_reading:
        block = _block(
            total, "Чтение вслух", "≈3–4 мин — главный блок",
            READING_INSTRUCTIONS, escape(workout.reading.text),
        )
    else:
        b = routine[step]
        drills = "\n".join(escape(line) for line in b.drills)
        block = _block(step + 1, b.title, minutes(b.duration_sec), b.instructions, drills)
    header = f"🎯 <b>Сет на {workout.date:%d.%m}</b> · шаг {step + 1} из {total}"
    if step == 0:
        header += " · всего ≈12 минут"
    parts = [header, block]
    if is_reading:
        parts.append("Когда закончишь — жми кнопку 👇")
    return "\n\n".join(parts)


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


SNOOZED = "⏰ Ок, напомню в {at:%H:%M}"


def evening(user: User) -> str:
    if user.current_streak:
        head = f"🌙 Сегодня ещё без тренировки — 🔥 стрик {days(user.current_streak)} под угрозой!"
    else:
        head = "🌙 Сегодня ещё без тренировки."
    return f"{head}\nХотя бы чтение вслух — это 4 минуты, и день засчитан 💪"


def weekly_digest(user: User, week: WeekSummary, days_to_measurement: int) -> str:
    lines = [f"📊 <b>Итоги недели</b> · {week.start:%d.%m}–{week.end:%d.%m}", ""]
    lines.append(f"✅ Сетов: {week.done} из {week.days}")
    lines.append(f"🔥 Стрик: {days(user.current_streak)} (лучший: {days(user.best_streak)})")
    if days_to_measurement == 0:
        lines.append("📏 Пора делать замер: /measure")
    else:
        lines.append(f"📏 До замера {days(days_to_measurement)}")
    lines.append("")
    if week.done == week.days:
        lines.append("🏆 Идеальная неделя, ни одного пропуска!")
    elif not week.done_today:
        lines.append("Сегодняшний сет ещё можно успеть 👉 /today")
    else:
        lines.append("Новая неделя — новый шанс на 7 из 7 💪")
    return "\n".join(lines)


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
    text = f"⏰ Готово, напоминание теперь в {hhmm(user)}."
    if user.evening_time and not user.evening_active:
        text += (
            f"\n🌙 Вечернее ({hhmm(user, 'evening_time')}) теперь раньше основного и приходить "
            "не будет — поменять: /evening"
        )
    return text


def evening_settings(user: User) -> str:
    if user.evening_time is None:
        current = "🌙 Вечернее напоминание выключено."
    elif user.evening_active:
        current = f"🌙 Если сет не сделан, в {hhmm(user, 'evening_time')} напомню ещё раз."
    else:
        current = (
            f"🌙 Вечернее напоминание стоит на {hhmm(user, 'evening_time')}, но это не позже "
            f"основного ({hhmm(user)}), поэтому оно не приходит."
        )
    return (
        f"{current}\n\n"
        "Напиши новое время в формате ЧЧ:ММ или «выкл», чтобы отключить. "
        "/cancel — оставить как есть."
    )


def evening_updated(user: User) -> str:
    if user.evening_time is None:
        return "🌙 Вечернее напоминание выключено. Включить снова: /evening"
    if not user.evening_active:
        return (
            f"🌙 Сохранил {hhmm(user, 'evening_time')}, но это не позже основного напоминания "
            f"({hhmm(user)}) — так оно приходить не будет."
        )
    return f"🌙 Готово, вечернее напоминание в {hhmm(user, 'evening_time')}."


BAD_EVENING_TIME = "🤔 Не понял. Напиши время в формате ЧЧ:ММ, например 21:00, или «выкл»."


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


def then_caption(m: Measurement) -> str:
    return f"🕰 Так было на первом замере, {m.date:%d.%m.%Y}. Сравни с сегодняшним 👆"


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
