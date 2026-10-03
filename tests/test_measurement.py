import random
from datetime import timedelta

from bot.content.models import TongueTwister
from bot.domain.measurement import (
    days_until_measurement,
    is_measurement_due,
    pick_measurement_twisters,
)
from tests.conftest import TODAY, make_user

POOL = [TongueTwister(id=f"t{i}", text="...") for i in range(6)]


def test_first_measurement_is_due_immediately():
    assert is_measurement_due(make_user(), TODAY)


def test_due_every_14_days():
    assert not is_measurement_due(make_user(last_measurement_at=TODAY - timedelta(days=13)), TODAY)
    assert is_measurement_due(make_user(last_measurement_at=TODAY - timedelta(days=14)), TODAY)
    assert days_until_measurement(make_user(last_measurement_at=TODAY - timedelta(days=4)), TODAY) == 10


def test_twisters_avoid_previous_measurement():
    previous = {"t0", "t1", "t2"}
    picked = pick_measurement_twisters(POOL, previous, random.Random(1))
    assert len(picked) == 3
    assert not {t.id for t in picked} & previous


def test_twisters_reuse_previous_when_pool_is_small():
    picked = pick_measurement_twisters(POOL[:3], {"t0", "t1"}, random.Random(1))
    assert len({t.id for t in picked}) == 3


def test_twisters_with_tiny_pool():
    assert len(pick_measurement_twisters(POOL[:1], set(), random.Random(1))) == 1
