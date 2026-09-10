from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Vehicle(SQLModel, table=True):
    """A car from a partner dealership feed.

    `vin` is the natural key. The UNIQUE constraint is what actually prevents
    duplicates -- the upsert relies on the database enforcing it, not on the
    application remembering to check first.
    """

    __tablename__ = "vehicles"

    id: int | None = Field(default=None, primary_key=True)
    vin: str = Field(unique=True, index=True, max_length=17)

    brand: str
    model: str
    year: int
    mileage_km: int
    price_kzt: int
    color: str | None = None
    body_type: str | None = None
    transmission: str | None = None
    engine_volume_l: float | None = None

    defects: str | None = None
    dealer_name: str
    dealer_city: str | None = None

    # When the dealership's 1C exported this row.
    exported_at: datetime | None = None

    first_seen_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)


class IngestRun(SQLModel, table=True):
    """Audit row written for every ingest attempt, scheduled or forced."""

    __tablename__ = "ingest_runs"

    id: int | None = Field(default=None, primary_key=True)
    trigger: str  # "scheduled" | "webhook" | "upload"
    source_file: str | None = None

    # Identity of the consumed file, so a sweep can tell "already done" from
    # "changed since". Stored as a raw epoch float rather than a datetime to
    # keep equality exact across the SQLite round-trip. Null for uploads.
    source_mtime: float | None = None
    source_size: int | None = None

    rows_total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0

    errors: str | None = None  # JSON list of per-row rejection reasons
    duration_ms: int = 0
    started_at: datetime = Field(default_factory=utcnow)
    ok: bool = True
