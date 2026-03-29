from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from app.clients.massive_client import MassiveClient


class TrendAnalyzer:
    def __init__(self, massive: MassiveClient) -> None:
        self.massive = massive

    def analyze(self, symbol: str) -> tuple[float, str]:
        bars = self.massive.get_underlying_bars(symbol, timespan="day", limit=260)
        if not bars:
            return 0.0, "No bars available"

        df = pd.DataFrame(bars)
        close = df.get("c")
        if close is None or close.empty:
            return 0.0, "Close series missing"

        df["ema_5"] = ta.ema(close, length=5)
        df["ema_20"] = ta.ema(close, length=20)
        df["sma_200"] = ta.sma(close, length=200)
        df["mom_20"] = ta.mom(close, length=20)
        last = df.iloc[-1]

        score = 50.0
        if last["ema_5"] > last["ema_20"]:
            score += 15
        else:
            score -= 15
        if last["c"] > last["sma_200"]:
            score += 15
        else:
            score -= 15
        score += max(min(float(last["mom_20"] or 0) / 2, 20), -20)
        score = max(0.0, min(100.0, score))

        summary = (
            f"1W EMA5/EMA20={last['ema_5']:.2f}/{last['ema_20']:.2f}; "
            f"1Y MA200={last['sma_200']:.2f}; momentum20={last['mom_20']:.2f}."
        )
        return float(round(score, 2)), summary
