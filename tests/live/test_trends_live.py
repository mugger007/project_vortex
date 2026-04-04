from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.analysis.trends import TrendAnalyzer
from app.clients.massive_client import MassiveClient


OUTPUT_FILE = Path("artifacts/test-output/test_trends_live_outputs.json")


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
class TestTrendsLive:
    @pytest.fixture(scope="class", autouse=True)
    def _reset_output_file(self) -> None:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("{}", encoding="utf-8")

    def test_analyze_live(self, require_massive, live_symbols) -> None:
        massive = MassiveClient()
        analyzer = TrendAnalyzer(massive=massive)

        symbol = live_symbols["massive_symbol"]
        try:
            score, summary = analyzer.analyze(symbol)
        finally:
            massive.client.close()

        _save_output(
            "test_analyze_live",
            {
                "symbol": symbol,
                "trend_score": score,
                "summary": summary,
            },
        )

        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0
        assert isinstance(summary, str)
        assert len(summary.strip()) > 0
