"""Recommendation scoring and Gemini-based synthesis engine."""

from __future__ import annotations

from app.clients.gemini_client import GeminiClient
from app.models.schemas import AnalysisBundle, FilteredCandidate, RecommendationPayload, RiskDecision
from app.synthesis.prompt_builder import build_synthesis_prompt


class RecommendationEngine:
    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

    def scorecard(
        self,
        candidate: FilteredCandidate,
        analysis: AnalysisBundle,
        risk: RiskDecision | None,
    ) -> int:
        score = 0.0
        score += min(candidate.premium_jump_pct / 10, 15)
        score += analysis.overreaction_score * 20
        score += analysis.hv_percentile * 15
        score += (analysis.trend_score / 100) * 15
        score += (analysis.regime_score / 100) * 10
        if risk is not None:
            score += (risk.risk_score / 100) * 25
        if analysis.event_risk_flag:
            score -= 35
        if risk is not None and not risk.approved:
            score -= 50
        return max(0, min(100, int(round(score))))

    def recommend(
        self,
        candidate: FilteredCandidate,
        analysis: AnalysisBundle,
        risk: RiskDecision | None,
    ) -> RecommendationPayload:
        scorecard = self.scorecard(candidate, analysis, risk)
        prompt = build_synthesis_prompt(candidate=candidate, analysis=analysis, risk=risk, scorecard=scorecard)
        response = self.gemini.generate_json(prompt)

        recommendation = str(response.get("recommendation", "Avoid"))
        if analysis.event_risk_flag or (risk is not None and not risk.approved):
            recommendation = "Avoid"

        return RecommendationPayload(
            recommendation=recommendation,
            confidence=int(response.get("confidence", 0)),
            explanation=str(response.get("explanation", "No explanation provided.")),
            suggested_strike=response.get("suggested_strike"),
            suggested_delta=response.get("suggested_delta"),
            estimated_theta=response.get("estimated_theta"),
            estimated_vega=response.get("estimated_vega"),
            scorecard=scorecard,
        )

