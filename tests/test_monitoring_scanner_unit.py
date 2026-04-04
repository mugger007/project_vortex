from __future__ import annotations

from datetime import UTC, datetime

from app.scanner.monitoring_scanner import MonitoringScanner


class _Repo:
    def __init__(self) -> None:
        self.snapshots: list[dict] = []
        self.audit_logs: list[dict] = []

    def save_snapshot(self, payload: dict) -> dict:
        self.snapshots.append(payload)
        return payload

    def add_audit_log(self, stage: str, message: str, payload_json: dict, scan_run_id=None, level: str = "INFO") -> None:
        self.audit_logs.append(
            {
                "stage": stage,
                "message": message,
                "payload_json": payload_json,
                "scan_run_id": scan_run_id,
                "level": level,
            }
        )


class _Moomoo:
    def __init__(self, prev_close: float = 1.0, bid: float = 2.9, ask: float = 3.1) -> None:
        self.prev_close = prev_close
        self.bid = bid
        self.ask = ask

    def get_option_expiration_date(self, symbol: str) -> list[str]:
        return [datetime.now(UTC).date().isoformat()]

    def get_option_chain(self, symbol: str, start: str | None = None, end: str | None = None) -> list[dict]:
        return [{"code": "US.USO260417C100000", "last_updated": datetime.now(UTC).isoformat()}]

    def get_snapshot(self, symbol: str) -> dict:
        return {
            "code": symbol,
            "last_price": 3.0,
            "prev_close_price": self.prev_close,
            "bid": self.bid,
            "ask": self.ask,
            "volume": 1000,
            "option_open_interest": 2000,
            "update_time": datetime.now(UTC).isoformat(),
        }


def test_scan_symbol_returns_candidate_when_filters_pass() -> None:
    repo = _Repo()
    scanner = MonitoringScanner(
        moomoo_client=_Moomoo(prev_close=1.0, bid=2.9, ask=3.1),
        massive_client=object(),
        cache=object(),
        repo=repo,
    )

    candidates = scanner.scan_symbol("US.USO")

    assert len(candidates) == 1
    assert candidates[0].premium_jump_pct > 100
    assert len(repo.snapshots) == 1
    assert len(repo.audit_logs) >= 1


def test_scan_symbol_rejects_when_jump_below_threshold() -> None:
    repo = _Repo()
    scanner = MonitoringScanner(
        moomoo_client=_Moomoo(prev_close=2.0, bid=2.9, ask=3.1),
        massive_client=object(),
        cache=object(),
        repo=repo,
    )

    candidates = scanner.scan_symbol("US.USO")

    assert candidates == []
    assert len(repo.snapshots) == 1
