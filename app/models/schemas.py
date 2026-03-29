from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OptionSnapshot(BaseModel):
    symbol: str
    option_symbol: str
    expiry: str
    premium: float
    oi: int
    volume: int
    bid: float
    ask: float
    ts: datetime
    extra: dict = Field(default_factory=dict)


class FilteredCandidate(BaseModel):
    symbol: str
    option_symbol: str
    expiry: str
    premium_jump_pct: float
    snapshot: OptionSnapshot


class AnalysisBundle(BaseModel):
    overreaction_score: float
    overreaction_explanation: str
    hv_percentile: float
    trend_score: float
    trend_summary: str
    event_risk_flag: bool
    event_risk_reason: str
    regime_score: float
    regime_summary: str


class RiskDecision(BaseModel):
    approved: bool
    reason: str
    risk_score: float
    expected_max_drawdown: float
    correlation_max: float
    proposed_size_pct: float


class RecommendationPayload(BaseModel):
    recommendation: str
    confidence: int
    explanation: str
    suggested_strike: float | None = None
    suggested_delta: float | None = None
    estimated_theta: float | None = None
    estimated_vega: float | None = None
    scorecard: int


class RecommendationCard(BaseModel):
    symbol: str
    option_symbol: str
    created_at: datetime
    data: RecommendationPayload
    rejected: bool
    rejection_reason: str | None = None
