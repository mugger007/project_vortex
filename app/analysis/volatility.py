"""Volatility percentile analysis from historical returns."""

from __future__ import annotations

import numpy as np
import pandas as pd
from structlog import get_logger

from app.clients.massive_client import MassiveClient


logger = get_logger(__name__)


class VolatilityAnalyzer:
    def __init__(self, massive: MassiveClient) -> None:
        self.massive = massive

    def _bars_to_frame(self, bars: list[dict]) -> pd.DataFrame:
        if not bars:
            return pd.DataFrame(columns=["t", "c"])
        df = pd.DataFrame(bars)
        if "c" not in df.columns:
            return pd.DataFrame(columns=["t", "c"])
        df["ret"] = np.log(df["c"] / df["c"].shift(1))
        return df.dropna()

    def analyze(self, symbol: str) -> float:
        bars = self.massive.get_underlying_bars(symbol, timespan="day", limit=730)
        logger.info("volatility_bars_loaded", symbol=symbol, bars_count=len(bars))
        df = self._bars_to_frame(bars)
        if df.empty:
            logger.warning("volatility_empty_frame", symbol=symbol)
            return 0.0
        weekly = df["ret"].rolling(5).std() * np.sqrt(252)
        current = float(weekly.iloc[-1])
        hist = weekly.dropna().to_numpy()
        if len(hist) == 0:
            logger.warning("volatility_empty_history", symbol=symbol)
            return 0.0
        percentile = float((hist < current).mean())
        hv_percentile = round(percentile, 4)
        logger.info(
            "volatility_analyzed",
            symbol=symbol,
            hv_current_annualized=current,
            hv_percentile=hv_percentile,
            samples=len(hist),
        )
        return hv_percentile

