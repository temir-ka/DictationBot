import random

from bot.content.models import ReadingText
from bot.domain.workout import History, build_workout, pick_unused
from tests.conftest import TODAY


def test_same_day_gives_same_workout(content):
    history = History(reading_ids=(content.reading_texts[0].id,))
    assert build_workout(1, TODAY, content, history) == build_workout(1, TODAY, content, history)


POOL = [ReadingText(id=f"t{i}", text="...") for i in range(5)]


def test_pick_unused_never_repeats_within_a_round():
    rng = random.Random(1)
    used: list[str] = []
    for _ in range(len(POOL)):
        used.append(pick_unused(POOL, used, rng).id)
    assert sorted(used) == [t.id for t in POOL]


def test_pick_unused_starts_new_round_without_immediate_repeat():
    for seed in range(50):
        rng = random.Random(seed)
        used: list[str] = []
        for _ in range(len(POOL) * 3):
            used.append(pick_unused(POOL, used, rng).id)
        rounds = [used[i : i + len(POOL)] for i in range(0, len(used), len(POOL))]
        assert all(sorted(r) == [t.id for t in POOL] for r in rounds)
        assert all(a != b for a, b in zip(used, used[1:]))


def test_pick_unused_single_item_pool():
    assert pick_unused(POOL[:1], ["t0", "t0"], random.Random(1)).id == "t0"


def test_reading_follows_history(content):
    used_reading = content.reading_texts[0].id
    workout = build_workout(1, TODAY, content, History(reading_ids=(used_reading,)))
    assert workout.reading.id != used_reading
