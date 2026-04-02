from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.clients.moomoo_client import MoomooClient
from app.scanner.filters import _is_expiry_in_current_week
from app.scanner.monitoring_scanner import MonitoringScanner


OUTPUT_FILE = Path("artifacts/test-output/test_monitoring_scanner_live_outputs.json")
pytestmark = [pytest.mark.live, pytest.mark.filterwarnings("ignore")]


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


class FakeCache:
    def __init__(self) -> None:
        self.json_values: dict[str, dict] = {}

    def get_json(self, key: str) -> dict | None:
        return self.json_values.get(key)

    def set_json(self, key: str, value: dict, ttl_seconds: int) -> None:
        self.json_values[key] = value


class FakeRepo:
    def __init__(self) -> None:
        self.snapshots: list[dict] = []
        self.audit_logs: list[dict] = []

    def save_snapshot(self, payload: dict) -> dict:
        self.snapshots.append(payload)
        return payload

    def add_audit_log(
        self,
        stage: str,
        message: str,
        payload_json: dict,
        scan_run_id: int | None = None,
        level: str = "INFO",
    ) -> None:
        self.audit_logs.append(
            {
                "stage": stage,
                "message": message,
                "payload_json": payload_json,
                "scan_run_id": scan_run_id,
                "level": level,
            }
        )


class TestMonitoringScannerLive:
    def _make_scanner(self) -> tuple[MonitoringScanner, FakeCache, FakeRepo, MoomooClient]:
        moomoo_client = MoomooClient()
        cache = FakeCache()
        repo = FakeRepo()
        scanner = MonitoringScanner(
            moomoo_client=moomoo_client,
            massive_client=object(),
            cache=cache,
            repo=repo,
        )
        return scanner, cache, repo, moomoo_client

    @pytest.mark.parametrize(
        "symbol",
        [
            "US.USO",
        ],
    )
    def test_scan_symbol_with_manual_tickers(
        self,
        require_moomoo,
        symbol: str,
    ) -> None:
        scanner, cache, repo, moomoo_client = self._make_scanner()

        expiries = moomoo_client.get_option_expiration_date(symbol)
        assert isinstance(expiries, list)
        assert len(expiries) > 0

        eligible_expiries = [
            expiry for expiry in expiries if _is_expiry_in_current_week(expiry)
        ]
        assert len(eligible_expiries) > 0

        expected_expiry = eligible_expiries[0]
        selected_expiry_chain = moomoo_client.get_option_chain(symbol, start=expected_expiry, end=expected_expiry)
        selected_expiry_option_codes = [
            str(row.get("code", "") or "")
            for row in selected_expiry_chain
            if str(row.get("code", "") or "")
        ]

        candidates = scanner.scan_symbol(symbol)

        assert isinstance(candidates, list)
        for candidate in candidates:
            assert candidate.symbol == symbol
            assert candidate.snapshot.symbol == symbol
            assert candidate.snapshot.option_symbol == candidate.option_symbol
            assert candidate.snapshot.expiry == candidate.expiry
            assert candidate.snapshot.ts.tzinfo is not None
            assert candidate.premium_jump_pct > 100

        if repo.audit_logs:
            assert repo.audit_logs[0]["stage"] == "liquidity_filter"

        _save_output(
            "test_scan_symbol_with_manual_tickers",
            {
                "symbol": symbol,
                "expected_expiry": expected_expiry,
                "expiries": expiries,
                "selected_expiry_chain_count": len(selected_expiry_chain),
                "selected_expiry_option_codes": selected_expiry_option_codes,
                "candidate_count": len(candidates),
                "candidates": [c.model_dump() for c in candidates[:5]],
                "snapshots_recorded": len(repo.snapshots),
                "audit_logs_recorded": len(repo.audit_logs),
            },
        )

        moomoo_client.close()

