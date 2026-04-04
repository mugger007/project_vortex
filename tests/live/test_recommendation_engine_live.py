from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest
import structlog

from app.analysis.event_risk import EventRiskAnalyzer
from app.analysis.market_regime import MarketRegimeAnalyzer
from app.analysis.overreaction import OverreactionAnalyzer
from app.analysis.trends import TrendAnalyzer
from app.analysis.volatility import VolatilityAnalyzer
from app.clients.gemini_client import GeminiClient
from app.clients.massive_client import MassiveClient
from app.models.schemas import AnalysisBundle, FilteredCandidate, OptionSnapshot
from app.synthesis.recommendation_engine import RecommendationEngine


OUTPUT_FILE = Path("artifacts/test-output/test_recommendation_engine_live_outputs.json")
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


def _build_candidate(symbol: str) -> FilteredCandidate:
    rng = random.Random(23)
    snapshot = OptionSnapshot(
        symbol=symbol,
        option_symbol=f"US.{symbol}260417C100000",
        expiry="2026-04-17",
        premium=round(rng.uniform(0.25, 1.8), 4),
        oi=int(rng.uniform(900, 6000)),
        volume=int(rng.uniform(120, 2500)),
        bid=round(rng.uniform(0.2, 1.6), 4),
        ask=round(rng.uniform(0.25, 1.8), 4),
        ts=datetime.now(timezone.utc),
    )
    return FilteredCandidate(
        symbol=symbol,
        option_symbol=snapshot.option_symbol,
        expiry=snapshot.expiry,
        premium_jump_pct=round(rng.uniform(105.0, 220.0), 2),
        snapshot=snapshot,
    )


def _build_analysis_from_live_apis(symbol: str) -> tuple[AnalysisBundle, dict[str, str]]:
    rng = random.Random(17)
    source: dict[str, str] = {}

    massive = MassiveClient()
    gemini = GeminiClient()

    overreaction_analyzer = OverreactionAnalyzer(massive=massive, gemini=gemini)
    volatility_analyzer = VolatilityAnalyzer(massive=massive)
    trends_analyzer = TrendAnalyzer(massive=massive)
    event_risk_analyzer = EventRiskAnalyzer(massive=massive)
    regime_analyzer = MarketRegimeAnalyzer()

    try:
        try:
            overreaction_score, overreaction_explanation = overreaction_analyzer.analyze(symbol)
            source["overreaction"] = "live"
        except Exception:
            overreaction_score, overreaction_explanation = (0.45, "Fallback overreaction explanation")
            source["overreaction"] = "fallback"

        try:
            hv_percentile = volatility_analyzer.analyze(symbol)
            source["volatility"] = "live"
        except Exception:
            hv_percentile = rng.uniform(0.2, 0.9)
            source["volatility"] = "fallback"

        try:
            trend_score, trend_summary = trends_analyzer.analyze(symbol)
            source["trends"] = "live"
        except Exception:
            trend_score, trend_summary = (rng.uniform(35.0, 75.0), "Fallback trend summary")
            source["trends"] = "fallback"

        try:
            event_risk_flag, event_risk_reason = event_risk_analyzer.analyze(symbol)
            source["event_risk"] = "live"
        except Exception:
            event_risk_flag, event_risk_reason = (False, "Fallback event risk reason")
            source["event_risk"] = "fallback"

        try:
            regime_score, regime_summary = regime_analyzer.analyze()
            source["market_regime"] = "live"
        except Exception:
            regime_score, regime_summary = (rng.uniform(40.0, 80.0), "Fallback regime summary")
            source["market_regime"] = "fallback"
    finally:
        massive.client.close()

    analysis = AnalysisBundle(
        overreaction_score=max(0.0, min(1.0, float(overreaction_score))),
        overreaction_explanation=str(overreaction_explanation),
        hv_percentile=max(0.0, min(1.0, float(hv_percentile))),
        trend_score=max(0.0, min(100.0, float(trend_score))),
        trend_summary=str(trend_summary),
        event_risk_flag=bool(event_risk_flag),
        event_risk_reason=str(event_risk_reason),
        regime_score=max(0.0, min(100.0, float(regime_score))),
        regime_summary=str(regime_summary),
    )
    return analysis, source


@pytest.mark.live
class TestRecommendationEngineLive:
    @pytest.fixture(scope="class", autouse=True)
    def _reset_output_file(self) -> None:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("{}", encoding="utf-8")

    def test_recommend_live(self, require_gemini, live_symbols) -> None:
        symbol = live_symbols["massive_symbol"]

        gemini = GeminiClient()
        engine = RecommendationEngine(gemini=gemini)

        candidate = _build_candidate(symbol)
        analysis, source = _build_analysis_from_live_apis(symbol)

        logger.info(
            "recommendation_live_input_sources",
            symbol=symbol,
            source=source,
        )

        recommendation = engine.recommend(candidate=candidate, analysis=analysis, risk=None)

        logger.info(
            "recommendation_live_result",
            symbol=candidate.symbol,
            recommendation=recommendation.recommendation,
            confidence=recommendation.confidence,
            scorecard=recommendation.scorecard,
        )

        _save_output(
            "test_recommend_live",
            {
                "candidate": candidate.model_dump(),
                "analysis": analysis.model_dump(),
                "input_source": source,
                "recommendation": recommendation.model_dump(),
            },
        )

        assert recommendation.recommendation in {"Strong Sell", "Sell", "Neutral", "Avoid"}
        assert isinstance(recommendation.confidence, int)
        assert 0 <= recommendation.scorecard <= 100
        assert isinstance(recommendation.explanation, str)
        assert len(recommendation.explanation.strip()) > 0
