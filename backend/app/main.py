import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.routes import router
from app.config import settings
from app.db import init_db
from app.scheduler import scheduled_ingest, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Ingest once at boot so a fresh container is never an empty table.
    scheduled_ingest()
    scheduler = start_scheduler()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title="Autocheck 1C Integration",
    description=(
        "Ingests 1C export files from partner dealerships. Two triggers, one "
        "ingest path: a scheduled interval job and a forced POST /api/ingest."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


class Health(BaseModel):
    status: str
    service: str


@app.get("/api/health")
def health() -> Health:
    return Health(status="ok", service="autocheck-integration")
