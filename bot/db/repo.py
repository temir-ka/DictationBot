import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, time
from typing import Any

import aiosqlite

from bot.domain.measurement import Measurement
from bot.domain.user import User
from bot.domain.workout import History, Workout


class Repo:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn
        # Сериализует read-modify-write пользователя: кнопка, полночный крон и настройки
        # не должны перезаписывать изменения друг друга.
        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        try:
            yield
        except BaseException:
            await self._conn.rollback()
            raise
        await self._conn.commit()

    # --- users ---

    async def get_user(self, user_id: int) -> User | None:
        async with self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        return _row_to_user(row) if row else None

    async def list_users(self) -> list[User]:
        async with self._conn.execute("SELECT * FROM users") as cursor:
            return [_row_to_user(row) for row in await cursor.fetchall()]

    async def create_user(self, user: User) -> None:
        row = _user_to_row(user)
        columns = ", ".join(row)
        placeholders = ", ".join(f":{key}" for key in row)
        async with self._transaction():
            await self._conn.execute(f"INSERT INTO users ({columns}) VALUES ({placeholders})", row)

    async def save_user(self, user: User) -> None:
        async with self._transaction():
            await self._update_user(user)

    async def _update_user(self, user: User) -> None:
        row = _user_to_row(user)
        assignments = ", ".join(f"{key} = :{key}" for key in row if key != "id")
        await self._conn.execute(f"UPDATE users SET {assignments} WHERE id = :id", row)

    # --- completions ---

    async def record_completion(self, user: User, workout: Workout) -> None:
        """Сохраняет выполнение и обновлённого пользователя одной транзакцией."""
        async with self._transaction():
            await self._conn.execute(
                "INSERT INTO completions (user_id, date, exercise_ids, twister_id, reading_text_id)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    user.id,
                    workout.date.isoformat(),
                    json.dumps([e.id for e in workout.exercises]),
                    workout.twister.id,
                    workout.reading.id,
                ),
            )
            await self._update_user(user)

    async def workout_history(self, user_id: int, before: date) -> History:
        async with self._conn.execute(
            "SELECT exercise_ids, twister_id, reading_text_id FROM completions"
            " WHERE user_id = ? AND date < ? ORDER BY date",
            (user_id, before.isoformat()),
        ) as cursor:
            rows = await cursor.fetchall()
        if not rows:
            return History()
        return History(
            last_exercise_ids=frozenset(json.loads(rows[-1]["exercise_ids"])),
            twister_ids=tuple(row["twister_id"] for row in rows),
            reading_ids=tuple(row["reading_text_id"] for row in rows),
        )

    # --- measurements ---

    async def add_measurement(self, measurement: Measurement, user: User) -> int:
        async with self._transaction():
            cursor = await self._conn.execute(
                "INSERT INTO measurements (user_id, date, control_text_id, twister_ids,"
                " voice_precise_file_id, voice_casual_file_id, notes)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    measurement.user_id,
                    measurement.date.isoformat(),
                    measurement.control_text_id,
                    json.dumps(list(measurement.twister_ids)),
                    measurement.voice_precise_file_id,
                    measurement.voice_casual_file_id,
                    measurement.notes,
                ),
            )
            await self._update_user(user)
        return cursor.lastrowid

    async def list_measurements(self, user_id: int) -> list[Measurement]:
        async with self._conn.execute(
            "SELECT * FROM measurements WHERE user_id = ? ORDER BY id", (user_id,)
        ) as cursor:
            return [_row_to_measurement(row) for row in await cursor.fetchall()]

    async def last_measurement(self, user_id: int) -> Measurement | None:
        async with self._conn.execute(
            "SELECT * FROM measurements WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return _row_to_measurement(row) if row else None


def _dump_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _load_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _user_to_row(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "current_streak": user.current_streak,
        "best_streak": user.best_streak,
        "last_completed_at": _dump_date(user.last_completed_at),
        "reminder_time": user.reminder_time.strftime("%H:%M"),
        "last_measurement_at": _dump_date(user.last_measurement_at),
    }


def _row_to_user(row: aiosqlite.Row) -> User:
    return User(
        id=row["id"],
        reminder_time=time.fromisoformat(row["reminder_time"]),
        current_streak=row["current_streak"],
        best_streak=row["best_streak"],
        last_completed_at=_load_date(row["last_completed_at"]),
        last_measurement_at=_load_date(row["last_measurement_at"]),
    )


def _row_to_measurement(row: aiosqlite.Row) -> Measurement:
    return Measurement(
        id=row["id"],
        user_id=row["user_id"],
        date=date.fromisoformat(row["date"]),
        control_text_id=row["control_text_id"],
        twister_ids=tuple(json.loads(row["twister_ids"])),
        voice_precise_file_id=row["voice_precise_file_id"],
        voice_casual_file_id=row["voice_casual_file_id"],
        notes=row["notes"],
    )
