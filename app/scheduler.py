from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from structlog import get_logger

from app.config import get_settings
from app.services.orchestrator import Orchestrator

logger = get_logger(__name__)


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    orchestrator = Orchestrator()
    scheduler = BackgroundScheduler(timezone="UTC")

    def run_job() -> None:
        logger.info("scheduled_scan_started", interval=settings.scan_interval_minutes)
        orchestrator.run_scan_cycle()
        logger.info("scheduled_scan_finished")

    scheduler.add_job(
        run_job,
        trigger=IntervalTrigger(minutes=settings.scan_interval_minutes),
        id="massive_polling_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
