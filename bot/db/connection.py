import logging
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)


async def connect(db_path: Path, migrations_dir: Path) -> aiosqlite.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    await migrate(conn, migrations_dir)
    return conn


async def migrate(conn: aiosqlite.Connection, migrations_dir: Path) -> None:
    """Применяет migrations/NNN_*.sql с номером больше PRAGMA user_version."""
    async with conn.execute("PRAGMA user_version") as cursor:
        (version,) = await cursor.fetchone()

    for path in sorted(migrations_dir.glob("*.sql")):
        number = int(path.name.split("_", 1)[0])
        if number <= version:
            continue
        log.info("Applying migration %s", path.name)
        script = path.read_text(encoding="utf-8")
        await conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
