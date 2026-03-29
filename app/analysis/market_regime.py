from __future__ import annotations

from app.clients.massive_client import MassiveClient


class MarketRegimeAnalyzer:
    def __init__(self, massive: MassiveClient) -> None:
        self.massive = massive

    def analyze(self, symbol: str) -> tuple[float, str]:
        vix = self.massive.get_index_bars("I:VIX")
        spy = self.massive.get_index_bars("SPY")

        vix_value = float(vix.get("c", 20.0))
        spy_close = float(spy.get("c", 0.0))
        spy_open = float(spy.get("o", 0.0))
        spy_change = ((spy_close - spy_open) / spy_open * 100) if spy_open else 0.0

        if vix_value > 28:
            vol_state = "high-vol"
            score = 25.0
        elif vix_value < 16:
            vol_state = "low-vol"
            score = 75.0
        else:
            vol_state = "mid-vol"
            score = 55.0

        if spy_change > 0.4:
            trend_state = "bull"
            score += 10
        elif spy_change < -0.4:
            trend_state = "bear"
            score -= 10
        else:
            trend_state = "neutral"

        score = max(0.0, min(100.0, score))
        return score, f"Regime={vol_state}/{trend_state}, VIX={vix_value:.2f}, SPY%={spy_change:.2f}"
