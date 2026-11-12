from datetime import timedelta

from bot import texts
from bot.domain.measurement import Measurement, days_until_measurement, is_measurement_due
from tests.conftest import TODAY, make_user
from tests.test_access import run_with_repo


def test_first_measurement_is_due_immediately():
    assert is_measurement_due(make_user(), TODAY)


def test_due_every_14_days():
    assert not is_measurement_due(make_user(last_measurement_at=TODAY - timedelta(days=13)), TODAY)
    assert is_measurement_due(make_user(last_measurement_at=TODAY - timedelta(days=14)), TODAY)
    assert days_until_measurement(make_user(last_measurement_at=TODAY - timedelta(days=4)), TODAY) == 10


def test_material_has_only_control_text(content):
    text = texts.measurement_material(content.control_text)
    assert texts.escape(content.control_text.text) in text
    assert "Скороговорк" not in text


def test_measurement_with_one_voice_round_trip(tmp_path):
    async def scenario(repo):
        user = make_user(id=1)
        await repo.create_user(user)
        m = Measurement(user_id=1, date=TODAY, control_text_id="ctrl", voice_file_id="v1", notes="ok")
        await repo.add_measurement(m, user)
        return await repo.list_measurements(1)

    [saved] = run_with_repo(tmp_path, scenario)
    assert (saved.voice_file_id, saved.notes, saved.date) == ("v1", "ok", TODAY)
