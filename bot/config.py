from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str
    owner_id: int
    timezone: str = "Asia/Almaty"
    db_path: Path = PROJECT_ROOT / "var" / "bot.db"
    data_dir: Path = PROJECT_ROOT / "data"
    migrations_dir: Path = PROJECT_ROOT / "migrations"
