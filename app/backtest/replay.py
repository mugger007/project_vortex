from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class ReplayConfig:
    start_date: datetime
    end_date: datetime
    symbols: list[str]


class HistoricalReplayRunner:
    """Backtesting stub for historical replay mode.

    Intended extension points:
    - Pull historical snapshots/news/iv for each timestamp from Massive.
    - Reconstruct scanner state and cached previous snapshots.
    - Run analysis/risk/synthesis deterministically and persist metrics.
    """

    def run(self, config: ReplayConfig) -> dict:
        logger.info(
            "backtest_replay_started",
            start=config.start_date.isoformat(),
            end=config.end_date.isoformat(),
            symbols=config.symbols,
        )
        # Placeholder summary until historical feed integration is completed.
        return {
            "status": "stub",
            "start": config.start_date.isoformat(),
            "end": config.end_date.isoformat(),
            "symbols": config.symbols,
            "trades_simulated": 0,
            "message": "Backtesting engine scaffold ready; integrate historical loaders next.",
        }
