"""Upsert tests -- the bonus requirement.

These run against a real in-memory SQLite database because the no-duplicates
guarantee is enforced by a UNIQUE constraint, not by application code. Mocking
the session here would assert nothing.
"""

from sqlmodel import Session, select

from app.models import IngestRun, Vehicle
from app.services.ingest import ingest_bytes
from tests.conftest import make_feed

VIN = "XW8ZZZ61ZJG000001"


def count_vehicles(session: Session) -> int:
    return len(session.exec(select(Vehicle)).all())


def test_ingesting_the_same_vin_twice_creates_one_row(session: Session):
    """The headline guarantee: re-ingesting a feed must not duplicate cars."""
    feed = make_feed({"VIN": VIN})

    ingest_bytes(session, feed, trigger="webhook")
    ingest_bytes(session, feed, trigger="webhook")

    assert count_vehicles(session) == 1


def test_second_ingest_updates_changed_fields(session: Session):
    ingest_bytes(session, make_feed({"VIN": VIN, "Пробег": "120500", "Цена": "14200000"}), trigger="webhook")
    ingest_bytes(session, make_feed({"VIN": VIN, "Пробег": "131900", "Цена": "13500000"}), trigger="webhook")

    car = session.exec(select(Vehicle).where(Vehicle.vin == VIN)).one()
    assert car.mileage_km == 131900
    assert car.price_kzt == 13_500_000


def test_duplicate_vin_within_a_single_file_collapses_to_one_row(session: Session):
    """1C exports are not guaranteed to be deduplicated. The last occurrence wins."""
    feed = make_feed(
        {"VIN": VIN, "Пробег": "100000"},
        {"VIN": VIN, "Пробег": "100500"},
    )

    ingest_bytes(session, feed, trigger="webhook")

    car = session.exec(select(Vehicle).where(Vehicle.vin == VIN)).one()
    assert count_vehicles(session) == 1
    assert car.mileage_km == 100500


def test_run_counts_distinguish_created_from_updated(session: Session):
    first = ingest_bytes(session, make_feed({"VIN": VIN}), trigger="webhook")
    second = ingest_bytes(
        session,
        make_feed({"VIN": VIN}, {"VIN": "XW8ZZZ61ZJG000002"}),
        trigger="webhook",
    )

    assert (first.created, first.updated) == (1, 0)
    assert (second.created, second.updated) == (1, 1)


def test_first_seen_is_preserved_while_last_seen_advances(session: Session):
    ingest_bytes(session, make_feed({"VIN": VIN}), trigger="webhook")
    original = session.exec(select(Vehicle).where(Vehicle.vin == VIN)).one()
    first_seen = original.first_seen_at

    ingest_bytes(session, make_feed({"VIN": VIN, "Пробег": "999999"}), trigger="scheduled")

    session.refresh(original)
    assert original.first_seen_at == first_seen
    assert original.last_seen_at >= first_seen


def test_malformed_rows_are_counted_as_skipped_not_ingested(session: Session):
    feed = make_feed({"VIN": VIN}, {"VIN": ""})

    run = ingest_bytes(session, feed, trigger="webhook")

    assert run.created == 1
    assert run.skipped == 1
    assert count_vehicles(session) == 1


def test_every_ingest_writes_an_audit_row(session: Session):
    ingest_bytes(session, make_feed({"VIN": VIN}), trigger="scheduled", source_file="feed_day1.csv")

    run = session.exec(select(IngestRun)).one()
    assert run.trigger == "scheduled"
    assert run.source_file == "feed_day1.csv"
    assert run.rows_total == 1
    assert run.ok is True
