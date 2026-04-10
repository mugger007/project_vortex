"""Market regime analysis using index volatility and trend signals."""

from __future__ import annotations

from app.clients.yfinance_client import YFinanceClient


class MarketRegimeAnalyzer:
    def __init__(self, yfinance: YFinanceClient | None = None) -> None:
        """Create a market regime analyzer backed by a reusable YFinance client."""
        self.yfinance = yfinance or YFinanceClient()

    def _get_index_intraday_metrics(self, index_ticker: str) -> tuple[float, float]:
        """Return latest index price and intraday percent change for a ticker."""
        intraday_data = self.yfinance.get_history(index_ticker, period="5d", interval="5m")
        if intraday_data.empty:
            return 0.0, 0.0

        # Use the latest available trading day in the intraday set.
        latest_session_date = intraday_data.index.max().date()
        latest_session = intraday_data[intraday_data.index.date == latest_session_date]
        if latest_session.empty:
            return 0.0, 0.0

        open_price = float(latest_session["Open"].iloc[0])
        current_price = float(latest_session["Close"].iloc[-1])
        if open_price == 0.0:
            return current_price, 0.0

        intraday_change = current_price - open_price
        percent_change = (intraday_change / open_price) * 100
        return current_price, percent_change

    def _get_index_prev_close_change_pct(self, index_ticker: str) -> float:
        """Return the percent change from the previous close for an index ticker."""
        daily_data = self.yfinance.get_history(index_ticker, period="7d", interval="1d")
        if daily_data.empty or "Close" not in daily_data.columns:
            return 0.0

        closes = daily_data["Close"].dropna()
        if len(closes) < 2:
            return 0.0

        previous_close = float(closes.iloc[-2])
        current_close = float(closes.iloc[-1])
        if previous_close == 0.0:
            return 0.0

        return ((current_close - previous_close) / previous_close) * 100

    def analyze(self) -> tuple[float, str]:
        """Score the current market regime and return a descriptive summary."""
        vix_value, vix_day_change = self._get_index_intraday_metrics("^VIX")
        _, index_change = self._get_index_intraday_metrics("^GSPC")
        vix_prev_close_change = self._get_index_prev_close_change_pct("^VIX")
        spx_prev_close_change = self._get_index_prev_close_change_pct("^GSPC")

        if vix_value <= 0.0:
            vol_state = "mid-vol"
            score = 55.0
        elif vix_value > 28:
            vol_state = "high-vol"
            score = 25.0
        elif vix_value < 16:
            vol_state = "low-vol"
            score = 75.0
        else:
            vol_state = "mid-vol"
            score = 55.0

        if index_change > 0.4:
            trend_state = "bull"
            score += 10
        elif index_change < -0.4:
            trend_state = "bear"
            score -= 10
        else:
            trend_state = "neutral"

        score = max(0.0, min(100.0, score))
        return score, (
            f"Regime={vol_state}/{trend_state}, "
            f"VIX={vix_value:.2f}, VIX%={vix_day_change:.2f}, VIX1D%={vix_prev_close_change:.2f}, "
            f"SPX%={index_change:.2f}, SPX1D%={spx_prev_close_change:.2f}"
        )

