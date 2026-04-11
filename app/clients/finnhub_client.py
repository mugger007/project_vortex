"""Finnhub client for company news access."""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import finnhub

from app.config import get_settings


class FinnhubClient:
    """Adapter for Finnhub API news access with rate limiting (60 calls/minute)."""

    # Rate limit: 60 API calls per minute = 1 call per second
    RATE_LIMIT_CALLS = 60
    RATE_LIMIT_WINDOW_SECONDS = 60

    def __init__(self, api_key: str | None = None):
        """Initialize Finnhub client with API key and rate limiter."""
        
        # Use provided api_key or fetch from config
        if api_key is None:
            settings = get_settings()
            api_key = settings.finnhub_api_key
        
        if not api_key:
            raise ValueError(
                "Finnhub API key not provided and not found in FINNHUB_API_KEY environment variable. "
                "Please set FINNHUB_API_KEY or pass api_key to FinnhubClient()."
            )
        
        self.client = finnhub.Client(api_key=api_key)
        # Track API call timestamps for rate limiting (sliding window)
        self._call_timestamps: deque[float] = deque(maxlen=self.RATE_LIMIT_CALLS)

    def _wait_for_rate_limit(self) -> None:
        """Enforce rate limiting: wait if necessary to stay within 60 calls/minute."""
        now = time.time()
        # Remove timestamps older than the rate limit window
        while self._call_timestamps and (now - self._call_timestamps[0]) > self.RATE_LIMIT_WINDOW_SECONDS:
            self._call_timestamps.popleft()
        
        # If we've reached the call limit, wait until the oldest call expires
        if len(self._call_timestamps) >= self.RATE_LIMIT_CALLS:
            oldest_call = self._call_timestamps[0]
            sleep_duration = self.RATE_LIMIT_WINDOW_SECONDS - (now - oldest_call)
            if sleep_duration > 0:
                time.sleep(sleep_duration)
        
        # Record this call
        self._call_timestamps.append(time.time())

    def get_news(self, symbol: str, limit: int = 15) -> str:
        """Fetch recent company news for the symbol and return as JSON string.
        Only includes articles published within the last 24 hours, sorted by recency.
        Respects rate limit of 60 calls/minute.
        """
        try:
            window_from, window_to = self._news_window()
            self._wait_for_rate_limit()
            raw_news = self.client.company_news(symbol, _from=window_from, to=window_to) or []
            enriched_news = sorted(
                (
                    {
                        "title": item.get("headline", ""),
                        "publisher": item.get("source", ""),
                        "link": item.get("url", ""),
                        "published_utc": self._extract_published_utc(item),
                        "content": item.get("summary", ""),
                    }
                    for item in raw_news[:limit]
                    if self._is_within_24_hours(item)
                ),
                key=self._news_sort_key,
                reverse=True,
            )
            return json.dumps(enriched_news, indent=2)
        except Exception as exc:
            return json.dumps(
                {
                    "error": type(exc).__name__,
                    "message": str(exc),
                    "symbol": symbol,
                    "window": dict(zip(("from", "to"), self._news_window())),
                },
                indent=2,
            )

    def _news_window(self) -> tuple[str, str]:
        """Return the last 24 hours as YYYY-MM-DD window strings for Finnhub."""
        now_utc = datetime.now(UTC)
        return ((now_utc - timedelta(days=1)).date().isoformat(), now_utc.date().isoformat())

    def _extract_published_utc(self, item: dict[str, Any]) -> str:
        """Normalize the publish timestamp from a finnhub news item to UTC ISO 8601."""
        raw_datetime = item.get("datetime")
        if raw_datetime in (None, ""):
            return ""

        try:
            if isinstance(raw_datetime, (int, float)):
                seconds = float(raw_datetime)
                return datetime.fromtimestamp(seconds, tz=UTC).isoformat()

            text_value = str(raw_datetime).strip()
            if not text_value:
                return ""

            if text_value.isdigit():
                seconds = float(text_value)
                return datetime.fromtimestamp(seconds, tz=UTC).isoformat()

            parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).isoformat()
        except (ValueError, OSError):
            return ""

    def _is_within_24_hours(self, item: dict[str, Any]) -> bool:
        """Check if an article was published within the last 24 hours."""
        published = self._extract_published_utc(item)
        if not published:
            return False

        try:
            parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            parsed_utc = parsed.astimezone(UTC)
            now_utc = datetime.now(UTC)
            age_seconds = (now_utc - parsed_utc).total_seconds()
            return age_seconds <= 86400  # 24 hours in seconds
        except ValueError:
            return False

    def _news_sort_key(self, item: dict[str, Any]) -> datetime:
        """Sort news items by recency, falling back to the oldest possible timestamp."""
        published = self._extract_published_utc(item)
        if not published:
            return datetime.min.replace(tzinfo=timezone.utc)

        try:
            parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
