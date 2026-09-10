import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    #
    # NoDecode is required, not decorative: without it pydantic-settings JSON-decodes
    # list fields inside the env source and raises before any validator runs, so a
    # plain comma-separated value crashed the service at startup.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: Any) -> Any:
        """Accept a comma-separated list as well as JSON.

        pydantic-settings parses list fields as JSON, so the obvious
        AUTOCHECK_CORS_ORIGINS=http://a,http://b raised SettingsError and the
        service refused to start.
        """
        if not isinstance(value, str):
            return value

        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]


settings = Settings()
