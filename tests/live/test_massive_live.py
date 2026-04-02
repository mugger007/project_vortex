from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.clients.massive_client import MassiveClient


OUTPUT_FILE = Path("artifacts/test-output/test_massive_live_outputs.json")


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
class TestMassiveLive:
    @pytest.fixture(scope="class", autouse=True)
    def _reset_output_file(self) -> None:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("{}", encoding="utf-8")

    def test_massive_smoke_connectivity(self, require_massive, live_symbols) -> None:
        client = MassiveClient()
        symbol = live_symbols["massive_symbol"]

        # Ticker overview endpoint from Massive docs (query must return a ticker payload).
        payload = client._get(f"/v3/reference/tickers/{symbol}")
        _save_output("test_massive_smoke_connectivity", {"symbol": symbol, "payload": payload})

        assert isinstance(payload, dict)
        assert "results" in payload
        assert payload["results"].get("ticker") == symbol

    def test_get_underlying_bars_live(self, require_massive, live_symbols) -> None:
        client = MassiveClient()
        symbol = live_symbols["massive_symbol"]
        bars = client.get_underlying_bars(symbol=symbol, timespan="day", limit=10)
        _save_output("test_get_underlying_bars_live", {"symbol": symbol, "bars": bars})

        assert isinstance(bars, list)
        assert len(bars) > 0
        required = {"t", "c", "h", "l"}
        assert required.issubset(set(bars[0].keys()))

    def test_get_news_live(self, require_massive, live_symbols) -> None:
        client = MassiveClient()
        symbol = live_symbols["massive_symbol"]
        news = client.get_news(symbol=symbol, limit=5)
        _save_output("test_get_news_live", {"symbol": symbol, "news": news})

        assert isinstance(news, list)
        if news:
            assert "title" in news[0]

    def test_get_dividend_calendar_live(self, require_massive, live_symbols) -> None:
        client = MassiveClient()
        symbol = live_symbols["massive_symbol"]
        dividends = client.get_dividend_calendar(symbol=symbol)
        _save_output("test_get_dividend_calendar_live", {"symbol": symbol, "dividends": dividends})

        assert isinstance(dividends, list)

    def test_get_index_bars_live(self, require_massive, live_symbols) -> None:
        client = MassiveClient()
        symbol = live_symbols["massive_symbol"]
        bar = client.get_index_bars(symbol=symbol)
        _save_output("test_get_index_bars_live", {"symbol": symbol, "bar": bar})

        assert isinstance(bar, dict)
        if bar:
            # Verify OHLC bar structure from custom bars endpoint
            required_fields = {"c", "o", "h", "l", "t"}
            assert required_fields.issubset(set(bar.keys()))
            assert isinstance(bar["c"], (int, float))
            assert isinstance(bar["t"], int)
