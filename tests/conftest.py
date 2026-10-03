from datetime import date, time

import pytest

from bot.config import PROJECT_ROOT
from bot.content.loader import load_content
from bot.content.models import Content
from bot.domain.user import User

TODAY = date(2026, 10, 1)


def make_user(**overrides) -> User:
    fields = {"id": 1, "reminder_time": time(9, 0)}
    fields.update(overrides)
    return User(**fields)


@pytest.fixture
def content() -> Content:
    return load_content(PROJECT_ROOT / "data")
