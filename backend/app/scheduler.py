"""Trigger 1 of 2: scheduled ingest.

Deliberately thin -- it opens a session and calls the same ingest service the
webhook calls. No parsing or upsert logic lives here.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from app.config import settings
from app.db import engine
from app.services.ingest import ingest_directory

logger = logging.getLogger(__name__)


def scheduled_ingest() -> None:
    try:
        with Session(engine, expire_on_commit=False) as session:
            runs = ingest_directory(session, settings.feed_dir, trigger="scheduled")
            # Read the summaries while the session is still open. Each commit
            # expires every instance in the session, so a run object read after
            # the session closes raises DetachedInstanceError -- which the
            # except below would then report as a bogus ingest failure.
            summaries = [
                (r.source_file, r.created, r.updated, r.skipped, r.duration_ms)
                for r in runs
            ]

        for source_file, created, updated, skipped, duration_ms in summaries:
            logger.info(
                "scheduled ingest %s: created=%d updated=%d skipped=%d in %dms",
                source_file, created, updated, skipped, duration_ms,
            )
        if not summaries:
            logger.debug("scheduled ingest: no new feeds in %s", settings.feed_dir)
    except Exception:
        # A scheduler thread that raises kills the job silently; log and survive.
        logger.exception("scheduled ingest failed")


def start_scheduler() -> BackgroundScheduler | None:
    """Start the interval job. Returns None when disabled (interval <= 0)."""
    if settings.ingest_interval_seconds <= 0:
        logger.info("scheduler disabled (AUTOCHECK_INGEST_INTERVAL_SECONDS=0)")
        return None

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        scheduled_ingest,
        trigger="interval",
        seconds=settings.ingest_interval_seconds,
        id="ingest-1c-feeds",
        # If a run overruns the interval, skip rather than pile up concurrent runs.
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("scheduler started: every %ds", settings.ingest_interval_seconds)
    return scheduler
