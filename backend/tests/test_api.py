"""API tests: the two ingest triggers and the read endpoints.

Both triggers must go through the same ingest service; these tests assert on the
resulting database state rather than on any internal call, so a future refactor
that duplicated parsing logic per trigger would still have to keep them honest.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.main import app
from app.services.ingest import ingest_bytes
from tests.conftest import make_feed

VIN = "XW8ZZZ61ZJG000001"
VIN2 = "XW8ZZZ61ZJG000002"


@pytest.fixture
def client(session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    feed_dir = tmp_path / "feeds"
    feed_dir.mkdir()
    monkeypatch.setattr(settings, "feed_dir", feed_dir)
    # Keep the scheduler out of tests: it would race with explicit ingests.
    monkeypatch.setattr(settings, "ingest_interval_seconds", 0)

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        c.feed_dir = feed_dir  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()


# --- forced ingest (webhook) ------------------------------------------------

def test_webhook_ingests_the_watched_directory(client: TestClient):
    (client.feed_dir / "feed_day1.csv").write_bytes(make_feed({"VIN": VIN}, {"VIN": VIN2}))

    response = client.post("/api/ingest")

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 2
    assert body["trigger"] == "webhook"


def test_webhook_accepts_an_uploaded_file(client: TestClient):
    response = client.post(
        "/api/ingest",
        files={"file": ("manual.csv", make_feed({"VIN": VIN}), "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert body["trigger"] == "upload"
    assert body["source_file"] == "manual.csv"


def test_repeating_the_webhook_on_an_unchanged_directory_is_a_no_op(client: TestClient):
    """The sweep skips files it has already ingested, so a second call costs
    nothing and adds no run history."""
    (client.feed_dir / "feed.csv").write_bytes(make_feed({"VIN": VIN}))

    client.post("/api/ingest")
    second = client.post("/api/ingest").json()

    assert second["rows_total"] == 0
    assert second["created"] == 0
    assert client.get("/api/vehicles").json()["total"] == 1


def test_force_makes_the_webhook_reprocess_unchanged_feeds(client: TestClient):
    (client.feed_dir / "feed.csv").write_bytes(make_feed({"VIN": VIN}))

    client.post("/api/ingest")
    forced = client.post("/api/ingest", params={"force": True}).json()

    assert forced["updated"] == 1
    assert client.get("/api/vehicles").json()["total"] == 1, "reprocessing must not duplicate"


def test_webhook_with_no_feeds_reports_zero_rather_than_failing(client: TestClient):
    response = client.post("/api/ingest")

    assert response.status_code == 200
    assert response.json()["rows_total"] == 0


def test_uploading_a_non_csv_file_is_rejected(client: TestClient):
    response = client.post(
        "/api/ingest",
        files={"file": ("photo.png", b"\x89PNG\r\n", "image/png")},
    )

    assert response.status_code == 400


# --- vehicles listing -------------------------------------------------------

def test_vehicles_returns_ingested_cars(client: TestClient, session: Session):
    ingest_bytes(session, make_feed({"VIN": VIN}, {"VIN": VIN2}), trigger="webhook")

    body = client.get("/api/vehicles").json()

    assert body["total"] == 2
    assert {item["vin"] for item in body["items"]} == {VIN, VIN2}


def test_vehicles_can_be_searched_by_vin_fragment(client: TestClient, session: Session):
    ingest_bytes(session, make_feed({"VIN": VIN}, {"VIN": VIN2}), trigger="webhook")

    body = client.get("/api/vehicles", params={"search": "000002"}).json()

    assert [item["vin"] for item in body["items"]] == [VIN2]


def test_vehicles_can_be_searched_by_brand_or_model(client: TestClient, session: Session):
    ingest_bytes(
        session,
        make_feed({"VIN": VIN, "Марка": "Toyota"}, {"VIN": VIN2, "Марка": "Kia", "Модель": "Rio"}),
        trigger="webhook",
    )

    body = client.get("/api/vehicles", params={"search": "kia"}).json()

    assert [item["vin"] for item in body["items"]] == [VIN2]


def test_vehicles_can_be_filtered_by_brand(client: TestClient, session: Session):
    ingest_bytes(
        session,
        make_feed({"VIN": VIN, "Марка": "Toyota"}, {"VIN": VIN2, "Марка": "Kia"}),
        trigger="webhook",
    )

    body = client.get("/api/vehicles", params={"brand": "Kia"}).json()

    assert [item["vin"] for item in body["items"]] == [VIN2]


def test_vehicles_are_paginated(client: TestClient, session: Session):
    ingest_bytes(session, make_feed({"VIN": VIN}, {"VIN": VIN2}), trigger="webhook")

    body = client.get("/api/vehicles", params={"limit": 1, "offset": 0}).json()

    assert len(body["items"]) == 1
    assert body["total"] == 2  # total reflects the filter, not the page


def test_vehicles_can_be_sorted_by_mileage(client: TestClient, session: Session):
    ingest_bytes(
        session,
        make_feed({"VIN": VIN, "Пробег": "200000"}, {"VIN": VIN2, "Пробег": "10000"}),
        trigger="webhook",
    )

    body = client.get("/api/vehicles", params={"sort": "mileage_km", "order": "asc"}).json()

    assert [item["vin"] for item in body["items"]] == [VIN2, VIN]


def test_unknown_sort_field_is_rejected(client: TestClient):
    assert client.get("/api/vehicles", params={"sort": "; DROP TABLE vehicles"}).status_code == 422


def test_brands_endpoint_lists_distinct_brands(client: TestClient, session: Session):
    ingest_bytes(
        session,
        make_feed({"VIN": VIN, "Марка": "Toyota"}, {"VIN": VIN2, "Марка": "Kia"}),
        trigger="webhook",
    )

    assert client.get("/api/brands").json() == ["Kia", "Toyota"]


# --- run history ------------------------------------------------------------

def test_runs_endpoint_returns_history_newest_first(client: TestClient):
    (client.feed_dir / "feed.csv").write_bytes(make_feed({"VIN": VIN}))
    client.post("/api/ingest")
    client.post("/api/ingest", params={"force": True})

    runs = client.get("/api/runs").json()

    assert len(runs) == 2
    assert runs[0]["id"] > runs[1]["id"]


def test_run_errors_are_exposed_for_the_ui(client: TestClient):
    (client.feed_dir / "feed.csv").write_bytes(make_feed({"VIN": VIN}, {"VIN": ""}))

    body = client.post("/api/ingest").json()

    assert body["skipped"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["line"] == 3


def test_webhook_sweeps_multiple_feed_files(client: TestClient):
    """Regression guard: with more than one feed, committing the second run
    expires the first run instance. Serialising it then yields an empty dict and
    a 500. A single-file directory hides this entirely."""
    (client.feed_dir / "feed_day1.csv").write_bytes(make_feed({"VIN": VIN}))
    (client.feed_dir / "feed_day2.csv").write_bytes(make_feed({"VIN": VIN, "Пробег": "180000"}, {"VIN": VIN2}))

    response = client.post("/api/ingest")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_file"] == "feed_day1.csv, feed_day2.csv"
    assert body["rows_total"] == 3
    assert body["created"] == 2   # VIN from day1, VIN2 from day2
    assert body["updated"] == 1   # VIN seen again in day2


def test_runs_endpoint_serialises_every_run_after_a_multi_file_sweep(client: TestClient):
    (client.feed_dir / "feed_day1.csv").write_bytes(make_feed({"VIN": VIN}))
    (client.feed_dir / "feed_day2.csv").write_bytes(make_feed({"VIN": VIN2}))

    client.post("/api/ingest")
    runs = client.get("/api/runs").json()

    assert [r["source_file"] for r in runs] == ["feed_day2.csv", "feed_day1.csv"]
    assert all(r["rows_total"] == 1 for r in runs)
