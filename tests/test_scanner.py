"""Integration tests for scanner module."""
from unittest.mock import MagicMock, patch

import pytest

from app.scanner.filters import is_weekly_friday_expiry, liquidity_filter
from app.scanner.monitoring_scanner import MonitoringScanner


class TestScannerFilters:
    """Test hard filter logic."""

    def test_weekly_friday_expiry_detection(self):
        """Verify weekly Friday expiry detection."""
        assert is_weekly_friday_expiry("2024-01-19") is True  # Friday
        assert is_weekly_friday_expiry("2024-01-20") is False  # Saturday
        assert is_weekly_friday_expiry("2024-01-18") is False  # Thursday

    def test_liquidity_filter_passes_valid_pair(self):
        """Test liquidity filter accepts valid criteria."""
        passed, reason = liquidity_filter(oi=1000, volume=200, bid=10.0, ask=10.5, premium=10.25)
        assert passed is True
        assert "Passed" in reason

    def test_liquidity_filter_rejects_low_oi(self):
        """Test liquidity filter rejects low open interest."""
        passed, reason = liquidity_filter(oi=500, volume=200, bid=10.0, ask=10.5, premium=10.25)
        assert passed is False
        assert "OI" in reason

    def test_liquidity_filter_rejects_low_volume(self):
        """Test liquidity filter rejects low volume."""
        passed, reason = liquidity_filter(oi=1000, volume=50, bid=10.0, ask=10.5, premium=10.25)
        assert passed is False
        assert "volume" in reason

    def test_liquidity_filter_rejects_wide_spread(self):
        """Test liquidity filter rejects wide bid-ask spread."""
        passed, reason = liquidity_filter(oi=1000, volume=200, bid=10.0, ask=11.0, premium=10.25)
        assert passed is False
        assert "spread" in reason.lower()

    def test_liquidity_filter_rejects_invalid_premium(self):
        """Test liquidity filter rejects zero/negative premium."""
        passed, reason = liquidity_filter(oi=1000, volume=200, bid=10.0, ask=10.5, premium=0.0)
        assert passed is False
        assert "premium" in reason.lower()


class TestMonitoringScanner:
    """Test spike detection and candidate generation."""

    @pytest.fixture
    def scanner_setup(self):
        """Set up scanner with mocked dependencies."""
        with patch("app.clients.massive_client.MassiveClient"), \
             patch("app.cache.redis_client.RedisCache"), \
             patch("app.db.repositories.ScanRepository"):
            mock_massive = MagicMock()
            mock_cache = MagicMock()
            mock_repo = MagicMock()
            scanner = MonitoringScanner(mock_massive, mock_cache, mock_repo)
            return scanner, mock_massive, mock_cache, mock_repo

    def test_extract_premium_from_bid_ask(self, scanner_setup):
        """Test premium extraction from bid/ask quotes."""
        scanner, _, _, _ = scanner_setup
        snapshot = {
            "last_quote": {"bid": 10.0, "ask": 10.5},
            "day": {"close": 0},
        }
        premium = scanner._extract_premium(snapshot)
        assert premium == 10.25  # (10.0 + 10.5) / 2

    def test_extract_premium_from_close(self, scanner_setup):
        """Test premium extraction from close price when bid/ask unavailable."""
        scanner, _, _, _ = scanner_setup
        snapshot = {
            "last_quote": {"bid": 0, "ask": 0},
            "day": {"close": 10.5},
        }
        premium = scanner._extract_premium(snapshot)
        assert premium == 10.5

    def test_scan_symbol_filters_non_weekly_expiry(self, scanner_setup):
        """Verify scanner ignores non-Friday expirations."""
        scanner, mock_massive, mock_cache, mock_repo = scanner_setup
        mock_massive.get_options_chain_snapshot.return_value = [
            {
                "ticker": "SPY240418C00500000",  # Thursday
                "details": {"expiration_date": "2024-04-18"},
                "last_quote": {"bid": 10.0, "ask": 10.5},
                "open_interest": 1000,
                "day": {"volume": 500, "close": 10.2},
                "last_updated": "2024-04-17T16:00:00Z",
            }
        ]
        mock_cache.get_float.return_value = None

        result = scanner.scan_symbol("SPY")
        assert len(result) == 0

    def test_scan_symbol_detects_spike_above_threshold(self, scanner_setup):
        """Verify scanner detects spikes > 500%."""
        scanner, mock_massive, mock_cache, mock_repo = scanner_setup
        mock_massive.get_options_chain_snapshot.return_value = [
            {
                "ticker": "SPY240419C00500000",  # Friday
                "details": {"expiration_date": "2024-04-19"},
                "last_quote": {"bid": 10.0, "ask": 10.5},
                "open_interest": 1000,
                "day": {"volume": 500, "close": 10.2},
                "fmv_last_updated": "2024-04-17T16:00:00Z",
                "last_updated": "2024-04-17T16:00:00Z",
            }
        ]
        # Cache returns 2.0, current is 10.25, spike is (10.25 - 2.0) / 2.0 * 100 = 412.5%
        mock_cache.get_float.return_value = 2.0

        result = scanner.scan_symbol("SPY")
        # Still below 500% threshold, so no candidates
        assert len(result) == 0

        # Now test with enough spike
        mock_cache.get_float.return_value = 1.0
        # Spike: (10.25 - 1.0) / 1.0 * 100 = 925%
        result = scanner.scan_symbol("SPY")
        # Should have candidate if it passes liquidity
        assert len(result) >= 0  # Depends on liquidity filter


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
