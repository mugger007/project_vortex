"""Moomoo OpenD client for quotes, options, and account data."""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Any

from structlog import get_logger

from app.config import get_settings

logger = get_logger(__name__)


class MoomooClient:
    """Moomoo OpenAPI client using the official Python SDK via local OpenD daemon.

    The OpenD daemon provides all data through a local binary protocol connection (localhost:11111).
    OpenD must be installed and running: https://www.moomoo.com/download/OpenAPI

    Methods available:
    - Account/Portfolio: get_account_balances(), get_option_positions()
    - Options: get_option_expiration_date(), get_option_chain()
    - Position Greeks: get_position_greeks()
    - Quotes: get_snapshot()
    
    All methods return moomoo-api SDK objects (typically pandas DataFrames or tuples).
    """

    SNAPSHOT_RATE_LIMIT = 60
    SNAPSHOT_RATE_WINDOW_SECONDS = 30
    OPTION_EXPIRATION_RATE_LIMIT = 60
    OPTION_EXPIRATION_RATE_WINDOW_SECONDS = 30
    OPTION_CHAIN_RATE_LIMIT = 10
    OPTION_CHAIN_RATE_WINDOW_SECONDS = 30

    def __init__(self) -> None:
        settings = get_settings()
        self.host = settings.moomoo_opend_host
        self.port = settings.moomoo_opend_port
        self._quote_ctx = None
        self._trade_ctx = None
        self._snapshot_call_times: deque[float] = deque()
        self._snapshot_rate_lock = threading.Lock()
        self._option_expiration_call_times: deque[float] = deque()
        self._option_expiration_rate_lock = threading.Lock()
        self._option_chain_call_times: deque[float] = deque()
        self._option_chain_rate_lock = threading.Lock()

    def _respect_rate_limit(
        self,
        call_times: deque[float],
        rate_lock: threading.Lock,
        rate_limit: int,
        window_seconds: int,
        log_event: str,
        request_count: int = 1,
    ) -> None:
        while True:
            with rate_lock:
                now = time.monotonic()
                window_start = now - window_seconds

                while call_times and call_times[0] <= window_start:
                    call_times.popleft()

                if len(call_times) + request_count <= rate_limit:
                    for _ in range(request_count):
                        call_times.append(now)
                    return

                wait_seconds = call_times[0] + window_seconds - now

            if wait_seconds > 0:
                logger.info(
                    log_event,
                    wait_seconds=round(wait_seconds, 3),
                    queued_calls=len(call_times),
                    limit=rate_limit,
                    window_seconds=window_seconds,
                )
                time.sleep(wait_seconds)

    def _respect_snapshot_rate_limit(self, request_count: int = 1) -> None:
        self._respect_rate_limit(
            call_times=self._snapshot_call_times,
            rate_lock=self._snapshot_rate_lock,
            rate_limit=self.SNAPSHOT_RATE_LIMIT,
            window_seconds=self.SNAPSHOT_RATE_WINDOW_SECONDS,
            log_event="moomoo_snapshot_rate_limited",
            request_count=request_count,
        )

    def _respect_option_expiration_rate_limit(self, request_count: int = 1) -> None:
        self._respect_rate_limit(
            call_times=self._option_expiration_call_times,
            rate_lock=self._option_expiration_rate_lock,
            rate_limit=self.OPTION_EXPIRATION_RATE_LIMIT,
            window_seconds=self.OPTION_EXPIRATION_RATE_WINDOW_SECONDS,
            log_event="moomoo_option_expiration_rate_limited",
            request_count=request_count,
        )

    def _respect_option_chain_rate_limit(self, request_count: int = 1) -> None:
        self._respect_rate_limit(
            call_times=self._option_chain_call_times,
            rate_lock=self._option_chain_rate_lock,
            rate_limit=self.OPTION_CHAIN_RATE_LIMIT,
            window_seconds=self.OPTION_CHAIN_RATE_WINDOW_SECONDS,
            log_event="moomoo_option_chain_rate_limited",
            request_count=request_count,
        )

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
                from moomoo import OpenSecTradeContext, SecurityFirm, TrdMarket

                # Required trade context configuration from validated working setup.
                self._trade_ctx = OpenSecTradeContext(
                    filter_trdmarket=TrdMarket.US,
                    host="127.0.0.1",
                    port=11111,
                    security_firm=SecurityFirm.FUTUSG,
                )
                logger.info(
                    "moomoo_trade_context_opened",
                    host="127.0.0.1",
                    port=11111,
                    filter_trdmarket="US",
                    security_firm="FUTUSG",
                )
            except TypeError:
                # Fallback for SDK variants that do not support filter_trdmarket/security_firm.
                from moomoo import OpenSecTradeContext

                self._trade_ctx = OpenSecTradeContext(host="127.0.0.1", port=11111)
                logger.info("moomoo_trade_context_opened_fallback", host="127.0.0.1", port=11111)
            except ImportError as e:
                logger.error("moomoo_import_error", error=str(e))
                raise RuntimeError(
                    "moomoo-api not installed or OpenD not running on localhost:11111"
                ) from e
            except Exception as e:
                logger.error("moomoo_trade_context_error", error=str(e))
                raise

    def get_account_balances(self, account_id: str | None = None) -> dict[str, Any]:
        """Get account balance and equity details.
        
        Uses accinfo_query() from Moomoo SDK to fetch fund data including power, assets, and cash.
        API Reference: https://openapi.moomoo.com/moomoo-api-doc/en/trade/get-funds.html
        """
        self._ensure_trade_ctx()

        def _to_float(value: Any, default: float = 0.0) -> float:
            try:
                if value is None:
                    return default
                if isinstance(value, str) and value.strip().upper() in {"N/A", "NA", "NULL", "NONE", ""}:
                    return default
                return float(value)
            except (TypeError, ValueError):
                return default

        try:
            from moomoo import TrdEnv

            ret, data = self._trade_ctx.accinfo_query(
                trd_env=TrdEnv.REAL,
                acc_id=int(account_id) if account_id else 0,
                acc_index=0,
                refresh_cache=False,
            )
            if ret == 0 and data is not None:
                # Convert DataFrame to dict for JSON serialization.
                first = data.iloc[0] if len(data) > 0 else None
                return {
                    "trd_env": "REAL",
                    "power": _to_float(first.get("power", 0.0)) if first is not None else 0.0,
                    "net_cash_power": _to_float(first.get("net_cash_power", 0.0)) if first is not None else 0.0,
                    "total_assets": _to_float(first.get("total_assets", 0.0)) if first is not None else 0.0,
                    "securities_assets": _to_float(first.get("securities_assets", 0.0)) if first is not None else 0.0,
                    "cash": _to_float(first.get("cash", 0.0)) if first is not None else 0.0,
                    "market_val": _to_float(first.get("market_val", 0.0)) if first is not None else 0.0,
                    # Backward-compatible aliases for existing consumers.
                    "net_asset": _to_float(first.get("total_assets", 0.0)) if first is not None else 0.0,
                    "equity": _to_float(first.get("total_assets", 0.0)) if first is not None else 0.0,
                    "currency": str(first.get("currency", "")) if first is not None else "",
                    "raw": data.to_dict("records"),
                }

            details = f"REAL: ret={ret}, detail={data}"
            logger.error("moomoo_accinfo_error", detail=details)
            return {
                "power": 0.0,
                "net_cash_power": 0.0,
                "total_assets": 0.0,
                "net_asset": 0.0,
                "equity": 0.0,
                "error": details,
            }
        except Exception as e:
            logger.exception("moomoo_get_account_balances_error", error=str(e))
            return {
                "power": 0.0,
                "net_cash_power": 0.0,
                "total_assets": 0.0,
                "net_asset": 0.0,
                "equity": 0.0,
                "error": str(e),
            }

    def get_option_positions(self, account_id: str | None = None) -> list[dict[str, Any]]:
        """Get open option positions from the account.

        Args:
            account_id: ignored (included for compatibility); OpenD manages account context.

        Returns:
            List of option position dicts with symbol, qty, delta, vega, market_val, etc.
        """
        self._ensure_trade_ctx()

        def _to_float(value: Any, default: float = 0.0) -> float:
            try:
                if value is None:
                    return default
                if isinstance(value, str) and value.strip().upper() in {"N/A", "NA", "NULL", "NONE", ""}:
                    return default
                return float(value)
            except (TypeError, ValueError):
                return default

        def _convert_positions(data: Any, env_name: str) -> list[dict[str, Any]]:
            positions: list[dict[str, Any]] = []
            for _, row in data.iterrows():
                ticker = str(row.get("code", ""))
                sec_type = str(row.get("sec_type", "")).upper()
                stock_name = str(row.get("stock_name", ""))

                # Keep this method option-focused but support multiple schema variants.
                is_option = (
                    "OPTION" in sec_type
                    or "OPTION" in stock_name.upper()
                    or (ticker and len(ticker) > 10)
                )
                if not is_option:
                    continue

                qty = _to_float(row.get("qty", row.get("can_sell_qty", 0.0)))
                market_val = _to_float(row.get("market_val", row.get("nominal_price", 0.0)))

                positions.append(
                    {
                        "symbol": ticker,
                        "stock_name": stock_name,
                        "qty": qty,
                        "quantity": qty,
                        "delta": 0.0,  # Greeks are fetched separately via get_position_greeks
                        "vega": 0.0,
                        "market_val": market_val,
                        "market_value": market_val,
                        "sec_type": str(row.get("sec_type", "")),
                        "trd_env": env_name,
                        "raw": row.to_dict(),
                    }
                )
            return positions

        try:
            from moomoo import TrdEnv

            ret, data = self._trade_ctx.position_list_query(
                trd_env=TrdEnv.REAL,
                acc_id=int(account_id) if account_id else 0,
                acc_index=0,
                refresh_cache=False,
            )
            if ret == 0 and data is not None:
                positions = _convert_positions(data, "REAL")

                logger.info(
                    "moomoo_option_positions_loaded",
                    env="REAL",
                    total_positions=int(len(data)),
                    option_positions=int(len(positions)),
                )
                return positions

            details = f"REAL: ret={ret}, detail={data}"
            logger.error("moomoo_positions_error", detail=details)
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

    def get_option_expiration_date(self, symbol: str) -> list[str]:
        """Get available option expiration dates for an underlying symbol via OpenD daemon.
        
        Args:
            symbol: underlying ticker code (e.g., 'HK.00700', 'US.AAPL').
        
        Returns:
            List of expiration dates in format 'YYYY-MM-DD'.
            API Reference: https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-option-expiration-date.html
        """
        self._respect_option_expiration_rate_limit(request_count=1)
        self._ensure_quote_ctx()
        try:
            ret, data = self._quote_ctx.get_option_expiration_date(code=symbol)
            if ret == 0 and data is not None:
                return data['strike_time'].values.tolist() if 'strike_time' in data.columns else []
            else:
                logger.error("moomoo_option_expiration_error", symbol=symbol, ret=ret)
                return []
        except Exception as e:
            logger.exception("moomoo_get_expiration_error", symbol=symbol, error=str(e))
            return []
    
    def get_option_chain(self, symbol: str, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        """Get option chain data for an underlying symbol via OpenD daemon.
        
        Args:
            symbol: underlying ticker code (e.g., 'HK.00700', 'US.AAPL').
            start: start date for expiration (format 'YYYY-MM-DD'), default 30 days before end.
            end: end date for expiration (format 'YYYY-MM-DD'), default 30 days after start.
        
        Returns:
            List of option contracts with strike, expiry, Greeks, OI, volume, etc.
            API Reference: https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-option-chain.html
        """
        self._respect_option_chain_rate_limit(request_count=1)
        self._ensure_quote_ctx()
        try:
            ret, data = self._quote_ctx.get_option_chain(code=symbol, start=start, end=end)
            if ret == 0 and data is not None:
                return data.to_dict('records')
            else:
                logger.error("moomoo_option_chain_error", symbol=symbol, ret=ret)
                return []
        except Exception as e:
            logger.exception("moomoo_get_option_chain_error", symbol=symbol, error=str(e))
            return []

    def get_snapshot(self, symbol: str) -> dict[str, Any]:
        """Get real-time quote snapshot for an option symbol via OpenD daemon.

        Only accepts option-related symbols in the Moomoo format.

        Args:
            symbol: option ticker code e.g. 'US.SCO260417P8000', 'US.AAPL260419C00150000'.
                   Format: {market}.{underlying}{YYMMDD}{C|P}{strike}
                   - market: US, HK, etc (2 chars)
                   - underlying: symbol name (1-6 chars)
                   - YYMMDD: expiration date
                   - C|P: Call or Put option type
                   - strike: strike price (digits, may include decimals)

        Returns:
            snapshot dict with last_price, bid, ask, volume, etc., or empty dict if validation fails.
            
        Raises:
            ValueError: if symbol does not match the expected option format.
            
        API Reference: https://openapi.moomoo.com/moomoo-api-doc/en/quote/get-market-snapshot.html
        """
        # Validate option symbol format: {market}.{underlying}{YYMMDD}{C|P}{strike}
        # Example: US.SCO260417P8000, US.AAPL260419C00150000
        option_symbol_pattern = re.compile(r"^[A-Z]{2}\.[A-Z0-9]{1,6}\d{6}[CP]\d+(\.\d+)?$")
        
        if not option_symbol_pattern.match(symbol):
            error_msg = f"Invalid option symbol format: {symbol}. Expected format: {{market}}.{{underlying}}{{YYMMDD}}{{C|P}}{{strike}} (e.g., US.SCO260417P8000)"
            logger.error("moomoo_invalid_option_symbol", symbol=symbol, error=error_msg)
            raise ValueError(error_msg)

        self._respect_snapshot_rate_limit(request_count=1)

        self._ensure_quote_ctx()
        try:
            ret, data = self._quote_ctx.get_market_snapshot([symbol])
            if ret == 0 and data is not None and len(data) > 0:
                row = data.iloc[0]
                option_open_interest = int(row.get("option_open_interest", 0) or 0)
                return {
                    "code": str(row.get("code", "")),
                    "last_price": float(row.get("last_price", 0.0) or 0.0),
                    "prev_close_price": float(row.get("prev_close_price", 0.0) or 0.0),
                    "bid": float(row.get("bid_price", 0.0) or 0.0),
                    "ask": float(row.get("ask_price", 0.0) or 0.0),
                    "volume": int(row.get("volume", 0) or 0),
                    "option_open_interest": option_open_interest,
                    "turnover": float(row.get("turnover", 0.0) or 0.0),
                    "raw": row.to_dict(),
                }
            else:
                logger.error("moomoo_snapshot_error", ret=ret, symbol=symbol)
                return {}
        except ValueError:
            raise
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


