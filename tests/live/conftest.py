from __future__ import annotations

import os
import socket
from collections.abc import Generator

import pytest
import redis
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.logging import configure_logging


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    return lowered in {
        "",
        "changeme",
        "your_api_key_here",
        "your_massive_api_key_here",
        "your_alpha_vantage_api_key_here",
        "your_gemini_api_key_here",
        "none",
        "null",
    }


def _socket_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _db_reachable(dsn: str) -> bool:
    try:
        engine = create_engine(dsn, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _redis_reachable(url: str) -> bool:
    try:
        client = redis.from_url(url)
        client.ping()
        return True
    except Exception:
        return False


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run live tests that hit external providers and local infra",
    )


@pytest.fixture(autouse=True)
def require_run_live(request: pytest.FixtureRequest) -> None:
    if not request.config.getoption("--run-live"):
        pytest.skip("live tests are disabled; rerun with --run-live")


@pytest.fixture(scope="session", autouse=True)
def configure_live_logging() -> None:
    configure_logging("INFO")


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def live_symbols() -> dict[str, str]:
    return {
        "massive_symbol": os.getenv("LIVE_MASSIVE_SYMBOL", "SPY"),
        "alpha_vantage_symbol": os.getenv("LIVE_ALPHA_VANTAGE_SYMBOL", "PLTR"),
        "moomoo_quote_symbol": os.getenv("LIVE_MOOMOO_QUOTE_SYMBOL", "HK.00700"),
        "moomoo_option_symbol": os.getenv("LIVE_MOOMOO_OPTION_SYMBOL", "HK.00700"),
    }


@pytest.fixture(scope="session")
def require_massive(settings) -> None:
    if _is_placeholder(settings.massive_api_key):
        pytest.skip("MASSIVE_API_KEY is missing or placeholder")


@pytest.fixture(scope="session")
def require_alpha_vantage(settings) -> None:
    if _is_placeholder(settings.alpha_vantage_api_key):
        pytest.skip("ALPHA_VANTAGE_API_KEY is missing or placeholder")


@pytest.fixture(scope="session")
def require_moomoo(settings) -> None:
    if not _socket_open(settings.moomoo_opend_host, settings.moomoo_opend_port):
        pytest.skip(
            f"Moomoo OpenD not reachable at {settings.moomoo_opend_host}:{settings.moomoo_opend_port}"
        )


@pytest.fixture(scope="session")
def require_gemini(settings) -> None:
    if _is_placeholder(settings.gemini_api_key):
        pytest.skip("GEMINI_API_KEY is missing or placeholder")


@pytest.fixture(scope="session")
def require_data_infra(settings) -> None:
    if not _db_reachable(settings.postgres_dsn):
        pytest.skip("PostgreSQL is not reachable")
    if not _redis_reachable(settings.redis_url):
        pytest.skip("Redis is not reachable")
