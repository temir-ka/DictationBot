from datetime import timedelta

import pytest

from bot import keyboards as kb
from bot import texts
from bot.content.models import Exercise
from bot.domain.workout import History, build_workout
from tests.conftest import TODAY


@pytest.fixture
def workout(content):
    return build_workout(1, TODAY, content, History())


def test_groups_are_shown_jaw_lips_cheeks_tongue(content):
    for shift in range(10):
        workout = build_workout(1, TODAY + timedelta(days=shift), content, History())
        assert [e.muscle_group for e in workout.exercises] == ["jaw", "lips", "cheeks", "tongue"]


def test_compact_workout_hides_only_exercise_instructions(workout):
    text = texts.format_workout(workout)
    for exercise in workout.exercises:
        assert exercise.name in text
        assert exercise.instructions not in text
    assert workout.reading.text in text
    assert workout.twister.text in text


def test_expanded_workout_shows_instructions(workout):
    text = texts.format_workout(workout, with_instructions=True)
    for exercise in workout.exercises:
        assert exercise.instructions in text


@pytest.mark.parametrize("expanded", [False, True])
def test_finisher_goes_after_exercises_before_block_b(workout, expanded):
    text = texts.format_workout(workout, with_instructions=expanded)
    last_exercise = text.index(workout.exercises[-1].name)
    finisher = text.index("тпру-у-у")
    assert last_exercise < finisher < text.index("Б. Метод сопротивления")


def _exercise(**fields) -> Exercise:
    base = {"id": "x", "name": "X", "muscle_group": "jaw", "instructions": "..."}
    return Exercise(**base | fields)


def test_amount_wording():
    assert texts.format_amount(_exercise(mode="reps", reps=15, duration_sec=45)) == "15 повторений, ~45 сек"
    assert texts.format_amount(_exercise(mode="reps", reps=2, duration_sec=None)) == "2 повторения"
    assert texts.format_amount(_exercise(mode="continuous", reps=None, duration_sec=60)) == "выполняй 60 сек"


@pytest.mark.parametrize(
    "fields",
    [
        {"mode": "reps", "reps": None, "duration_sec": 45},
        {"mode": "continuous", "reps": 1, "duration_sec": 45},
        {"mode": "continuous", "reps": None, "duration_sec": None},
    ],
)
def test_invalid_mode_combinations(fields):
    with pytest.raises(ValueError):
        _exercise(**fields)


def test_instructions_callback_round_trip(content, workout):
    markup = kb.workout_kb(workout, showing_instructions=False, with_done=True)
    packed = markup.inline_keyboard[0][0].callback_data
    assert len(packed.encode()) <= 64
    data = kb.InstructionsCb.unpack(packed)
    assert data.show is True
    assert kb.workout_from_callback(data, content, TODAY) == workout


def test_callback_with_removed_content_is_stale(content, workout):
    data = kb.InstructionsCb(show=True, ex="ex_999,ex_001,ex_021,ex_010", tw="tw_001", rd="txt_0001")
    assert kb.workout_from_callback(data, content, TODAY) is None


def test_all_real_ids_fit_callback_limit(content):
    kb.ensure_callbacks_fit(content)


def test_too_long_ids_are_caught_at_startup(content):
    long_reading = content.reading_texts[0].model_copy(update={"id": "txt_" + "x" * 40})
    content = content.model_copy(update={"reading_texts": [long_reading]})
    with pytest.raises(ValueError):
        kb.ensure_callbacks_fit(content)


def test_done_button_is_dropped_but_toggle_stays(workout):
    markup = kb.workout_kb(workout, showing_instructions=True, with_done=True)
    assert kb.has_done_button(markup)
    stripped = kb.without_done_button(markup)
    assert not kb.has_done_button(stripped)
    assert stripped.inline_keyboard[0][0].text == "Свернуть 🔼"


@pytest.mark.parametrize("expanded", [False, True])
def test_retell_is_the_last_block(workout, expanded):
    text = texts.format_workout(workout, with_instructions=expanded)
    assert text.index("В. Скороговорка дня") < text.index("Г. Пересказ") < text.index("жми кнопку")


def test_exercises_are_numbered(workout):
    text = texts.format_workout(workout)
    positions = [text.index(n) for n in ("1️⃣", "2️⃣", "3️⃣", "4️⃣")]
    assert positions == sorted(positions)
    assert "• " not in text


def test_milestone_is_announced_only_on_round_streaks():
    from tests.conftest import make_user

    assert "неделя" in texts.completed(make_user(current_streak=7, best_streak=7))
    assert texts.milestone(make_user(current_streak=8)) is None


def test_stickers_are_optional(tmp_path, content):
    import shutil

    from bot.config import PROJECT_ROOT
    from bot.content.loader import load_content

    for name in ("articulation_exercises", "tongue_twisters", "reading_texts", "control_text"):
        shutil.copy(PROJECT_ROOT / "data" / f"{name}.json", tmp_path)
    assert load_content(tmp_path).stickers.completed == []


def test_cautions_only_with_instructions(content):
    exercise = next(e for e in content.exercises if e.caution)
    assert exercise.caution not in texts.format_exercise(1, exercise, with_instructions=False)
    assert exercise.caution in texts.format_exercise(1, exercise, with_instructions=True)
