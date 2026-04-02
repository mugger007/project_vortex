from __future__ import annotations

from datetime import UTC, datetime


def _is_expiry_in_current_week(expiry: str) -> bool:
    try:
        expiry_date = datetime.fromisoformat(expiry).date()
    except ValueError:
        return False

    current_date = datetime.now(UTC).date()
    expiry_year, expiry_week, _ = expiry_date.isocalendar()
    current_year, current_week, _ = current_date.isocalendar()
    return (expiry_year, expiry_week) == (current_year, current_week)


def liquidity_filter(oi: int, volume: int, bid: float, ask: float, premium: float) -> tuple[bool, str]:
    if oi <= 500:
        return False, "Rejected: OI <= 500"
    # spread = max(ask - bid, 0.0)
    if premium <= 0:
        return False, "Rejected: invalid premium"
    # if spread / premium >= 0.01:
        # return False, "Rejected: bid-ask spread >= 1% premium"
    return True, "Passed liquidity"
