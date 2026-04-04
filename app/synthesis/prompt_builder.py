"""Prompt construction helpers for recommendation synthesis."""

from __future__ import annotations

from app.models.schemas import AnalysisBundle, FilteredCandidate, RiskDecision


def build_synthesis_prompt(
    candidate: FilteredCandidate,
    analysis: AnalysisBundle,
    risk: RiskDecision | None,
    scorecard: int,
) -> str:
    if risk is None:
        risk_lines = """
Portfolio risk:
- Disabled for this run
""".strip()
    else:
        risk_lines = f"""
Portfolio risk:
- Approved: {risk.approved}
- Risk reason: {risk.reason}
- Risk score (0-100): {risk.risk_score:.2f}
- Expected max drawdown: {risk.expected_max_drawdown:.4f}
- Max correlation: {risk.correlation_max:.4f}
- Proposed size % capital: {risk.proposed_size_pct:.2f}
""".strip()

    return f"""
You are an institutional US weekly-options premium-selling strategist.
Task: Decide if this contract should be sold for theta decay.

Hard constraints already applied:
- US equity weekly options (Friday expiry)
- Liquidity filter passed (OI>750, volume>100, spread<10%)

Input data:
- Symbol: {candidate.symbol}
- Option symbol: {candidate.option_symbol}
- Expiry: {candidate.expiry}
- Premium jump %: {candidate.premium_jump_pct:.2f}
- Premium: {candidate.snapshot.premium:.4f}
- OI/Volume: {candidate.snapshot.oi}/{candidate.snapshot.volume}

Analysis:
- Overreaction score (0-1): {analysis.overreaction_score:.4f}
- Overreaction explanation: {analysis.overreaction_explanation}
- HV percentile (0-1): {analysis.hv_percentile:.4f}
- Trend score (0-100): {analysis.trend_score:.2f}
- Trend summary: {analysis.trend_summary}
- Event risk flag: {analysis.event_risk_flag}
- Event risk reason: {analysis.event_risk_reason}
- Market regime score (0-100): {analysis.regime_score:.2f}
- Market regime summary: {analysis.regime_summary}

{risk_lines}

Rule-based scorecard (0-100): {scorecard}

Output requirements:
1) Return strict JSON only, no markdown and no extra keys.
2) JSON schema:
{{
  "recommendation": "Strong Sell|Sell|Neutral|Avoid",
  "confidence": 0-100 integer,
  "explanation": "single paragraph under 140 words",
  "suggested_strike": number or null,
  "suggested_delta": number or null,
  "estimated_theta": number or null,
  "estimated_vega": number or null
}}
3) If event risk flag is true, recommendation must be Avoid.
4) Confidence calibration:
- Strong Sell should generally be >=75
- Sell should generally be 60-80
- Neutral 40-65
- Avoid 0-55
5) Use conservative assumptions; never suggest auto-trading.
""".strip()

