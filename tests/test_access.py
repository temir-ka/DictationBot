import asyncio
from datetime import time

from bot import texts
from bot.config import Settings
from bot.db.connection import connect
from bot.db.repo import Repo
from bot.domain.user import Member
from tests.conftest import TODAY, make_user

MIGRATIONS = Settings.model_fields["migrations_dir"].default


def run_with_repo(tmp_path, scenario):
    async def main():
        conn = await connect(tmp_path / "bot.db", MIGRATIONS)
        try:
            return await scenario(Repo(conn))
        finally:
            await conn.close()

    return asyncio.run(main())


def test_allow_and_deny(tmp_path):
    async def scenario(repo: Repo):
        assert not await repo.is_allowed(5)
        assert await repo.allow_user(5, "Аня (@anya)", TODAY) is True
        assert await repo.allow_user(5, None, TODAY) is False  # повтор не стирает имя
        assert await repo.is_allowed(5)
        members = await repo.list_members()
        assert await repo.deny_user(5) is True
        assert await repo.deny_user(5) is False
        assert not await repo.is_allowed(5)
        return members

    assert run_with_repo(tmp_path, scenario) == [
        Member(id=5, name="Аня (@anya)", added_at=TODAY, current_streak=None)
    ]


def test_denied_users_are_not_listed_for_reminders(tmp_path):
    async def scenario(repo: Repo):
        await repo.create_user(make_user(id=1))
        await repo.create_user(make_user(id=2, reminder_time=time(8, 0)))
        await repo.allow_user(1, None, TODAY)
        return [u.id for u in await repo.list_users()]

    assert run_with_repo(tmp_path, scenario) == [1]


def test_members_list_escapes_names():
    text = texts.members([Member(id=7, name="<b>x</b>", added_at=TODAY, current_streak=3)])
    assert "&lt;b&gt;x&lt;/b&gt;" in text
    assert "<code>7</code>" in text
    assert "🔥 3" in text
