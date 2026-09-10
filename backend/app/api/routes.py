"""HTTP surface.

The forced trigger lives here; the scheduled trigger lives in app.scheduler.
Both call app.services.ingest -- this module contains no parsing or upsert logic
of its own.
"""

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlmodel import Session, distinct, func, select

from app.config import settings
from app.db import get_session
from app.models import IngestRun, Vehicle
from app.schemas import IngestRunOut, Stats, VehicleOut, VehiclePage
from app.services.ingest import ingest_bytes, ingest_directory

router = APIRouter(prefix="/api", tags=["autocheck"])

SessionDep = Annotated[Session, Depends(get_session)]

# Whitelisted so a sort parameter can never reach SQL as free text.
SortField = Literal["last_seen_at", "price_kzt", "mileage_km", "year", "brand", "vin"]

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def merge_runs(runs: list[IngestRun], trigger: str) -> IngestRunOut:
    """Collapse a multi-file directory sweep into one summary for the caller.

    Each file still gets its own persisted IngestRun row; this is only the
    response shape.
    """
    if not runs:
        return IngestRunOut(
            trigger=trigger,
            rows_total=0,
            created=0,
            updated=0,
            skipped=0,
            duration_ms=0,
            started_at=datetime.now(timezone.utc),
            ok=True,
        )
    if len(runs) == 1:
        return IngestRunOut.from_run(runs[0])

    parts = [IngestRunOut.from_run(r) for r in runs]
    return IngestRunOut(
        id=parts[-1].id,
        trigger=trigger,
        source_file=", ".join(p.source_file for p in parts if p.source_file),
        rows_total=sum(p.rows_total for p in parts),
        created=sum(p.created for p in parts),
        updated=sum(p.updated for p in parts),
        skipped=sum(p.skipped for p in parts),
        errors=[e for p in parts for e in p.errors],
        duration_ms=sum(p.duration_ms for p in parts),
        started_at=parts[0].started_at,
        ok=all(p.ok for p in parts),
    )


@router.post("/ingest", summary="Force an ingest now")
def force_ingest(
    session: SessionDep,
    file: Annotated[UploadFile | None, File()] = None,
    force: Annotated[bool, Query(description="Reprocess feeds even if unchanged")] = False,
) -> IngestRunOut:
    """Trigger 2 of 2: forced. Ingests an uploaded file if one is supplied,
    otherwise sweeps the watched feed directory.

    The sweep skips files it has already ingested, so calling this repeatedly is
    cheap. Pass force=true to reprocess everything regardless.
    """
    if file is None:
        return merge_runs(
            ingest_directory(
                session, settings.feed_dir, trigger="webhook", skip_unchanged=not force
            ),
            "webhook",
        )

    name = file.filename or "upload.csv"
    if not name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Ожидается CSV-файл выгрузки 1С")

    data = file.file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Файл слишком большой")

    return IngestRunOut.from_run(
        ingest_bytes(session, data, trigger="upload", source_file=name)
    )


@router.get("/vehicles")
def list_vehicles(
    session: SessionDep,
    search: Annotated[str | None, Query(description="VIN, марка или модель")] = None,
    brand: str | None = None,
    sort: SortField = "last_seen_at",
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VehiclePage:
    filters = []
    if search:
        needle = f"%{search.lower()}%"
        filters.append(
            func.lower(Vehicle.vin).like(needle)
            | func.lower(Vehicle.brand).like(needle)
            | func.lower(Vehicle.model).like(needle)
        )
    if brand:
        filters.append(Vehicle.brand == brand)

    total = session.exec(select(func.count()).select_from(Vehicle).where(*filters)).one()

    column = getattr(Vehicle, sort)
    statement = (
        select(Vehicle)
        .where(*filters)
        .order_by(column.asc() if order == "asc" else column.desc())
        .limit(limit)
        .offset(offset)
    )

    return VehiclePage(
        items=[VehicleOut.model_validate(v.model_dump()) for v in session.exec(statement).all()],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/brands", summary="Distinct brands, for the filter dropdown")
def list_brands(session: SessionDep) -> list[str]:
    return list(session.exec(select(distinct(Vehicle.brand)).order_by(Vehicle.brand)).all())


@router.get("/runs", summary="Ingest history, newest first")
def list_runs(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[IngestRunOut]:
    runs = session.exec(select(IngestRun).order_by(IngestRun.id.desc()).limit(limit)).all()
    return [IngestRunOut.from_run(r) for r in runs]


@router.get("/stats")
def stats(session: SessionDep) -> Stats:
    last_run = session.exec(select(IngestRun).order_by(IngestRun.id.desc()).limit(1)).first()
    return Stats(
        vehicles=session.exec(select(func.count()).select_from(Vehicle)).one(),
        dealers=session.exec(select(func.count(distinct(Vehicle.dealer_name)))).one(),
        brands=session.exec(select(func.count(distinct(Vehicle.brand)))).one(),
        last_run=IngestRunOut.from_run(last_run) if last_run else None,
    )
