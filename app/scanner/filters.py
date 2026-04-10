"""Scanner filter helpers for expiry and liquidity checks."""

from __future__ import annotations

import re
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


def _parse_option_contract(option_symbol: str) -> tuple[str, float] | None:
    match = re.search(r"\d{6}([CP])(\d+)(?:\.\d+)?$", option_symbol)
    if match is None:
        return None

    option_type = match.group(1)
    strike_raw = match.group(2)
    # OCC-style strike encoding: last 3 digits are fractional precision placeholders.
    strike = int(strike_raw) / 1000.0
    return option_type, strike


def _is_option_otm(option_symbol: str, underlying_price: float) -> bool:
    parsed = _parse_option_contract(option_symbol)
    if parsed is None:
        return False

    option_type, strike = parsed
    # Project strategy definition:
    # - Call OTM when strike is above spot
    # - Put OTM when strike is below spot
    if option_type == "C":
        return strike > underlying_price
    return strike < underlying_price


def _is_last_price_above_threshold(last_price: float, min_price: float = 1.0) -> bool:
    """Check if an option's last price meets the minimum threshold."""
    return last_price > min_price

