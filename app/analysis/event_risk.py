from __future__ import annotations

from datetime import date, datetime, timedelta

from app.clients.alpha_vantage_client import AlphaVantageClient
from app.clients.massive_client import MassiveClient


class EventRiskAnalyzer:
    def __init__(self, massive: MassiveClient) -> None:
        self.massive = massive
        self.alpha_vantage = AlphaVantageClient()

    def _within_5_days(self, date_str: str) -> bool:
        try:
            d = datetime.fromisoformat(date_str).date()
        except ValueError:
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return False
        today = date.today()
        return today <= d <= today + timedelta(days=5)

    def analyze(self, symbol: str) -> tuple[bool, str]:
        earnings = self.alpha_vantage.get_earnings_calendar(symbol)
        dividends = self.massive.get_dividend_calendar(symbol)
        reasons: list[str] = []

        for row in earnings:
            dt = row.get("report_date") or row.get("date")
            if dt and self._within_5_days(str(dt)):
                reasons.append(f"earnings:{dt}")

        for row in dividends:
            dt = row.get("ex_dividend_date") or row.get("pay_date")
            if dt and self._within_5_days(str(dt)):
                reasons.append(f"dividend:{dt}")

        # FOMC placeholder, to be replaced with Massive macro/economic calendar endpoint.
        return (len(reasons) > 0, ", ".join(reasons) if reasons else "No near-term events")
