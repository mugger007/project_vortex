from __future__ import annotations

from app.models.schemas import RecommendationPayload, RiskDecision
from app.synthesis.recommendation_engine import RecommendationEngine


class _FakeGemini:
    def __init__(self, response: dict):
        self.response = response

    def generate_json(self, prompt: str) -> dict:
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        return self.response


def test_scorecard_includes_risk_when_present(sample_candidate, sample_analysis) -> None:
    engine = RecommendationEngine(_FakeGemini({}))
    risk = RiskDecision(
        approved=True,
        reason="ok",
        risk_score=80,
        expected_max_drawdown=0.1,
        correlation_max=0.2,
        proposed_size_pct=2.0,
    )

    with_risk = engine.scorecard(sample_candidate, sample_analysis, risk)
    without_risk = engine.scorecard(sample_candidate, sample_analysis, None)

    assert with_risk > without_risk


def test_recommend_forces_avoid_on_event_risk(sample_candidate, sample_analysis) -> None:
    analysis = sample_analysis.model_copy(update={"event_risk_flag": True})
    engine = RecommendationEngine(
        _FakeGemini(
            {
                "recommendation": "Sell",
                "confidence": 80,
                "explanation": "model said sell",
            }
        )
    )

    payload = engine.recommend(sample_candidate, analysis, risk=None)

    assert isinstance(payload, RecommendationPayload)
    assert payload.recommendation == "Avoid"


def test_recommend_uses_model_response_when_no_hard_block(sample_candidate, sample_analysis) -> None:
    engine = RecommendationEngine(
        _FakeGemini(
            {
                "recommendation": "Sell",
                "confidence": 76,
                "explanation": "unit test recommendation",
                "suggested_strike": 500.0,
                "suggested_delta": 0.12,
                "estimated_theta": 0.04,
                "estimated_vega": 0.03,
            }
        )
    )

    payload = engine.recommend(sample_candidate, sample_analysis, risk=None)

    assert payload.recommendation == "Sell"
    assert payload.confidence == 76
    assert 0 <= payload.scorecard <= 100
