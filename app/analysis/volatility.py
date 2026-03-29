from __future__ import annotations

import numpy as np
import pandas as pd

from app.clients.massive_client import MassiveClient


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
        bars = self.massive.get_underlying_bars(symbol, timespan="day", limit=756)
        df = self._bars_to_frame(bars)
        if df.empty:
            return 0.0
        weekly = df["ret"].rolling(5).std() * np.sqrt(252)
        current = float(weekly.iloc[-1])
        hist = weekly.dropna().to_numpy()
        if len(hist) == 0:
            return 0.0
        percentile = float((hist < current).mean())
        return round(percentile, 4)
