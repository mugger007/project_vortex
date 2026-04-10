"""CLI entrypoint for running API, scheduler, and one-shot scan modes."""

from __future__ import annotations

import argparse
import time
from datetime import datetime

import uvicorn

from app.backtest.replay import HistoricalReplayRunner, ReplayConfig
from app.config import get_settings
from app.db.session import engine
from app.logging import configure_logging
from app.models.base import Base
from app.models import entities  # noqa: F401
from app.scheduler import start_scheduler
from app.services.orchestrator import Orchestrator


def init_db() -> None:
    """Create all ORM tables for the configured database."""
    Base.metadata.create_all(bind=engine)


def main() -> None:
    """Parse CLI arguments and dispatch the requested app mode."""
    parser = argparse.ArgumentParser(description="weekly-options-scanner")
    parser.add_argument("--mode", choices=["api", "scheduler", "scan-once", "backtest"], default="api")
    parser.add_argument("--backtest-start", default="2024-01-01")
    parser.add_argument("--backtest-end", default="2024-12-31")
    parser.add_argument("--backtest-symbols", default="SPY,QQQ")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    init_db()

    if args.mode == "api":
        uvicorn.run("app.api.main:app", host=settings.api_host, port=settings.api_port, reload=False)
        return

    if args.mode == "scheduler":
        scheduler = start_scheduler()
        try:
            while True:
                time.sleep(30)
        except KeyboardInterrupt:
            scheduler.shutdown(wait=False)
        return

    if args.mode == "scan-once":
        Orchestrator().run_scan_cycle()
        return

    if args.mode == "backtest":
        runner = HistoricalReplayRunner()
        result = runner.run(
            ReplayConfig(
                start_date=datetime.fromisoformat(args.backtest_start),
                end_date=datetime.fromisoformat(args.backtest_end),
                symbols=[s.strip().upper() for s in args.backtest_symbols.split(",") if s.strip()],
            )
        )
        print(result)


if __name__ == "__main__":
    main()

