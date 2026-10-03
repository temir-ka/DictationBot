from datetime import timedelta

import pytest

from bot.domain.streak import complete_day, reset_if_missed
from tests.conftest import TODAY, make_user

YESTERDAY = TODAY - timedelta(days=1)


def test_complete_day():
    user = complete_day(make_user(current_streak=4, best_streak=4), TODAY)
    assert user.current_streak == 5
    assert user.best_streak == 5
    assert user.last_completed_at == TODAY


def test_complete_day_keeps_best_streak():
    assert complete_day(make_user(current_streak=2, best_streak=10), TODAY).best_streak == 10


def test_cannot_complete_twice_a_day():
    with pytest.raises(ValueError):
        complete_day(complete_day(make_user(), TODAY), TODAY)


def test_streak_survives_if_done_yesterday():
    user = make_user(current_streak=5, last_completed_at=YESTERDAY)
    assert reset_if_missed(user, TODAY) == user


def test_streak_survives_if_already_done_today():
    user = make_user(current_streak=5, last_completed_at=TODAY)
    assert reset_if_missed(user, TODAY) == user


def test_missed_day_resets_streak_only():
    user = make_user(current_streak=5, best_streak=9, last_completed_at=YESTERDAY - timedelta(days=1))
    after = reset_if_missed(user, TODAY)
    assert after.current_streak == 0
    assert after.best_streak == 9
    assert after.last_completed_at == user.last_completed_at


def test_reset_is_idempotent():
    user = make_user(current_streak=5, last_completed_at=TODAY - timedelta(days=5))
    once = reset_if_missed(user, TODAY)
    assert reset_if_missed(once, TODAY) == once
