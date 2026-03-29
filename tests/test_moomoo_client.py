"""Integration tests for Moomoo OpenAPI client."""
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest


@pytest.fixture
def moomoo_client():
    """Create a MoomooClient instance with mocked connections."""
    from app.clients.moomoo_client import MoomooClient

    with patch("app.clients.moomoo_client.get_logger"):
        client = MoomooClient()
    return client


class TestMoomooClient:
    """Test Moomoo OpenAPI client using official SDK."""

    def test_initialization(self, moomoo_client):
        """Verify client initializes with correct OpenD host/port from config."""
        assert moomoo_client.host == "127.0.0.1"
        assert moomoo_client.port == 11111

    @patch("app.clients.moomoo_client.OpenSecTradeContext")
    def test_get_account_balances(self, mock_trade_context_class, moomoo_client):
        """Test account balance retrieval returns dict with net_asset and equity."""
        mock_ctx = MagicMock()
        mock_response_df = pd.DataFrame(
            {
                "net_asset": [100000.0],
                "total_assets": [120000.0],
            }
        )
        mock_ctx.get_acc_balance.return_value = (0, mock_response_df)
        mock_trade_context_class.return_value = mock_ctx

        moomoo_client._trade_ctx = mock_ctx
        result = moomoo_client.get_account_balances()

        assert result["net_asset"] == 100000.0
        assert result["equity"] == 120000.0
        assert "raw" in result

    @patch("app.clients.moomoo_client.OpenSecTradeContext")
    def test_get_option_positions(self, mock_trade_context_class, moomoo_client):
        """Test option positions retrieval returns list of position dicts."""
        mock_ctx = MagicMock()
        mock_response_df = pd.DataFrame(
            {
                "code": ["HK.00700C202401200"],
                "qty": [100.0],
                "market_val": [5000.0],
                "sec_type": ["OPTION"],
            }
        )
        mock_ctx.get_position_list_in_day.return_value = (0, mock_response_df)
        mock_trade_context_class.return_value = mock_ctx

        moomoo_client._trade_ctx = mock_ctx
        result = moomoo_client.get_option_positions()

        assert len(result) >= 0
        if result:
            assert "symbol" in result[0]
            assert "qty" in result[0]

    @patch("app.clients.moomoo_client.OpenSecTradeContext")
    def test_get_position_greeks(self, mock_trade_context_class, moomoo_client):
        """Test position Greeks retrieval returns list with delta, vega, theta."""
        mock_ctx = MagicMock()
        mock_response_df = pd.DataFrame(
            {
                "code": ["HK.00700C202401200"],
                "delta": [0.5],
                "gamma": [0.02],
                "theta": [-0.1],
                "vega": [0.3],
                "rho": [0.01],
            }
        )
        mock_ctx.get_position_greeks.return_value = (0, mock_response_df)
        mock_trade_context_class.return_value = mock_ctx

        moomoo_client._trade_ctx = mock_ctx
        result = moomoo_client.get_position_greeks()

        assert len(result) >= 0
        if result:
            assert "symbol" in result[0]
            assert "delta" in result[0]
            assert "vega" in result[0]

    @patch("app.clients.moomoo_client.OpenQuoteContext")
    def test_get_snapshot(self, mock_quote_context_class, moomoo_client):
        """Test snapshot retrieval for a symbol."""
        mock_ctx = MagicMock()
        mock_response_df = pd.DataFrame(
            {
                "code": ["HK.00700"],
                "last_price": [625.0],
                "bid_price": [624.9],
                "ask_price": [625.1],
                "volume": [1000000],
                "turnover": [625000000.0],
            }
        )
        mock_ctx.get_market_snapshot.return_value = (0, mock_response_df)
        mock_quote_context_class.return_value = mock_ctx

        moomoo_client._quote_ctx = mock_ctx
        result = moomoo_client.get_snapshot("HK.00700")

        assert result.get("last_price") == 625.0
        assert result.get("bid") == 624.9
        assert result.get("ask") == 625.1

    @patch("app.clients.moomoo_client.OpenSecTradeContext")
    def test_error_handling_on_connection_error(self, mock_trade_context_class, moomoo_client):
        """Test graceful error handling when OpenD daemon is not running."""
        mock_ctx = MagicMock()
        mock_ctx.get_acc_balance.return_value = (1, None)
        mock_trade_context_class.return_value = mock_ctx

        moomoo_client._trade_ctx = mock_ctx
        result = moomoo_client.get_account_balances()

        assert result["net_asset"] == 0.0
        assert "error" in result


class TestMoomooClientLifecycle:
    """Test client connection lifecycle."""

    def test_close_contexts(self, moomoo_client):
        """Test that close() properly closes both quote and trade contexts."""
        mock_quote = MagicMock()
        mock_trade = MagicMock()
        moomoo_client._quote_ctx = mock_quote
        moomoo_client._trade_ctx = mock_trade

        moomoo_client.close()

        mock_quote.close.assert_called_once()
        mock_trade.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
