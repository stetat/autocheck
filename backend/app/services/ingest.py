"""Ingest service: load a feed, parse it, upsert it into the database.

This is the single ingest path. Both triggers -- the scheduled job and the
forced webhook -- are thin callers of `ingest_bytes`. Parsing logic is never
duplicated per trigger.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from app.models import IngestRun, Vehicle
from app.parsers.csv_1c import VehicleRecord, parse_feed

# SQLite allows a limited number of bound parameters per statement; chunking the
# upsert keeps large feeds within it.
CHUNK_SIZE = 200

# Fields refreshed from the feed on every ingest. `first_seen_at` is deliberately
# absent: it records when we first saw the car and must survive later updates.
UPDATABLE_FIELDS = (
    "brand", "model", "year", "mileage_km", "price_kzt", "color", "body_type",
    "transmission", "engine_volume_l", "defects", "dealer_name", "dealer_city",
    "exported_at", "last_seen_at",
)


def deduplicate(records: list[VehicleRecord]) -> list[VehicleRecord]:
    """Collapse repeated VINs within one file, last occurrence winning.

    Needed because ON CONFLICT cannot resolve a conflict against a row inserted
    by the same statement -- SQLite raises instead.
    """
    by_vin: dict[str, VehicleRecord] = {}
    for record in records:
        by_vin[record.vin] = record
    return list(by_vin.values())


def existing_vins(session: Session, vins: list[str]) -> set[str]:
    found: set[str] = set()
    for start in range(0, len(vins), CHUNK_SIZE):
        chunk = vins[start : start + CHUNK_SIZE]
        found.update(session.exec(select(Vehicle.vin).where(Vehicle.vin.in_(chunk))).all())
    return found


def upsert_vehicles(session: Session, records: list[VehicleRecord], now: datetime) -> None:
    """Insert new cars and update known ones in one statement per chunk.

    The no-duplicates guarantee comes from the UNIQUE constraint on `vin` plus
    ON CONFLICT -- not from application-side checking, which would race.
    """
    rows = [
        {**record.model_dump(), "first_seen_at": now, "last_seen_at": now}
        for record in records
    ]

    for start in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[start : start + CHUNK_SIZE]
        stmt = sqlite_insert(Vehicle).values(chunk)
        session.exec(
            stmt.on_conflict_do_update(
                index_elements=[Vehicle.vin],
                set_={field: getattr(stmt.excluded, field) for field in UPDATABLE_FIELDS},
            )
        )


def ingest_bytes(
    session: Session,
    data: bytes,
    *,
    trigger: str,
    source_file: str | None = None,
    source_mtime: float | None = None,
    source_size: int | None = None,
) -> IngestRun:
    """Parse `data` and upsert it. Returns the persisted audit row."""
    started = time.perf_counter()
    now = datetime.now(timezone.utc)

    parsed = parse_feed(data)
    records = deduplicate(parsed.records)

    already_known = existing_vins(session, [r.vin for r in records])
    updated = sum(1 for r in records if r.vin in already_known)

    upsert_vehicles(session, records, now)

    run = IngestRun(
        trigger=trigger,
        source_file=source_file,
        source_mtime=source_mtime,
        source_size=source_size,
        rows_total=len(parsed.records) + len(parsed.errors),
        created=len(records) - updated,
        updated=updated,
        skipped=len(parsed.errors),
        errors=json.dumps(
            [e.model_dump() for e in parsed.errors], ensure_ascii=False
        ) if parsed.errors else None,
        duration_ms=int((time.perf_counter() - started) * 1000),
        started_at=now,
        ok=True,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def ingest_file(session: Session, path: Path, *, trigger: str) -> IngestRun:
    stat = path.stat()
    return ingest_bytes(
        session,
        path.read_bytes(),
        trigger=trigger,
        source_file=path.name,
        source_mtime=stat.st_mtime,
        source_size=stat.st_size,
    )


def processed_files(session: Session) -> set[tuple[str, float, int]]:
    """Identities of files already ingested successfully.

    Only successful runs count, so a transient failure does not blacklist a feed
    forever.
    """
    rows = session.exec(
        select(IngestRun.source_file, IngestRun.source_mtime, IngestRun.source_size).where(
            IngestRun.ok == True,  # noqa: E712 -- SQLAlchemy needs the comparison, not `is`
            IngestRun.source_file != None,  # noqa: E711
            IngestRun.source_mtime != None,  # noqa: E711
        )
    ).all()
    return {(name, mtime, size) for name, mtime, size in rows}


def ingest_directory(
    session: Session,
    directory: Path,
    *,
    trigger: str,
    skip_unchanged: bool = True,
) -> list[IngestRun]:
    """Ingest the CSVs in `directory`, oldest first, skipping unchanged files.

    Ordered by mtime rather than filename: a later export must apply on top of
    an earlier one, and filename order gets that wrong as soon as a partner
    reaches ten files ("feed_day10" sorts before "feed_day2").

    Unchanged files are skipped so a 60-second interval costs the new drops
    rather than the whole history, and so the run log stays free of no-op rows.
    Pass skip_unchanged=False to force a full reprocess.
    """
    if not directory.exists():
        return []

    candidates = sorted(
        (p for p in directory.glob("*.csv") if p.is_file()),
        key=lambda p: (p.stat().st_mtime, p.name),
    )

    if skip_unchanged:
        done = processed_files(session)
        candidates = [
            p for p in candidates
            if (p.name, p.stat().st_mtime, p.stat().st_size) not in done
        ]

    return [ingest_file(session, path, trigger=trigger) for path in candidates]
