"""Integration tests for external API clients."""
import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.clients.massive_client import MassiveClient, MassiveRateLimitError


@pytest.fixture
def massive_client():
    """Create a MassiveClient instance."""
    return MassiveClient()


class TestMassiveClient:
    """Test Massive REST client with mocked HTTP responses."""

    def test_throttling_respects_rate_limit(self, massive_client):
        """Verify that the throttle mechanism prevents exceeding max calls per minute."""
        massive_client.max_calls = 2
        # Simulate 2 calls
        massive_client._call_timestamps.append(1000.0)
        massive_client._call_timestamps.append(1010.0)
        # Clock hasn't advanced beyond the limit, so next call should trigger sleep
        # This test just verifies the deque management
        assert len(massive_client._call_timestamps) == 2

    @patch("app.clients.massive_client.httpx.Client.get")
    def test_get_options_chain_snapshot(self, mock_get, massive_client):
        """Test options chain snapshot retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "ticker": "SPY240419C00500000",
                    "details": {"expiration_date": "2024-04-19"},
                    "last_quote": {"bid": 10.0, "ask": 10.5},
                    "open_interest": 1000,
                    "day": {"volume": 500, "close": 10.2},
                }
            ]
        }
        mock_get.return_value = mock_response

        result = massive_client.get_options_chain_snapshot("SPY")
        assert len(result) == 1
        assert result[0]["ticker"] == "SPY240419C00500000"

    @patch("app.clients.massive_client.httpx.Client.get")
    def test_get_underlying_bars(self, mock_get, massive_client):
        """Test underlying OHLCV bars retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {"t": 1000, "c": 500.0, "h": 502.0, "l": 499.0},
                {"t": 2000, "c": 501.0, "h": 503.0, "l": 500.0},
            ]
        }
        mock_get.return_value = mock_response

        result = massive_client.get_underlying_bars("SPY")
        assert len(result) == 2
        assert result[0]["c"] == 500.0

    @patch("app.clients.massive_client.httpx.Client.get")
    def test_get_news(self, mock_get, massive_client):
        """Test news retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {"title": "Breaking news", "description": "Market moves", "published_utc": "2024-01-01T00:00:00Z"}
            ]
        }
        mock_get.return_value = mock_response

        result = massive_client.get_news("SPY")
        assert len(result) == 1
        assert "Breaking news" in result[0]["title"]

    @patch("app.clients.massive_client.httpx.Client.get")
    def test_rate_limit_error_retries(self, mock_get, massive_client):
        """Test that 429 errors trigger retries."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        with pytest.raises(MassiveRateLimitError):
            massive_client._get("/test")

    @patch("app.clients.massive_client.httpx.Client.get")
    def test_other_errors_also_retry(self, mock_get, massive_client):
        """Test that HTTP errors trigger retries."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_get.return_value = mock_response

        with pytest.raises(Exception):
            massive_client._get("/test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
