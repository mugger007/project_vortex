"""Time and calendar utility helpers used across the application."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)

