from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import structlog

from app.analysis.market_regime import MarketRegimeAnalyzer


OUTPUT_FILE = Path("artifacts/test-output/test_market_regime_live_outputs.json")
logger = structlog.get_logger(__name__)
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
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    OUTPUT_FILE.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")


@pytest.mark.live
class TestMarketRegimeLive:
    @pytest.fixture(scope="class", autouse=True)
    def _reset_output_file(self) -> None:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("{}", encoding="utf-8")

    def test_analyze_live(self) -> None:
        analyzer = MarketRegimeAnalyzer()

        logger.info("market_regime_live_test_start")

        vix_value, vix_pct = analyzer._get_index_intraday_metrics("^VIX")
        _, spx_pct = analyzer._get_index_intraday_metrics("^GSPC")
        vix_prev_close_pct = analyzer._get_index_prev_close_change_pct("^VIX")
        spx_prev_close_pct = analyzer._get_index_prev_close_change_pct("^GSPC")

        logger.info(
            "market_regime_live_yfinance_reference",
            vix_value=vix_value,
            vix_intraday_pct=vix_pct,
            spx_intraday_pct=spx_pct,
            vix_prev_close_pct=vix_prev_close_pct,
            spx_prev_close_pct=spx_prev_close_pct,
        )

        score, summary = analyzer.analyze()

        logger.info(
            "market_regime_live_analyze_result",
            score=score,
            summary=summary,
        )

        _save_output(
            "test_analyze_live",
            {
                "vix_value": vix_value,
                "vix_intraday_pct": vix_pct,
                "spx_intraday_pct": spx_pct,
                "vix_prev_close_pct": vix_prev_close_pct,
                "spx_prev_close_pct": spx_prev_close_pct,
                "regime_score": score,
                "summary": summary,
            },
        )

        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0
        assert isinstance(summary, str)
        assert len(summary.strip()) > 0
        assert "Regime=" in summary
        assert "VIX=" in summary
        assert "VIX%=" in summary
        assert "SPX%=" in summary
        assert "VIX1D%=" in summary
        assert "SPX1D%=" in summary
