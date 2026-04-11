"""Alpha Vantage API client for earnings calendar data."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from typing import Any

import httpx
from structlog import get_logger

from app.config import get_settings

logger = get_logger(__name__)


class AlphaVantageClient:
    """Alpha Vantage REST client for earnings calendar data.

    Endpoint reference:
    https://www.alphavantage.co/documentation/#earnings-calendar
    """

    # Free-tier guardrail: cap total requests to 25 per UTC day.
    MAX_REQUESTS_PER_DAY = 25

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.alpha_vantage_api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.client = httpx.Client(timeout=30.0)
        self._rate_limit_day: date = datetime.now(UTC).date()
        self._request_count_today = 0

    def _allow_request(self) -> bool:
        """Return whether another request is allowed under the daily cap."""
        current_day = datetime.now(UTC).date()
        if current_day != self._rate_limit_day:
            self._rate_limit_day = current_day
            self._request_count_today = 0

        if self._request_count_today >= self.MAX_REQUESTS_PER_DAY:
            return False

        self._request_count_today += 1
        return True

    def get_earnings_calendar(self, symbol: str, horizon: str = "3month") -> list[dict[str, Any]]:
        """Fetch earnings calendar rows for a given ticker.

        Alpha Vantage returns CSV text for this endpoint. We parse the CSV and
        keep only rows matching the requested symbol for deterministic behavior.
        """
        if not self.api_key:
            logger.warning("alpha_vantage_api_key_missing")
            return []

        if not self._allow_request():
            logger.warning(
                "alpha_vantage_rate_limit_reached",
                max_requests_per_day=self.MAX_REQUESTS_PER_DAY,
            )
            return []

        response = self.client.get(
            self.base_url,
            params={
                "function": "EARNINGS_CALENDAR",
                "symbol": symbol,
                "horizon": horizon,
                "apikey": self.api_key,
            },
        )
        response.raise_for_status()

        text = response.text.strip()
        if not text:
            return []

        rows = list(csv.DictReader(io.StringIO(text)))
        symbol_upper = symbol.upper()
        return [row for row in rows if str(row.get("symbol", "")).upper() == symbol_upper]

