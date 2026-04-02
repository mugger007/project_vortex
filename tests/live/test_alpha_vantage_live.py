from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.clients.alpha_vantage_client import AlphaVantageClient


OUTPUT_FILE = Path("artifacts/test-output/test_alpha_vantage_live_outputs.json")


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
class TestAlphaVantageLive:
    @pytest.fixture(scope="class", autouse=True)
    def _reset_output_file(self) -> None:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("{}", encoding="utf-8")

    def test_get_earnings_calendar_live(self, require_alpha_vantage, live_symbols) -> None:
        client = AlphaVantageClient()
        symbol = live_symbols["alpha_vantage_symbol"]
        rows = client.get_earnings_calendar(symbol=symbol, horizon="3month")

        _save_output(
            "test_get_earnings_calendar_live",
            {"symbol": symbol, "horizon": "3month", "rows": rows},
        )

        assert isinstance(rows, list)
        if rows:
            first = rows[0]
            assert "symbol" in first
            assert str(first["symbol"]).upper() == symbol.upper()
            assert "reportDate" in first or "report_date" in first
