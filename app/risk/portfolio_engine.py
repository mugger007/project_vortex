"""Portfolio risk checks for candidate trade approval."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.clients.massive_client import MassiveClient
from app.clients.moomoo_client import MoomooClient
from app.models.schemas import RiskDecision


class PortfolioRiskEngine:
    def __init__(self, moomoo: MoomooClient, massive: MassiveClient, account_id: str = "default") -> None:
        """Create a portfolio risk evaluator backed by Moomoo and Massive data."""
        self.moomoo = moomoo
        self.massive = massive
        self.account_id = account_id

    def _underlying_from_option(self, option_symbol: str) -> str:
        """Extract the underlying ticker from a Moomoo-style option symbol."""
        return option_symbol.split("2", 1)[0][:5].replace("O:", "")

    def _build_corr(self, symbols: list[str]) -> pd.DataFrame:
        """Build a correlation matrix from recent underlying return series."""
        series = {}
        for symbol in symbols:
            bars = self.massive.get_underlying_bars(symbol, timespan="day", limit=90)
            if not bars:
                continue
            df = pd.DataFrame(bars)
            if "c" not in df.columns:
                continue
            series[symbol] = np.log(df["c"] / df["c"].shift(1)).dropna().reset_index(drop=True)
        if not series:
            return pd.DataFrame()
        joined = pd.DataFrame(series).dropna()
        if joined.empty:
            return pd.DataFrame()
        return joined.corr()

    def evaluate(self, symbol: str, candidate_delta: float, candidate_vega: float) -> RiskDecision:
        """Approve or reject a candidate based on portfolio delta, vega, and correlation."""
        balances = self.moomoo.get_account_balances()
        positions = self.moomoo.get_option_positions()
        greeks_list = self.moomoo.get_position_greeks()

        # Build a dict of symbol -> greeks for quick lookup
        greeks_map = {g["symbol"]: g for g in greeks_list}

        capital = float(balances.get("total_assets", 100000) or 100000)
        max_trade_value = 0.05 * capital

        # Merge greeks into positions
        for p in positions:
            symbol_key = p.get("symbol", "")
            if symbol_key in greeks_map:
                p["delta"] = greeks_map[symbol_key].get("delta", 0.0)
                p["vega"] = greeks_map[symbol_key].get("vega", 0.0)

        total_delta = float(sum(float(p.get("delta", 0.0) or 0.0) for p in positions)) + candidate_delta
        total_vega = float(sum(float(p.get("vega", 0.0) or 0.0) for p in positions)) + candidate_vega

        if abs(total_delta) > capital * 0.001:
            return RiskDecision(
                approved=False,
                reason="Portfolio delta limit breached",
                risk_score=15,
                expected_max_drawdown=0.2,
                correlation_max=1.0,
                proposed_size_pct=0.0,
            )

        if abs(total_vega) > capital * 0.0008:
            return RiskDecision(
                approved=False,
                reason="Portfolio vega limit breached",
                risk_score=20,
                expected_max_drawdown=0.25,
                correlation_max=1.0,
                proposed_size_pct=0.0,
            )

        current_underlyings = [self._underlying_from_option(str(p.get("symbol", ""))) for p in positions]
        current_underlyings = [u for u in current_underlyings if u]
        corr_max = 0.0
        if current_underlyings:
            corr = self._build_corr(list(set(current_underlyings + [symbol])))
            if not corr.empty and symbol in corr.columns:
                corr_max = float(corr[symbol].drop(labels=[symbol], errors="ignore").max() or 0.0)
                if corr_max > 0.7:
                    return RiskDecision(
                        approved=False,
                        reason=f"Correlation too high ({corr_max:.2f})",
                        risk_score=30,
                        expected_max_drawdown=0.18,
                        correlation_max=corr_max,
                        proposed_size_pct=0.0,
                    )

        drawdown_est = min(0.35, abs(total_delta) / max(capital, 1) * 8 + abs(total_vega) / max(capital, 1) * 8)
        if drawdown_est > 0.15:
            return RiskDecision(
                approved=False,
                reason="Expected max drawdown too high",
                risk_score=25,
                expected_max_drawdown=drawdown_est,
                correlation_max=corr_max,
                proposed_size_pct=0.0,
            )

        proposed_size = min(5.0, max_trade_value / max(capital, 1) * 100)
        return RiskDecision(
            approved=True,
            reason="Risk checks passed",
            risk_score=80,
            expected_max_drawdown=drawdown_est,
            correlation_max=corr_max,
            proposed_size_pct=proposed_size,
        )

