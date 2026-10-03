from dataclasses import replace
from datetime import date, timedelta

from bot.domain.user import User


def complete_day(user: User, today: date) -> User:
    if user.last_completed_at == today:
        raise ValueError("day already completed")
    streak = user.current_streak + 1
    return replace(
        user,
        current_streak=streak,
        best_streak=max(user.best_streak, streak),
        last_completed_at=today,
    )


def reset_if_missed(user: User, today: date) -> User:
    """Полночная проверка: стрик жив, только если сет выполнен вчера (или уже сегодня).

    Идемпотентна — повторный запуск в тот же день ничего не меняет, поэтому её можно
    безопасно вызывать и при старте бота, чтобы догнать пропущенную полночь.
    """
    if user.current_streak == 0:
        return user
    if user.last_completed_at is not None and user.last_completed_at >= today - timedelta(days=1):
        return user
    return replace(user, current_streak=0)
