from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.schemas import FilteredCandidate, OptionSnapshot, RecommendationPayload
from app.services import orchestrator as orchestrator_module


def test_orchestrator_run_scan_cycle_unit(monkeypatch) -> None:
    class FakeSettings:
        scan_interval_minutes = 5

    class FakeMoomoo:
        def get_option_positions(self) -> list[dict]:
            return [
                {
                    "symbol": "US.SPY260417C500000",
                    "qty": 1,
                    "delta": 0.1,
                    "vega": 0.2,
                    "market_val": 100.0,
                }
            ]

    class FakeMassive:
        pass

    class FakeGemini:
        pass

    class FakeAlerts:
        def __init__(self) -> None:
            self.notified = 0

        def notify_high_confidence(self, card) -> None:
            self.notified += 1

    holder: dict[str, object] = {}

    class FakeRepo:
        def __init__(self, db) -> None:
            self.saved_recommendations: list[dict] = []
            self.saved_positions: list[dict] = []
            self.completed: dict | None = None
            self.audit_logs: list[dict] = []
            holder["repo"] = self

        def create_scan_run(self, started_at, metadata_json):
            return SimpleNamespace(id=123)

        def save_position_snapshot(self, payload: dict) -> None:
            self.saved_positions.append(payload)

        def clear_position_snapshots(self) -> None:
            self.saved_positions.clear()

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

        def save_recommendation(self, payload: dict) -> None:
            self.saved_recommendations.append(payload)

        def complete_scan_run(self, run_id: int, finished_at, status: str, metadata_json: dict) -> None:
            self.completed = {
                "run_id": run_id,
                "status": status,
                "metadata_json": metadata_json,
            }

    class FakeScanner:
        def __init__(self, moomoo_client, massive_client, repo) -> None:
            self.repo = repo

        def scan_symbol(self, symbol: str) -> list[FilteredCandidate]:
            if symbol != "US.SPY":
                return []
            ts = datetime.now(timezone.utc)
            candidate = FilteredCandidate(
                symbol="US.SPY",
                option_symbol="US.SPY260417C500000",
                expiry="2026-04-17",
                premium_jump_pct=140.0,
                snapshot=OptionSnapshot(
                    symbol="US.SPY",
                    option_symbol="US.SPY260417C500000",
                    expiry="2026-04-17",
                    premium=1.2,
                    oi=1200,
                    volume=350,
                    bid=1.1,
                    ask=1.3,
                    ts=ts,
                    extra={"greeks": {"delta": 0.12, "vega": 0.08}},
                ),
            )
            return [candidate]

    class FakeOverreaction:
        def __init__(self, yfinance, finnhub, gemini) -> None:
            pass

        def analyze(self, symbol: str, option_type: str = "C") -> tuple[float, str]:
            return 0.45, "unit overreaction"

    class FakeVolatility:
        def __init__(self, massive) -> None:
            pass

        def analyze(self, symbol: str) -> float:
            return 0.62

    class FakeTrends:
        def __init__(self, massive) -> None:
            pass

        def analyze(self, symbol: str) -> tuple[float, str]:
            return 68.0, "unit trend"

    class FakeEvents:
        def __init__(self, massive) -> None:
            pass

        def analyze(self, symbol: str) -> tuple[bool, str]:
            return False, "No near-term events"

    class FakeRegime:
        def analyze(self) -> tuple[float, str]:
            return 60.0, "Regime=mid-vol/neutral"

    class FakeRecommender:
        def __init__(self, gemini) -> None:
            pass

        def recommend(self, candidate, analysis, risk) -> RecommendationPayload:
            return RecommendationPayload(
                recommendation="Sell",
                confidence=82,
                explanation="unit recommendation",
                suggested_strike=500.0,
                suggested_delta=0.12,
                estimated_theta=0.05,
                estimated_vega=0.03,
                scorecard=77,
            )

    @contextmanager
    def fake_get_db_session():
        yield object()

    monkeypatch.setattr(orchestrator_module, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(orchestrator_module, "MoomooClient", FakeMoomoo)
    monkeypatch.setattr(orchestrator_module, "MassiveClient", FakeMassive)
    monkeypatch.setattr(orchestrator_module, "GeminiClient", FakeGemini)
    monkeypatch.setattr(orchestrator_module, "AlertService", FakeAlerts)
    monkeypatch.setattr(orchestrator_module, "ScanRepository", FakeRepo)
    monkeypatch.setattr(orchestrator_module, "MonitoringScanner", FakeScanner)
    monkeypatch.setattr(orchestrator_module, "OverreactionAnalyzer", FakeOverreaction)
    monkeypatch.setattr(orchestrator_module, "VolatilityAnalyzer", FakeVolatility)
    monkeypatch.setattr(orchestrator_module, "TrendAnalyzer", FakeTrends)
    monkeypatch.setattr(orchestrator_module, "EventRiskAnalyzer", FakeEvents)
    monkeypatch.setattr(orchestrator_module, "MarketRegimeAnalyzer", FakeRegime)
    monkeypatch.setattr(orchestrator_module, "RecommendationEngine", FakeRecommender)
    monkeypatch.setattr(orchestrator_module, "get_db_session", fake_get_db_session)

    orchestrator = orchestrator_module.Orchestrator()
    orchestrator.watchlist = ["SPY"]

    cards = orchestrator.run_scan_cycle()

    repo = holder["repo"]
    assert len(cards) == 1
    assert cards[0].symbol == "SPY"
    assert cards[0].data.recommendation == "Sell"
    assert cards[0].data.scorecard == 77

    assert len(repo.saved_positions) == 1
    assert len(repo.saved_recommendations) == 1
    assert repo.completed is not None
    assert repo.completed["status"] == "success"
    assert repo.completed["metadata_json"]["recommendations"] == 1
