from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.clients.moomoo_client import MoomooClient


OUTPUT_FILE = Path("artifacts/test-output/test_moomoo_live_outputs.json")


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
class TestMoomooLive:
    @pytest.fixture(scope="class", autouse=True)
    def _reset_output_file(self) -> None:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("{}", encoding="utf-8")

    def test_moomoo_smoke_connectivity(self, require_moomoo, live_symbols) -> None:
        client = MoomooClient()
        symbol = live_symbols["moomoo_option_symbol"]

        snap = client.get_snapshot(symbol)
        _save_output("test_moomoo_smoke_connectivity", {"symbol": symbol, "snapshot": snap})

        assert isinstance(snap, dict)
        assert "code" in snap
        client.close()

    def test_get_snapshot_live(self, require_moomoo, live_symbols) -> None:
        client = MoomooClient()
        symbol = live_symbols["moomoo_option_symbol"]

        snap = client.get_snapshot(symbol)
        _save_output("test_get_snapshot_live", {"symbol": symbol, "snapshot": snap})

        assert isinstance(snap, dict)
        assert "last_price" in snap
        assert "bid" in snap
        assert "ask" in snap
        client.close()

    def test_get_option_expiration_date_live(self, require_moomoo, live_symbols) -> None:
        client = MoomooClient()
        symbol = live_symbols["moomoo_option_symbol"]

        expiries = client.get_option_expiration_date(symbol)
        _save_output(
            "test_get_option_expiration_date_live",
            {"symbol": symbol, "expiries": expiries},
        )

        assert isinstance(expiries, list)
        if expiries:
            datetime.strptime(expiries[0], "%Y-%m-%d")
        client.close()

    def test_get_option_chain_live(self, require_moomoo, live_symbols) -> None:
        client = MoomooClient()
        symbol = live_symbols["moomoo_option_symbol"]

        expiries = client.get_option_expiration_date(symbol)
        if not expiries:
            client.close()
            pytest.skip(f"No option expiries available for {symbol}")

        expiry = expiries[0]
        chain = client.get_option_chain(symbol=symbol, start=expiry, end=expiry)
        _save_output(
            "test_get_option_chain_live",
            {"symbol": symbol, "expiry": expiry, "chain": chain},
        )

        assert isinstance(chain, list)
        if chain:
            required = {"code", "strike_time", "strike_price"}
            assert required.issubset(set(chain[0].keys()))
        client.close()

    def test_get_account_balances_live(self, require_moomoo) -> None:
        client = MoomooClient()

        balances = client.get_account_balances()
        _save_output("test_get_account_balances_live", {"balances": balances})
        if balances.get("error"):
            client.close()
            pytest.skip(f"Trade context unavailable: {balances['error']}")

        assert isinstance(balances["power"], float)
        assert isinstance(balances["total_assets"], float)
        assert isinstance(balances["net_cash_power"], float)
        client.close()

    def test_get_option_positions_live(self, require_moomoo) -> None:
        client = MoomooClient()

        positions = client.get_option_positions()
        _save_output("test_get_option_positions_live", {"positions": positions})

        assert isinstance(positions, list)
        if positions:
            assert "symbol" in positions[0]
            assert "qty" in positions[0] or "quantity" in positions[0]
        client.close()

    def test_get_position_greeks_live(self, require_moomoo) -> None:
        client = MoomooClient()

        greeks = client.get_position_greeks()
        _save_output("test_get_position_greeks_live", {"greeks": greeks})

        assert isinstance(greeks, list)
        if greeks:
            assert "symbol" in greeks[0]
            assert "delta" in greeks[0]
            assert "vega" in greeks[0]
        client.close()
