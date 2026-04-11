"""Prompt construction helpers for recommendation synthesis."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.models.schemas import AnalysisBundle, FilteredCandidate, RiskDecision


def _extract_strike(option_symbol: str, candidate: FilteredCandidate) -> float | None:
    chain = candidate.snapshot.extra.get("chain", {})
    chain_strike = chain.get("strike_price") if isinstance(chain, dict) else None
    if chain_strike is None and isinstance(chain, dict):
        chain_strike = chain.get("strike")

    try:
        if chain_strike is not None:
            return float(chain_strike)
    except (TypeError, ValueError):
        pass

    match = re.search(r"\d{6}[CP](\d+)(?:\.\d+)?$", option_symbol)
    if match is None:
        return None

    try:
        return int(match.group(1)) / 1000.0
    except ValueError:
        return None


def _extract_underlying_spot(candidate: FilteredCandidate) -> float | None:
    extra = candidate.snapshot.extra
    sources: list[dict[str, Any]] = []
    if isinstance(extra, dict):
        sources.append(extra)
        snapshot = extra.get("snapshot")
        chain = extra.get("chain")
        if isinstance(snapshot, dict):
            sources.append(snapshot)
        if isinstance(chain, dict):
            sources.append(chain)

    for source in sources:
        for key in ("underlying_price", "underlying_last_price", "stock_price", "owner_price", "underlying_last"):
            raw = source.get(key)
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
    return None


def _days_to_expiry(expiry: str) -> int | None:
    try:
        expiry_date = datetime.fromisoformat(expiry).date()
    except ValueError:
        return None

    today = datetime.now(UTC).date()
    return (expiry_date - today).days


def build_synthesis_prompt(
    candidate: FilteredCandidate,
    analysis: AnalysisBundle,
    risk: RiskDecision | None,
    scorecard: int,
) -> str:
    """Build the strict-JSON Gemini prompt for final recommendation synthesis."""
    strike = _extract_strike(candidate.option_symbol, candidate)
    spot = _extract_underlying_spot(candidate)
    expiry_days = _days_to_expiry(candidate.expiry)

    strike_text = f"{strike:.4f}" if strike is not None else "unknown"
    spot_text = f"{spot:.4f}" if spot is not None else "unknown"
    expiry_days_text = str(expiry_days) if expiry_days is not None else "unknown"
    if strike is not None and spot is not None and spot > 0:
        moneyness_text = f"{(strike / spot):.6f}"
    else:
        moneyness_text = "unknown"

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
- Days to expiry: {expiry_days_text}
- Strike: {strike_text}
- Underlying last price: {spot_text}
- Spot (underlying): {spot_text}
- Moneyness ratio (strike/spot): {moneyness_text}
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

