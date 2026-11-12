import json
import shutil

import pytest

from bot import keyboards as kb
from bot import texts
from bot.config import PROJECT_ROOT
from bot.content.loader import ContentError, load_content
from bot.domain.workout import History, Workout, build_workout
from tests.conftest import TODAY, make_user

REQUIRED_FILES = ("daily_routine", "reading_texts", "control_text")


@pytest.fixture
def workout(content):
    return build_workout(1, TODAY, content, History())


@pytest.fixture
def text(content, workout):
    return texts.format_workout(workout, content.routine)


def test_routine_is_fixed_and_in_order(content):
    assert [b.id for b in content.routine] == ["breathing", "warmup", "consonants", "endings"]


def test_blocks_go_1_to_5_with_reading_last(text):
    titles = ["Дыхание", "Разминка", "Согласные", "Окончания", "Чтение вслух"]
    positions = [text.index(f"{n} <b>{t}</b>") for n, t in zip(texts.NUMBERS, titles)]
    assert positions == sorted(positions)


def test_all_instructions_are_shown_in_full(content, text, workout):
    for block in content.routine:
        for line in block.instructions:
            assert texts.escape(line) in text
    assert texts.escape(workout.reading.text) in text


def test_no_time_hint_is_the_last_line(text):
    assert text.endswith(texts.NO_TIME)


def test_old_blocks_are_gone(text):
    for removed in ("Пересказ", "тпру", "Скороговорка"):
        assert removed not in text


def test_message_fits_telegram_limit(content):
    longest = max(content.reading_texts, key=lambda t: len(t.text))
    workout = Workout(date=TODAY, reading=longest)
    assert len(texts.format_workout(workout, content.routine)) < 4096


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(60, "≈1 мин"), (90, "≈1,5 мин"), (120, "≈2 мин"), (20, "≈0,5 мин")],
)
def test_minutes_wording(seconds, expected):
    assert texts.minutes(seconds) == expected


def test_only_done_button(workout):
    markup = kb.workout_kb(workout)
    [[button]] = markup.inline_keyboard
    assert button.text == "Выполнил ✅"
    assert kb.DoneCb.unpack(button.callback_data).day == TODAY.isoformat()


def test_milestone_is_announced_only_on_round_streaks():
    assert "неделя" in texts.completed(make_user(current_streak=7, best_streak=7))
    assert texts.milestone(make_user(current_streak=8)) is None


def _copy_content(tmp_path):
    for name in REQUIRED_FILES:
        shutil.copy(PROJECT_ROOT / "data" / f"{name}.json", tmp_path)


def test_stickers_and_old_pools_are_optional(tmp_path):
    _copy_content(tmp_path)  # без stickers, articulation_exercises и tongue_twisters
    assert load_content(tmp_path).stickers.completed == []


@pytest.mark.parametrize(
    "broken",
    [
        {"blocks": []},
        {"blocks": [{"id": "a", "title": "A", "duration_sec": 60, "instructions": []}]},
        {"blocks": [{"id": "a", "title": "A", "duration_sec": 0, "instructions": ["x"]}]},
        {"blocks": [{"id": "a", "title": "A", "duration_sec": 60, "instructions": ["x"]}] * 2},
    ],
)
def test_broken_routine_fails_at_startup(tmp_path, broken):
    _copy_content(tmp_path)
    (tmp_path / "daily_routine.json").write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ContentError, match="daily_routine.json"):
        load_content(tmp_path)
