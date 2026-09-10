"""Tests for feed-level (not row-level) failure modes, and for the file/directory
entry points the two triggers actually call."""

from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.models import Vehicle
from app.parsers.csv_1c import parse_feed
from app.services.ingest import ingest_directory, ingest_file
from tests.conftest import BASE_ROW, make_feed

VIN = "XW8ZZZ61ZJG000001"


def test_empty_file_is_reported_not_crashed():
    result = parse_feed(b"")

    assert result.records == []
    assert len(result.errors) == 1


def test_missing_required_column_rejects_the_whole_file():
    """A feed without a VIN column is a schema change on the partner's side, not
    a row problem -- failing the file loudly is correct."""
    feed = "Марка;Модель\r\nToyota;Camry\r\n".encode("windows-1251")

    result = parse_feed(feed)

    assert result.records == []
    assert "VIN" in result.errors[0].reason


def test_utf8_feed_is_accepted_as_well_as_cp1251():
    """Not every partner exports cp1251; UTF-8 must not become mojibake."""
    cp1251_feed = make_feed({"Марка": "Хёндэ"})
    utf8_feed = cp1251_feed.decode("windows-1251").encode("utf-8")

    assert parse_feed(utf8_feed).records[0].brand == "Хёндэ"
    assert parse_feed(cp1251_feed).records[0].brand == "Хёндэ"


def test_bom_prefixed_header_is_still_recognised():
    """Excel round-trips add a UTF-8 BOM that would otherwise hide the VIN column."""
    feed = b"\xef\xbb\xbf" + make_feed({}).decode("windows-1251").encode("utf-8")

    result = parse_feed(feed)

    assert [r.vin for r in result.records] == [VIN]


def test_ingest_file_records_the_source_filename(session: Session, tmp_path: Path):
    path = tmp_path / "feed_day1.csv"
    path.write_bytes(make_feed({"VIN": VIN}))

    run = ingest_file(session, path, trigger="scheduled")

    assert run.source_file == "feed_day1.csv"
    assert run.created == 1


def test_ingest_directory_applies_feeds_in_filename_order(session: Session, tmp_path: Path):
    """A later export must win over an earlier one, so ordering is load-bearing."""
    (tmp_path / "feed_day1.csv").write_bytes(make_feed({"VIN": VIN, "Пробег": "100000"}))
    (tmp_path / "feed_day2.csv").write_bytes(make_feed({"VIN": VIN, "Пробег": "180000"}))

    runs = ingest_directory(session, tmp_path, trigger="scheduled")

    car = session.exec(select(Vehicle).where(Vehicle.vin == VIN)).one()
    assert [r.source_file for r in runs] == ["feed_day1.csv", "feed_day2.csv"]
    assert car.mileage_km == 180000


def test_ingest_directory_on_missing_directory_is_a_no_op(session: Session, tmp_path: Path):
    assert ingest_directory(session, tmp_path / "nope", trigger="scheduled") == []


@pytest.mark.parametrize(
    "mileage,expected",
    [("120500", 120500), ("120 500", 120500), ("120\xa0500", 120500), ("120 500,00", 120500)],
)
def test_accepts_the_thousands_and_decimal_variants_1c_emits(mileage: str, expected: int):
    result = parse_feed(make_feed({"Пробег": mileage}))

    assert result.records[0].mileage_km == expected


def test_lowercase_vin_is_normalised_to_uppercase():
    result = parse_feed(make_feed({"VIN": BASE_ROW["VIN"].lower()}))

    assert result.records[0].vin == VIN
