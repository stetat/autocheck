from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every value is overridable by env var."""

    model_config = SettingsConfigDict(env_prefix="AUTOCHECK_", extra="ignore")

    # SQLite file. Volume-mounted in Docker so data survives restarts.
    database_url: str = "sqlite:///./data/autocheck.db"

    # Directory the scheduler watches for 1C export drops.
    feed_dir: Path = Path("./data/feeds")

    # Interval between scheduled ingest runs. 0 disables the scheduler.
    ingest_interval_seconds: int = 60

    # Allowed browser origins for the React dev server.
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
