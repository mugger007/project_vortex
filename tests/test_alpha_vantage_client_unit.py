from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.clients.alpha_vantage_client import AlphaVantageClient


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _FakeHttpClient:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[dict] = []

    def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        self.calls.append({"url": url, "params": params or {}})
        return _FakeResponse(self.response_text)


def _make_client(monkeypatch, response_text: str = "") -> tuple[AlphaVantageClient, _FakeHttpClient]:
    fake_http = _FakeHttpClient(response_text=response_text)
    monkeypatch.setattr(
        "app.clients.alpha_vantage_client.get_settings",
        lambda: SimpleNamespace(alpha_vantage_api_key="unit-test-key"),
    )
    monkeypatch.setattr("app.clients.alpha_vantage_client.httpx.Client", lambda timeout=30.0: fake_http)
    return AlphaVantageClient(), fake_http


def test_earnings_calendar_filters_to_requested_symbol(monkeypatch) -> None:
    csv_text = "symbol,name,reportDate\nAAPL,Apple Inc,2026-05-01\nMSFT,Microsoft,2026-05-02\n"
    client, fake_http = _make_client(monkeypatch, response_text=csv_text)

    rows = client.get_earnings_calendar(symbol="AAPL")

    assert len(fake_http.calls) == 1
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"


def test_rate_limit_blocks_after_max_requests(monkeypatch) -> None:
    csv_text = "symbol,name,reportDate\nAAPL,Apple Inc,2026-05-01\n"
    client, fake_http = _make_client(monkeypatch, response_text=csv_text)

    for _ in range(client.MAX_REQUESTS_PER_DAY):
        rows = client.get_earnings_calendar(symbol="AAPL")
        assert len(rows) == 1

    blocked_rows = client.get_earnings_calendar(symbol="AAPL")

    assert blocked_rows == []
    assert len(fake_http.calls) == client.MAX_REQUESTS_PER_DAY


def test_rate_limit_counter_resets_when_utc_day_changes(monkeypatch) -> None:
    csv_text = "symbol,name,reportDate\nAAPL,Apple Inc,2026-05-01\n"
    client, _ = _make_client(monkeypatch, response_text=csv_text)

    client._request_count_today = client.MAX_REQUESTS_PER_DAY
    client._rate_limit_day = datetime.now(UTC).date() - timedelta(days=1)

    allowed = client._allow_request()

    assert allowed is True
    assert client._request_count_today == 1
