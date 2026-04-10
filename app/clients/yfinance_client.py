"""YFinance client helpers for quote and historical index/equity data."""

from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf


class YFinanceClient:
    """Thin adapter around yfinance for history, fast-info, and spot price access."""

    def get_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        """Return a historical OHLCV DataFrame for the requested symbol and window."""
        return yf.Ticker(symbol).history(period=period, interval=interval)

    def get_fast_info(self, symbol: str) -> dict[str, Any]:
        """Return yfinance fast_info as a plain dictionary."""
        info = yf.Ticker(symbol).fast_info
        # yfinance returns a lazy mapping; normalize to plain dict for callers.
        return dict(info)

    def get_last_price(self, symbol: str) -> float:
        """Return the latest spot price from yfinance fast_info or raise on missing data."""
        fast_info = self.get_fast_info(symbol)
        last_price = float(fast_info.get("lastPrice") or 0.0)
        if last_price <= 0:
            raise ValueError(f"yfinance fast_info.lastPrice unavailable for {symbol}")
        return last_price