from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings


class MassiveRateLimitError(RuntimeError):
    pass


class MassiveClient:
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

    def get_options_chain_snapshot(self, symbol: str) -> list[dict[str, Any]]:
        data = self._get("/v3/snapshot/options", {"underlying_ticker": symbol})
        return data.get("results", [])

    def get_options_trades(self, option_symbol: str) -> list[dict[str, Any]]:
        data = self._get(f"/v3/trades/{option_symbol}")
        return data.get("results", [])

    def get_underlying_bars(self, symbol: str, timespan: str = "day", limit: int = 365) -> list[dict[str, Any]]:
        data = self._get(f"/v2/aggs/ticker/{symbol}/range/1/{timespan}/2020-01-01/{datetime.utcnow().date()}", {"limit": limit})
        return data.get("results", [])

    def get_iv_snapshot(self, option_symbol: str) -> dict[str, Any]:
        return self._get(f"/v3/snapshot/options/{option_symbol}")

    def get_news(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get("/v2/reference/news", {"ticker": symbol, "limit": limit})
        return data.get("results", [])

    def get_earnings_calendar(self, symbol: str) -> list[dict[str, Any]]:
        data = self._get("/vX/reference/earnings", {"ticker": symbol})
        return data.get("results", [])

    def get_dividend_calendar(self, symbol: str) -> list[dict[str, Any]]:
        data = self._get("/v3/reference/dividends", {"ticker": symbol})
        return data.get("results", [])

    def get_index_snapshot(self, symbol: str) -> dict[str, Any]:
        data = self._get("/v2/snapshot/locale/us/markets/stocks/tickers", {"tickers": symbol})
        results = data.get("tickers", [])
        return results[0] if results else {}
