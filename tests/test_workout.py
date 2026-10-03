import random
from datetime import timedelta

from bot.content.models import MUSCLE_GROUPS, ReadingText
from bot.domain.workout import History, build_workout, pick_unused
from tests.conftest import TODAY


def test_one_exercise_per_muscle_group(content):
    workout = build_workout(1, TODAY, content, History())
    assert tuple(e.muscle_group for e in workout.exercises) == MUSCLE_GROUPS


def test_same_day_gives_same_workout(content):
    history = History(twister_ids=("tw_001",))
    assert build_workout(1, TODAY, content, history) == build_workout(1, TODAY, content, history)


def test_does_not_repeat_last_exercises(content):
    # В заглушках по 2 упражнения на группу — исключив вчерашние, выбор однозначен.
    first = build_workout(1, TODAY, content, History())
    last_ids = frozenset(e.id for e in first.exercises)
    for shift in range(1, 20):
        day = TODAY + timedelta(days=shift)
        workout = build_workout(1, day, content, History(last_exercise_ids=last_ids))
        assert not {e.id for e in workout.exercises} & last_ids


def test_repeats_exercise_when_group_has_no_alternative(content):
    lips = content.exercises_in("lips")[:1]
    others = [e for e in content.exercises if e.muscle_group != "lips"]
    content = content.model_copy(update={"exercises": lips + others})
    workout = build_workout(1, TODAY, content, History(last_exercise_ids=frozenset({lips[0].id})))
    assert lips[0] in workout.exercises


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
