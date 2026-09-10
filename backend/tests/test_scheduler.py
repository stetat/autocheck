"""Scheduler tests.

The scheduled trigger is half the requirement, and a scheduler that silently
never fires looks identical to a working one in a smoke test -- so assert on the
job's actual next run time, not merely that a scheduler object came back.
"""

from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.config import settings
from app.models import Vehicle
from app.scheduler import scheduled_ingest, start_scheduler
from tests.conftest import make_feed

VIN = "XW8ZZZ61ZJG000001"


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    feed_dir = tmp_path / "feeds"
    feed_dir.mkdir()
    monkeypatch.setattr(settings, "feed_dir", feed_dir)
    return feed_dir


def test_scheduler_job_has_a_pending_next_run_time(monkeypatch: pytest.MonkeyPatch):
    """Regression guard: APScheduler treats next_run_time=None as 'paused', so a
    job can be registered and still never execute."""
    monkeypatch.setattr(settings, "ingest_interval_seconds", 60)

    scheduler = start_scheduler()
    try:
        job = scheduler.get_job("ingest-1c-feeds")
        assert job is not None
        assert job.next_run_time is not None, "job is registered but paused; it will never fire"
    finally:
        scheduler.shutdown(wait=False)


def test_scheduler_is_disabled_when_interval_is_zero(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "ingest_interval_seconds", 0)

    assert start_scheduler() is None


def test_scheduled_ingest_loads_feeds_from_the_watched_directory(_isolate: Path, monkeypatch):
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.scheduler.engine", engine)
    (_isolate / "feed.csv").write_bytes(make_feed({"VIN": VIN}))

    scheduled_ingest()

    with Session(engine) as session:
        assert [v.vin for v in session.exec(select(Vehicle)).all()] == [VIN]


def test_an_idle_sweep_does_not_log_at_info_level(_isolate: Path, monkeypatch, caplog):
    """The job runs every interval; a per-tick INFO line for "nothing to do"
    would bury the lines that matter."""
    import logging

    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.scheduler.engine", engine)
    (_isolate / "feed.csv").write_bytes(make_feed({"VIN": VIN}))

    scheduled_ingest()
    with caplog.at_level(logging.INFO, logger="app.scheduler"):
        scheduled_ingest()

    assert [r.getMessage() for r in caplog.records] == []


def test_scheduled_ingest_survives_a_broken_feed(_isolate: Path, monkeypatch):
    """A raising job thread dies silently in APScheduler; the service must not
    stop ingesting because one file was garbage."""
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.scheduler.engine", engine)
    (_isolate / "broken.csv").write_bytes(b"\x00\x01\x02 not a csv at all")

    scheduled_ingest()  # must not raise


def test_scheduled_ingest_completes_without_logging_an_error(_isolate: Path, monkeypatch, caplog):
    """The broad except in scheduled_ingest means a genuine bug surfaces only as
    a log line, never as a failing call. Assert the log is clean, or defects
    like DetachedInstanceError pass silently."""
    import logging

    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.scheduler.engine", engine)
    # TWO files on purpose: committing the second run expires the first run
    # object, so reading its fields after the session closes is what actually
    # raises DetachedInstanceError. A single-file directory hides the bug.
    (_isolate / "feed_day1.csv").write_bytes(make_feed({"VIN": VIN}))
    (_isolate / "feed_day2.csv").write_bytes(make_feed({"VIN": "XW8ZZZ61ZJG000002"}))

    with caplog.at_level(logging.INFO, logger="app.scheduler"):
        scheduled_ingest()

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors == [], f"scheduled ingest logged an error: {errors[0].message if errors else ''}"
    assert any("created=1" in r.getMessage() for r in caplog.records), (
        "expected a summary line reporting the counts"
    )
