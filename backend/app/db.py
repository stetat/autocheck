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
    # expire_on_commit=False: an ingest commits once per feed file, and each
    # commit would otherwise expire every instance already loaded in the
    # session. Reading an expired IngestRun after the session closes raises
    # DetachedInstanceError; reading it while open silently yields an empty
    # model_dump. Both bit us. Run objects are read-only summaries, so keeping
    # their loaded state after commit is both safe and what callers expect.
    with Session(engine, expire_on_commit=False) as session:
        yield session
