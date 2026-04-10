"""Pydantic schemas for scanner, analysis, risk, and recommendation data."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


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
    option_type: str = ""
    expiry: str
    premium_jump_pct: float
    snapshot: OptionSnapshot

    @model_validator(mode="after")
    def _extract_option_type(self) -> FilteredCandidate:
        match = re.search(r"\d{6}([CP])\d+(?:\.\d+)?$", self.option_symbol)
        if match is None:
            raise ValueError("option_symbol must include option type C/P after a 6-digit expiry")

        extracted = match.group(1)
        if self.option_type and self.option_type != extracted:
            raise ValueError("option_type does not match option_symbol")

        self.option_type = extracted
        return self


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

