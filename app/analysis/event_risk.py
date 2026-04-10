"""Event risk analysis based on earnings and dividend calendars."""

from __future__ import annotations

from structlog import get_logger

from app.clients.alpha_vantage_client import AlphaVantageClient
from app.clients.massive_client import MassiveClient
from app.scanner.filters import _is_expiry_in_current_week


logger = get_logger(__name__)


class EventRiskAnalyzer:
    def __init__(self, massive: MassiveClient) -> None:
        """Create an event-risk analyzer using Massive and Alpha Vantage feeds."""
        self.massive = massive
        self.alpha_vantage = AlphaVantageClient()

    def analyze(self, symbol: str) -> tuple[bool, str]:
        """Flag whether the symbol has near-term earnings or dividend risk."""
        earnings = self.alpha_vantage.get_earnings_calendar(symbol)
        dividends = self.massive.get_dividend_calendar(symbol)
        logger.info(
            "event_risk_data_loaded",
            symbol=symbol,
            earnings_count=len(earnings),
            dividends_count=len(dividends),
        )

        reasons: list[str] = []

        for row in earnings:
            dt = row.get("report_date") or row.get("date")
            if dt and _is_expiry_in_current_week(str(dt)):
                reasons.append(f"earnings:{dt}")

        for row in dividends:
            dt = row.get("ex_dividend_date") or row.get("pay_date")
            if dt and _is_expiry_in_current_week(str(dt)):
                reasons.append(f"dividend:{dt}")

        logger.info(
            "event_risk_analyzed",
            symbol=symbol,
            risk_flag=len(reasons) > 0,
            matched_reasons=reasons,
        )

        # FOMC placeholder, to be replaced with Massive macro/economic calendar endpoint.
        return (len(reasons) > 0, ", ".join(reasons) if reasons else "No near-term events")

