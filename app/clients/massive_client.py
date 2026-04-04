"""Massive API client with throttling and market data helpers."""

from __future__ import annotations

import time
from collections import deque
from datetime import UTC, date, datetime, timedelta
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
    MAX_CALLS_PER_MINUTE = 5
    MAX_HISTORICAL_DAYS = 730

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.massive_base_url.rstrip("/")
        self.api_key = settings.massive_api_key
        configured_max = int(settings.max_massive_calls_per_minute or self.MAX_CALLS_PER_MINUTE)
        self.max_calls = max(1, min(configured_max, self.MAX_CALLS_PER_MINUTE))
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

    def _coerce_date(self, value: date | str) -> date:
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)).date()

    def _previous_market_day(self, reference_date: date | None = None) -> date:
        d = (reference_date or datetime.now(UTC).date()) - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d

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

    def get_underlying_bars(
        self,
        symbol: str,
        timespan: str = "day",
        limit: int = 365,
        from_date: date | str | None = None,
        to_date: date | str | None = None,
    ) -> list[dict[str, Any]]:
        resolved_to = self._coerce_date(to_date) if to_date is not None else self._previous_market_day()
        resolved_from = self._coerce_date(from_date) if from_date is not None else resolved_to - timedelta(days=self.MAX_HISTORICAL_DAYS)

        if resolved_from > resolved_to:
            resolved_from = resolved_to

        max_window_start = resolved_to - timedelta(days=self.MAX_HISTORICAL_DAYS)
        if resolved_from < max_window_start:
            resolved_from = max_window_start

        max_rows_by_window = max(1, (resolved_to - resolved_from).days + 1)
        bounded_limit = max(1, min(int(limit or 1), self.MAX_HISTORICAL_DAYS, max_rows_by_window))
        data = self._get(
            f"/v2/aggs/ticker/{symbol}/range/1/{timespan}/{resolved_from.isoformat()}/{resolved_to.isoformat()}",
            {"limit": bounded_limit},
        )
        return data.get("results", [])

    def get_news(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get("/v2/reference/news", {"ticker": symbol, "limit": limit})
        return data.get("results", [])

    def get_dividend_calendar(self, symbol: str) -> list[dict[str, Any]]:
        data = self._get("/v3/reference/dividends", {"ticker": symbol})
        return data.get("results", [])

