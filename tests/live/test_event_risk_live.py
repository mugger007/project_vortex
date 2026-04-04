from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.analysis.event_risk import EventRiskAnalyzer
from app.clients.alpha_vantage_client import AlphaVantageClient
from app.clients.massive_client import MassiveClient
from app.scanner.filters import _is_expiry_in_current_week


OUTPUT_FILE = Path("artifacts/test-output/test_event_risk_live_outputs.json")


def _save_output(test_name: str, payload: dict) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists():
        try:
            existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    existing[test_name] = {
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "payload": payload,
    }
    OUTPUT_FILE.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")


@pytest.mark.live
class TestEventRiskLive:
    @pytest.fixture(scope="class", autouse=True)
    def _reset_output_file(self) -> None:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("{}", encoding="utf-8")

    def test_analyze_live(self, require_massive, require_alpha_vantage, live_symbols) -> None:
        massive = MassiveClient()
        analyzer = EventRiskAnalyzer(massive=massive)

        symbol = live_symbols["alpha_vantage_symbol"]
        risk_flag, reason = analyzer.analyze(symbol)

        earnings = AlphaVantageClient().get_earnings_calendar(symbol)
        dividends = massive.get_dividend_calendar(symbol)
        earnings_this_week = [
            row
            for row in earnings
            if (row.get("report_date") or row.get("date"))
            and _is_expiry_in_current_week(str(row.get("report_date") or row.get("date")))
        ]
        dividends_this_week = [
            row
            for row in dividends
            if (row.get("ex_dividend_date") or row.get("pay_date"))
            and _is_expiry_in_current_week(str(row.get("ex_dividend_date") or row.get("pay_date")))
        ]

        _save_output(
            "test_analyze_live",
            {
                "symbol": symbol,
                "risk_flag": risk_flag,
                "reason": reason,
                "earnings_count": len(earnings),
                "dividends_count": len(dividends),
                "earnings_this_week_count": len(earnings_this_week),
                "dividends_this_week_count": len(dividends_this_week),
                "earnings_this_week": earnings_this_week[:5],
                "dividends_this_week": dividends_this_week[:5],
            },
        )

        assert isinstance(risk_flag, bool)
        assert isinstance(reason, str)
        massive.client.close()
