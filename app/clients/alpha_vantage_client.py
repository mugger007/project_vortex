"""Alpha Vantage API client for earnings calendar data."""

from __future__ import annotations

import csv
import io
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

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.alpha_vantage_api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.client = httpx.Client(timeout=30.0)

    def get_earnings_calendar(self, symbol: str, horizon: str = "3month") -> list[dict[str, Any]]:
        """Fetch earnings calendar rows for a given ticker.

        Alpha Vantage returns CSV text for this endpoint. We parse the CSV and
        keep only rows matching the requested symbol for deterministic behavior.
        """
        if not self.api_key:
            logger.warning("alpha_vantage_api_key_missing")
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

