from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings


class MassiveRateLimitError(RuntimeError):
    pass


class MassiveClient:
    """Massive REST API client for underlying stock and index data.
    
    Provides market data for equities, indices, and fundamental analysis.
    
    API Reference: https://massive.com/docs/rest/stocks/tickers/ticker-overview
    """
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.massive_base_url.rstrip("/")
        self.api_key = settings.massive_api_key
        self.max_calls = settings.max_massive_calls_per_minute
        self._call_timestamps: deque[float] = deque()
        self.client = httpx.Client(timeout=30.0)

    def _throttle(self) -> None:
        now = time.time()
        while self._call_timestamps and now - self._call_timestamps[0] > 60:
            self._call_timestamps.popleft()
        if len(self._call_timestamps) >= self.max_calls:
            sleep_for = 60 - (now - self._call_timestamps[0]) + 0.1
            if sleep_for > 0:
                time.sleep(sleep_for)
        self._call_timestamps.append(time.time())

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, MassiveRateLimitError)),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._throttle()
        params = params or {}
        params["apiKey"] = self.api_key
        response = self.client.get(f"{self.base_url}{path}", params=params)
        if response.status_code == 429:
            raise MassiveRateLimitError("Massive API rate limit hit")
        response.raise_for_status()
        return response.json()

    def get_underlying_bars(self, symbol: str, timespan: str = "day", limit: int = 365) -> list[dict[str, Any]]:
        data = self._get(f"/v2/aggs/ticker/{symbol}/range/1/{timespan}/2020-01-01/{datetime.utcnow().date()}", {"limit": limit})
        return data.get("results", [])

    def get_news(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get("/v2/reference/news", {"ticker": symbol, "limit": limit})
        return data.get("results", [])

    def get_dividend_calendar(self, symbol: str) -> list[dict[str, Any]]:
        data = self._get("/v3/reference/dividends", {"ticker": symbol})
        return data.get("results", [])

    def get_market_holidays(self) -> list[dict[str, Any]]:
        """Get upcoming US market holidays and closures.

        Massive exposes upcoming market status data for forward-looking holiday planning.
        The payload shape is flexible across API versions, so we accept several common keys.
        """
        data = self._get("/v1/marketstatus/upcoming")
        for key in ("response", "results", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        return []

    def get_index_bars(self, symbol: str, days: int = 5) -> dict[str, Any]:
        """Get recent OHLC bars for an index using the custom bars endpoint.
        
        Args:
            symbol: Index ticker (e.g., 'I:NDX', 'I:VIX', 'SPY')
            days: Number of days to look back
            
        Returns:
            The latest bar as a dict with c (close), o (open), h (high), l (low), t (timestamp)
            Returns empty dict if no data available.
        """
        to_date = datetime.utcnow().date()
        from_date = to_date - timedelta(days=days)
        
        data = self._get(
            f"/v2/aggs/ticker/{symbol}/range/1/day/{from_date.isoformat()}/{to_date.isoformat()}",
            {"sort": "desc", "limit": days}
        )
        
        results = data.get("results", [])
        return results[0] if results else {}
