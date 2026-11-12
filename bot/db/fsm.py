"""Хранилище FSM aiogram в SQLite: незаконченный замер не теряется при перезапуске бота."""

import json
from collections.abc import Mapping
from typing import Any

import aiosqlite
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey


class SQLiteStorage(BaseStorage):
    def __init__(self, conn: aiosqlite.Connection) -> None:
        # Своё соединение, а не общее с Repo: коммит состояния не должен зафиксировать
        # половину чужой транзакции.
        self._conn = conn
        self._closed = False

    @staticmethod
    def _key(key: StorageKey) -> str:
        parts = (key.bot_id, key.chat_id, key.user_id, key.thread_id,
                 key.business_connection_id, key.destiny)
        return ":".join("" if p is None else str(p) for p in parts)

    async def set_state(self, key: StorageKey, state: str | State | None = None) -> None:
        value = state.state if isinstance(state, State) else state
        await self._conn.execute(
            "INSERT INTO fsm (key, state) VALUES (?, ?)"
            " ON CONFLICT (key) DO UPDATE SET state = excluded.state",
            (self._key(key), value),
        )
        await self._conn.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        async with self._conn.execute("SELECT state FROM fsm WHERE key = ?", (self._key(key),)) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await self._conn.execute(
            "INSERT INTO fsm (key, data) VALUES (?, ?)"
            " ON CONFLICT (key) DO UPDATE SET data = excluded.data",
            (self._key(key), json.dumps(dict(data), ensure_ascii=False)),
        )
        await self._conn.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self._conn.execute("SELECT data FROM fsm WHERE key = ?", (self._key(key),)) as cur:
            row = await cur.fetchone()
        return json.loads(row[0]) if row else {}

    async def close(self) -> None:
        # Зовут и Dispatcher при остановке, и finally в __main__ — второй вызов ничего не делает.
        if not self._closed:
            self._closed = True
            await self._conn.close()
