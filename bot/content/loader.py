import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from bot.content.models import Content, ControlText, DailyRoutine, ReadingPool, Stickers


class ContentError(Exception):
    pass


def load_content(data_dir: Path) -> Content:
    """Читает и валидирует все JSON с контентом. Падает при старте, а не посреди дня."""
    stickers_path = data_dir / "stickers.json"
    content = Content(
        routine=_load(data_dir / "daily_routine.json", DailyRoutine).blocks,
        reading_texts=_load(data_dir / "reading_texts.json", ReadingPool).texts,
        control_text=_load(data_dir / "control_text.json", ControlText),
        stickers=_load(stickers_path, Stickers) if stickers_path.exists() else Stickers(),
    )
    _ensure_unique("daily_routine.json", [b.id for b in content.routine])
    _ensure_unique("reading_texts.json", [t.id for t in content.reading_texts])
    if not content.reading_texts:
        raise ContentError("reading_texts.json: пул текстов пуст")
    return content


def _load(path: Path, schema: Any) -> Any:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return TypeAdapter(schema).validate_python(raw)
    except FileNotFoundError as e:
        raise ContentError(f"{path.name}: файл не найден") from e
    except (json.JSONDecodeError, ValidationError) as e:
        raise ContentError(f"{path.name}: {e}") from e


def _ensure_unique(file_name: str, ids: list[str]) -> None:
    duplicates = [i for i, n in Counter(ids).items() if n > 1]
    if duplicates:
        raise ContentError(f"{file_name}: повторяющиеся id {duplicates}")
