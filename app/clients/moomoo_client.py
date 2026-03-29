from __future__ import annotations

from typing import Any

from structlog import get_logger

from app.config import get_settings

logger = get_logger(__name__)


class MoomooClient:
    """Moomoo OpenAPI client using the official Python SDK.

    The client connects to the local OpenD daemon (default localhost:11111).
    OpenD must be installed and running: https://www.moomoo.com/download/OpenAPI

    Architecture:
    - Quote context: snapshot, options chain, Greeks.
    - Trade context: account balances, positions.
    - Both run via local binary protocol (not REST).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.host = settings.moomoo_opend_host
        self.port = settings.moomoo_opend_port
        self._quote_ctx = None
        self._trade_ctx = None

    def _ensure_quote_ctx(self):
        if self._quote_ctx is None:
            try:
                from moomoo import OpenQuoteContext

                self._quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
                logger.info("moomoo_quote_context_opened", host=self.host, port=self.port)
            except ImportError as e:
                logger.error("moomoo_import_error", error=str(e))
                raise RuntimeError(
                    "moomoo-api not installed or OpenD not running on localhost:11111"
                ) from e
            except Exception as e:
                logger.error("moomoo_quote_context_error", error=str(e))
                raise

    def _ensure_trade_ctx(self):
        if self._trade_ctx is None:
            try:
                from moomoo import OpenSecTradeContext

                self._trade_ctx = OpenSecTradeContext(host=self.host, port=self.port)
                logger.info("moomoo_trade_context_opened", host=self.host, port=self.port)
            except ImportError as e:
                logger.error("moomoo_import_error", error=str(e))
                raise RuntimeError(
                    "moomoo-api not installed or OpenD not running on localhost:11111"
                ) from e
            except Exception as e:
                logger.error("moomoo_trade_context_error", error=str(e))
                raise

    def get_account_balances(self, account_id: str | None = None) -> dict[str, Any]:
        """Get account balance and equity details."""
        self._ensure_trade_ctx()
        try:
            ret, data = self._trade_ctx.get_acc_balance()
            if ret == 0 and data is not None:
                # Convert DataFrame to dict for JSON serialization
                return {
                    "net_asset": float(data.iloc[0]["net_asset"]) if len(data) > 0 else 0.0,
                    "equity": float(data.iloc[0]["total_assets"]) if len(data) > 0 else 0.0,
                    "raw": data.to_dict("records"),
                }
            else:
                logger.error("moomoo_balance_error", ret=ret)
                return {"net_asset": 0.0, "equity": 0.0, "error": f"ret={ret}"}
        except Exception as e:
            logger.exception("moomoo_get_balances_error", error=str(e))
            return {"net_asset": 0.0, "equity": 0.0, "error": str(e)}

    def get_option_positions(self, account_id: str | None = None) -> list[dict[str, Any]]:
        """Get open option positions from the account.

        Args:
            account_id: ignored (included for compatibility); OpenD manages account context.

        Returns:
            List of option position dicts with symbol, qty, delta, vega, market_val, etc.
        """
        self._ensure_trade_ctx()
        try:
            ret, data = self._trade_ctx.get_position_list_in_day()
            if ret == 0 and data is not None:
                positions = []
                for _, row in data.iterrows():
                    ticker = str(row.get("code", ""))
                    # Filter for options (typically contain 'OPTION' or special formatting)
                    if "OPTION" in str(row.get("sec_type", "")).upper() or (
                        ticker and len(ticker) > 10
                    ):
                        positions.append({
                            "symbol": ticker,
                            "qty": float(row.get("qty", 0.0) or 0.0),
                            "quantity": float(row.get("qty", 0.0) or 0.0),
                            "delta": 0.0,  # Greeks will be fetched separately via get_position_greeks
                            "vega": 0.0,
                            "market_val": float(row.get("market_val", 0.0) or 0.0),
                            "market_value": float(row.get("market_val", 0.0) or 0.0),
                            "sec_type": str(row.get("sec_type", "")),
                            "raw": row.to_dict(),
                        })
                return positions
            else:
                logger.error("moomoo_positions_error", ret=ret)
                return []
        except Exception as e:
            logger.exception("moomoo_get_positions_error", error=str(e))
            return []

    def get_position_greeks(self) -> list[dict[str, Any]]:
        """Get position Greeks (delta, vega, theta, etc.) from all open positions."""
        self._ensure_trade_ctx()
        try:
            ret, data = self._trade_ctx.get_position_greeks()
            if ret == 0 and data is not None:
                greeks = []
                for _, row in data.iterrows():
                    greeks.append({
                        "symbol": str(row.get("code", "")),
                        "delta": float(row.get("delta", 0.0) or 0.0),
                        "gamma": float(row.get("gamma", 0.0) or 0.0),
                        "theta": float(row.get("theta", 0.0) or 0.0),
                        "vega": float(row.get("vega", 0.0) or 0.0),
                        "rho": float(row.get("rho", 0.0) or 0.0),
                        "raw": row.to_dict(),
                    })
                return greeks
            else:
                logger.error("moomoo_greeks_error", ret=ret)
                return []
        except Exception as e:
            logger.exception("moomoo_get_greeks_error", error=str(e))
            return []

    def get_snapshot(self, symbol: str) -> dict[str, Any]:
        """Get real-time quote snapshot for a symbol (including underlier or USD.HKD, etc.).

        Args:
            symbol: ticker code e.g. 'HK.00700', 'US.AAPL', 'USD.HKD'

        Returns:
            snapshot dict with last_price, bid, ask, volume, etc.
        """
        self._ensure_quote_ctx()
        try:
            ret, data = self._quote_ctx.get_market_snapshot([symbol])
            if ret == 0 and data is not None and len(data) > 0:
                row = data.iloc[0]
                return {
                    "code": str(row.get("code", "")),
                    "last_price": float(row.get("last_price", 0.0) or 0.0),
                    "bid": float(row.get("bid_price", 0.0) or 0.0),
                    "ask": float(row.get("ask_price", 0.0) or 0.0),
                    "volume": int(row.get("volume", 0) or 0),
                    "turnover": float(row.get("turnover", 0.0) or 0.0),
                    "raw": row.to_dict(),
                }
            else:
                logger.error("moomoo_snapshot_error", ret=ret, symbol=symbol)
                return {}
        except Exception as e:
            logger.exception("moomoo_get_snapshot_error", error=str(e))
            return {}

    def close(self) -> None:
        """Close OpenD connections."""
        try:
            if self._quote_ctx:
                self._quote_ctx.close()
            if self._trade_ctx:
                self._trade_ctx.close()
            logger.info("moomoo_contexts_closed")
        except Exception as e:
            logger.exception("moomoo_close_error", error=str(e))

