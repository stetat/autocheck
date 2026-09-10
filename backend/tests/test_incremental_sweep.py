"""Directory sweep semantics: ordering by mtime, and not reprocessing files.

Both matter because the scheduled trigger re-runs every interval. Ordering by
filename silently applies stale data over fresh once a partner passes nine
files (feed_day10 sorts before feed_day2), and reprocessing everything makes
each tick cost the whole history instead of the new drops.
"""

import os
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.models import IngestRun, Vehicle
from app.services.ingest import ingest_directory
from tests.conftest import make_feed

VIN = "XW8ZZZ61ZJG000001"
VIN2 = "XW8ZZZ61ZJG000002"


def write(path: Path, data: bytes, mtime: float) -> Path:
    path.write_bytes(data)
    os.utime(path, (mtime, mtime))
    return path


def test_files_are_applied_in_mtime_order_not_filename_order(session: Session, tmp_path: Path):
    """feed_day10 sorts before feed_day2 lexicographically. If ordering used the
    filename, day2's older mileage would land last and overwrite day10's."""
    write(tmp_path / "feed_day10.csv", make_feed({"VIN": VIN, "Пробег": "180000"}), mtime=2000)
    write(tmp_path / "feed_day2.csv", make_feed({"VIN": VIN, "Пробег": "100000"}), mtime=1000)

    runs = ingest_directory(session, tmp_path, trigger="scheduled")

    assert [r.source_file for r in runs] == ["feed_day2.csv", "feed_day10.csv"]
    car = session.exec(select(Vehicle).where(Vehicle.vin == VIN)).one()
    assert car.mileage_km == 180000, "the newest feed must win"


def test_a_second_sweep_processes_nothing_when_nothing_changed(session: Session, tmp_path: Path):
    write(tmp_path / "feed.csv", make_feed({"VIN": VIN}), mtime=1000)

    first = ingest_directory(session, tmp_path, trigger="scheduled")
    second = ingest_directory(session, tmp_path, trigger="scheduled")

    assert len(first) == 1
    assert second == [], "an unchanged directory must be a no-op"


def test_an_unchanged_sweep_writes_no_run_history(session: Session, tmp_path: Path):
    """Otherwise a 60s interval fills the run log with no-op rows."""
    write(tmp_path / "feed.csv", make_feed({"VIN": VIN}), mtime=1000)

    ingest_directory(session, tmp_path, trigger="scheduled")
    ingest_directory(session, tmp_path, trigger="scheduled")

    assert len(session.exec(select(IngestRun)).all()) == 1


def test_a_modified_file_is_reprocessed(session: Session, tmp_path: Path):
    path = tmp_path / "feed.csv"
    write(path, make_feed({"VIN": VIN, "Пробег": "100000"}), mtime=1000)
    ingest_directory(session, tmp_path, trigger="scheduled")

    write(path, make_feed({"VIN": VIN, "Пробег": "150000"}), mtime=2000)
    runs = ingest_directory(session, tmp_path, trigger="scheduled")

    assert len(runs) == 1
    car = session.exec(select(Vehicle).where(Vehicle.vin == VIN)).one()
    assert car.mileage_km == 150000


def test_a_file_rewritten_with_the_same_mtime_but_new_size_is_reprocessed(session: Session, tmp_path: Path):
    """mtime alone is forgeable by a careless partner script; size catches the
    common case of a same-second rewrite."""
    path = tmp_path / "feed.csv"
    write(path, make_feed({"VIN": VIN}), mtime=1000)
    ingest_directory(session, tmp_path, trigger="scheduled")

    write(path, make_feed({"VIN": VIN}, {"VIN": VIN2}), mtime=1000)
    runs = ingest_directory(session, tmp_path, trigger="scheduled")

    assert len(runs) == 1
    assert runs[0].created == 1


def test_only_the_newly_added_file_is_processed(session: Session, tmp_path: Path):
    write(tmp_path / "feed_day1.csv", make_feed({"VIN": VIN}), mtime=1000)
    ingest_directory(session, tmp_path, trigger="scheduled")

    write(tmp_path / "feed_day2.csv", make_feed({"VIN": VIN2}), mtime=2000)
    runs = ingest_directory(session, tmp_path, trigger="scheduled")

    assert [r.source_file for r in runs] == ["feed_day2.csv"]


def test_force_reprocesses_everything(session: Session, tmp_path: Path):
    write(tmp_path / "feed.csv", make_feed({"VIN": VIN}), mtime=1000)
    ingest_directory(session, tmp_path, trigger="scheduled")

    runs = ingest_directory(session, tmp_path, trigger="webhook", skip_unchanged=False)

    assert len(runs) == 1
    assert runs[0].updated == 1


def test_a_failed_file_is_retried_on_the_next_sweep(session: Session, tmp_path: Path):
    """Only successful runs mark a file as done, so a transient failure does not
    permanently blacklist a feed."""
    path = write(tmp_path / "feed.csv", make_feed({"VIN": VIN}), mtime=1000)
    ingest_directory(session, tmp_path, trigger="scheduled")
    run = session.exec(select(IngestRun)).one()
    run.ok = False
    session.add(run)
    session.commit()

    runs = ingest_directory(session, tmp_path, trigger="scheduled")

    assert len(runs) == 1
