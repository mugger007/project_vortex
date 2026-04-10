"""Volatility percentile analysis from historical returns."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
from structlog import get_logger

from app.clients.massive_client import MassiveClient
from app.clients.yfinance_client import YFinanceClient


logger = get_logger(__name__)


class VolatilityAnalyzer:
    def __init__(self, massive: MassiveClient, yfinance: YFinanceClient | None = None) -> None:
        """Create a volatility analyzer backed by Massive history and YFinance spot data."""
        self.massive = massive
        self.yfinance = yfinance or YFinanceClient()

    def _bars_to_frame(self, bars: list[dict]) -> pd.DataFrame:
        """Normalize raw Massive bars into a chronologically ordered DataFrame."""
        if not bars:
            return pd.DataFrame(columns=["t", "o", "c", "h", "l"])
        df = pd.DataFrame(bars)
        required = {"t", "o", "c", "h", "l"}
        if not required.issubset(set(df.columns)):
            return pd.DataFrame(columns=["t", "o", "c", "h", "l"])
        return df.sort_values("t").reset_index(drop=True)

    def _is_current_week(self, ts_ms: int | float) -> bool:
        """Return whether a Massive weekly bar timestamp falls in the current ISO week."""
        ts = datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=UTC)
        now = datetime.now(UTC)
        return ts.isocalendar()[:2] == now.isocalendar()[:2]

    def _weekly_volatility(self, open_price: float, close_price: float, high_price: float, low_price: float) -> float:
        """Compute a simple weekly volatility score from price range and weekly change."""
        if open_price <= 0:
            raise ValueError("weekly volatility requires open_price > 0")
        change_pct = ((close_price - open_price) / open_price) * 100.0
        range_pct = ((high_price - low_price) / open_price) * 100.0
        return float(np.sqrt((change_pct**2) + (range_pct**2)))

    def _current_week_volatility(self, symbol: str) -> float:
        """Compute the current-week volatility using yfinance daily history and spot price."""
        history = self.yfinance.get_history(symbol, period="7d", interval="1d")
        if history.empty:
            raise ValueError(f"No yfinance daily history found for {symbol}")

        week_open = float(history["Open"].iloc[0])
        current_close = self.yfinance.get_last_price(symbol)

        week_high = float(history["High"].max())
        week_low = float(history["Low"].min())
        week_high = max(week_high, current_close)
        week_low = min(week_low, current_close)
        return self._weekly_volatility(week_open, current_close, week_high, week_low)

    def analyze(self, symbol: str) -> float:
        """Return the current week volatility percentile versus completed weekly history."""
        bars = self.massive.get_underlying_bars(symbol, timespan="week", limit=100)
        logger.info("volatility_bars_loaded", symbol=symbol, bars_count=len(bars))
        df = self._bars_to_frame(bars)
        if df.empty:
            message = f"No valid weekly bars returned by Massive for {symbol}"
            logger.error("volatility_empty_frame", symbol=symbol, error=message)
            raise ValueError(message)

        completed = df[~df["t"].apply(self._is_current_week)].copy()
        if completed.empty:
            message = f"No completed weekly bars available for {symbol}"
            logger.error("volatility_no_completed_weeks", symbol=symbol, error=message)
            raise ValueError(message)

        completed["weekly_vol"] = completed.apply(
            lambda row: self._weekly_volatility(float(row["o"]), float(row["c"]), float(row["h"]), float(row["l"])),
            axis=1,
        )
        hist = completed["weekly_vol"].dropna().to_numpy()
        if len(hist) == 0:
            message = f"Unable to compute historical weekly volatility for {symbol}"
            logger.error("volatility_empty_history", symbol=symbol, error=message)
            raise ValueError(message)

        current = self._current_week_volatility(symbol)
        if current <= 0:
            message = f"Current-week volatility is non-positive for {symbol}"
            logger.error("volatility_current_week_missing", symbol=symbol, error=message)
            raise ValueError(message)

        percentile = float((hist < current).mean())
        hv_percentile = round(percentile, 4)
        logger.info(
            "volatility_analyzed",
            symbol=symbol,
            current_week_volatility=current,
            hv_percentile=hv_percentile,
            samples=len(hist),
        )
        return hv_percentile

