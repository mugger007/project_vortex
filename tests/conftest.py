from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.schemas import AnalysisBundle, FilteredCandidate, OptionSnapshot


@pytest.fixture
def sample_candidate() -> FilteredCandidate:
    snapshot = OptionSnapshot(
        symbol="SPY",
        option_symbol="US.SPY260417C500000",
        expiry="2026-04-17",
        premium=1.25,
        oi=1500,
        volume=500,
        bid=1.2,
        ask=1.3,
        ts=datetime.now(timezone.utc),
        extra={"greeks": {"delta": 0.1, "vega": 0.05}},
    )
    return FilteredCandidate(
        symbol="SPY",
        option_symbol=snapshot.option_symbol,
        expiry=snapshot.expiry,
        premium_jump_pct=140.0,
        snapshot=snapshot,
    )


@pytest.fixture
def sample_analysis() -> AnalysisBundle:
    return AnalysisBundle(
        overreaction_score=0.4,
        overreaction_explanation="Unit overreaction explanation",
        hv_percentile=0.55,
        trend_score=70.0,
        trend_summary="Unit trend summary",
        event_risk_flag=False,
        event_risk_reason="No near-term events",
        regime_score=60.0,
        regime_summary="Regime=mid-vol/neutral",
    )
