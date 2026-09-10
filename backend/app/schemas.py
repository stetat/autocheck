"""Public API shapes. Kept separate from app.models so the wire format can
change without dragging the database schema along."""

from datetime import datetime

from pydantic import BaseModel

from app.models import IngestRun
from app.parsers.csv_1c import RowError


class VehicleOut(BaseModel):
    id: int
    vin: str
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
    exported_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime


class VehiclePage(BaseModel):
    items: list[VehicleOut]
    total: int  # matches the filter, not the page
    limit: int
    offset: int


class IngestRunOut(BaseModel):
    """An ingest run with its per-row rejections decoded for the UI."""

    id: int | None = None
    trigger: str
    source_file: str | None = None
    rows_total: int
    created: int
    updated: int
    skipped: int
    errors: list[RowError] = []
    duration_ms: int
    started_at: datetime
    ok: bool

    @classmethod
    def from_run(cls, run: IngestRun) -> "IngestRunOut":
        import json

        return cls(
            **run.model_dump(exclude={"errors"}),
            errors=[RowError(**e) for e in json.loads(run.errors)] if run.errors else [],
        )


class Stats(BaseModel):
    vehicles: int
    dealers: int
    brands: int
    last_run: IngestRunOut | None = None
