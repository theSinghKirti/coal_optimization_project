"""APScheduler wiring for the daily UPSLDC ingestion job.

Only starts a background scheduler when SCHEDULER_ENABLED=true. The job
itself opens and closes its own DB session (it does not run inside a request
lifecycle) and never raises out of `_scheduled_job`, so a single failure
cannot crash the scheduler thread.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.scheduler.upsldc_adapter import run_ingestion

logger = logging.getLogger("codsp.scheduler")
settings = get_settings()

_scheduler: BackgroundScheduler | None = None


def _scheduled_job() -> None:
    db = SessionLocal()
    try:
        result = run_ingestion(db)
        logger.info(
            "UPSLDC ingestion run: reachable=%s downloaded=%s duplicates=%s failed=%s",
            result.source_reachable,
            result.downloaded,
            result.skipped_duplicates,
            result.failed_downloads,
        )
    except Exception:  # noqa: BLE001 - scheduler must survive any unexpected error
        logger.exception("UPSLDC scheduled ingestion job raised an unexpected error.")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info(
            "Scheduler disabled (SCHEDULER_ENABLED=false); UPSLDC ingestion will not run automatically."
        )
        return None

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _scheduled_job,
        trigger=CronTrigger(hour=settings.scheduler_cron_hour, minute=settings.scheduler_cron_minute),
        id="upsldc_variable_cost_ingestion",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "UPSLDC ingestion scheduler started (cron %02d:%02d UTC).",
        settings.scheduler_cron_hour,
        settings.scheduler_cron_minute,
    )
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
