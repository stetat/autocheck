from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# check_same_thread=False: FastAPI serves sync endpoints from a threadpool,
# so a connection may legitimately be touched by a different thread.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create the SQLite file and all tables. Idempotent."""
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Import for the side effect of registering tables on SQLModel.metadata.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
