from __future__ import annotations


def is_weekly_friday_expiry(expiry: str) -> bool:
    # Expiry format expected YYYY-MM-DD. US equity weekly options expire on Friday.
    if len(expiry) != 10:
        return False
    year, month, day = map(int, expiry.split("-"))
    import datetime as dt

    return dt.date(year, month, day).weekday() == 4


def liquidity_filter(oi: int, volume: int, bid: float, ask: float, premium: float) -> tuple[bool, str]:
    if oi <= 750:
        return False, "Rejected: OI <= 750"
    if volume <= 100:
        return False, "Rejected: volume <= 100/day"
    spread = max(ask - bid, 0.0)
    if premium <= 0:
        return False, "Rejected: invalid premium"
    if spread / premium >= 0.10:
        return False, "Rejected: bid-ask spread >= 10% premium"
    return True, "Passed liquidity"
