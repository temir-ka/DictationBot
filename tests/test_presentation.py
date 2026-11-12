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


def steps(content, workout) -> list[str]:
    total = texts.step_count(content.routine)
    return [texts.format_step(workout, content.routine, i) for i in range(total)]


def test_routine_is_fixed_and_in_order(content):
    assert [b.id for b in content.routine] == ["breathing", "warmup", "consonants", "endings"]


def test_five_steps_one_block_each(content, workout):
    titles = ["Дыхание", "Разминка", "Согласные", "Окончания", "Чтение вслух"]
    all_steps = steps(content, workout)
    assert len(all_steps) == 5
    for i, text in enumerate(all_steps):
        assert f"шаг {i + 1} из 5" in text
        shown = [t for t in titles if f"<b>{t}</b>" in text]
        assert shown == [titles[i]]


def test_block_shows_instructions_and_drills_as_quote(content, workout):
    for block, text in zip(content.routine, steps(content, workout)):
        assert f"<i>{texts.escape(block.instructions)}</i>" in text
        drills = "\n".join(texts.escape(line) for line in block.drills)
        assert f"<blockquote>{drills}</blockquote>" in text


def test_reading_is_last_step(content, workout):
    *first, last = steps(content, workout)
    assert f"<blockquote>{texts.escape(workout.reading.text)}</blockquote>" in last
    assert last.endswith("жми кнопку 👇")
    assert all(workout.reading.text[:30] not in t for t in first)


def test_old_blocks_are_gone(content, workout):
    for text in steps(content, workout):
        for removed in ("Пересказ", "тпру", "Скороговорка"):
            assert removed not in text


def test_steps_fit_telegram_limit(content):
    longest = max(content.reading_texts, key=lambda t: len(t.text))
    workout = Workout(date=TODAY, reading=longest)
    assert all(len(t) < 4096 for t in steps(content, workout))


def _buttons(markup):
    return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]


def test_first_step_buttons(workout):
    buttons = _buttons(kb.step_kb(workout, 0, 5))
    assert [t for t, _ in buttons] == ["Дальше ▶️", "⏩ Нет времени — сразу к чтению"]
    assert kb.StepCb.unpack(buttons[0][1]).step == 1
    assert kb.StepCb.unpack(buttons[1][1]).step == 4


def test_middle_step_buttons(workout):
    buttons = _buttons(kb.step_kb(workout, 2, 5))
    assert [t for t, _ in buttons] == ["◀️ Назад", "Дальше ▶️"]
    assert [kb.StepCb.unpack(d).step for _, d in buttons] == [1, 3]


def test_last_step_has_done(workout):
    buttons = _buttons(kb.step_kb(workout, 4, 5))
    assert [t for t, _ in buttons] == ["◀️ Назад", "Выполнил ✅"]
    assert kb.DoneCb.unpack(buttons[1][1]).day == TODAY.isoformat()
    assert all(len(d.encode()) <= 64 for _, d in buttons)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(60, "≈1 мин"), (90, "≈1,5 мин"), (120, "≈2 мин"), (20, "≈0,5 мин")],
)
def test_minutes_wording(seconds, expected):
    assert texts.minutes(seconds) == expected


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
        {"blocks": [{"id": "a", "title": "A", "duration_sec": 60, "instructions": "x", "drills": []}]},
        {"blocks": [{"id": "a", "title": "A", "duration_sec": 60, "instructions": "", "drills": ["y"]}]},
        {"blocks": [{"id": "a", "title": "A", "duration_sec": 0, "instructions": "x", "drills": ["y"]}]},
        {"blocks": [{"id": "a", "title": "A", "duration_sec": 60, "instructions": "x", "drills": ["y"]}] * 2},
    ],
)
def test_broken_routine_fails_at_startup(tmp_path, broken):
    _copy_content(tmp_path)
    (tmp_path / "daily_routine.json").write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ContentError, match="daily_routine.json"):
        load_content(tmp_path)
