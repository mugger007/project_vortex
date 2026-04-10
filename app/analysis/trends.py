"""Trend scoring analysis from historical price indicators."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pandas_ta as ta
from structlog import get_logger

from app.clients.massive_client import MassiveClient


logger = get_logger(__name__)


class TrendAnalyzer:
    TARGET_BARS = 260
    LOOKBACK_CALENDAR_DAYS = 400

    def __init__(self, massive: MassiveClient) -> None:
        """Create a trend analyzer backed by Massive historical bars."""
        self.massive = massive

    def analyze(self, symbol: str) -> tuple[float, str]:
        """Score trend strength from moving averages and momentum indicators."""
        to_date = datetime.now(UTC).date() - timedelta(days=1)
        while to_date.weekday() >= 5:
            to_date -= timedelta(days=1)
        from_date = to_date - timedelta(days=self.LOOKBACK_CALENDAR_DAYS)

        logger.info(
            "trend_window_selected",
            symbol=symbol,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            limit=self.TARGET_BARS,
        )

        bars = self.massive.get_underlying_bars(
            symbol,
            timespan="day",
            limit=self.TARGET_BARS,
            from_date=from_date,
            to_date=to_date,
        )
        logger.info("trend_bars_loaded", symbol=symbol, bars_count=len(bars))
        if not bars:
            logger.warning("trend_no_bars", symbol=symbol)
            return 0.0, "No bars available"

        df = pd.DataFrame(bars)
        logger.info(
            "trend_bar_window_raw",
            symbol=symbol,
            bars_count=len(df),
            has_t="t" in df.columns,
            t_first=(int(df["t"].iloc[0]) if "t" in df.columns and not df.empty else None),
            t_last=(int(df["t"].iloc[-1]) if "t" in df.columns and not df.empty else None),
        )

        if "t" in df.columns:
            df = df.sort_values("t").reset_index(drop=True)

        if "c" not in df.columns:
            logger.warning("trend_close_missing", symbol=symbol)
            return 0.0, "Close series missing"

        df["c"] = pd.to_numeric(df["c"], errors="coerce")
        df = df.dropna(subset=["c"])

        close = df.get("c")
        if close is None or close.empty:
            logger.warning("trend_close_missing", symbol=symbol)
            return 0.0, "Close series missing"

        recent_closes = close.tail(10).round(4).tolist()
        close_last = float(close.iloc[-1])
        close_20d_ago = float(close.iloc[-21]) if len(close) >= 21 else None
        pct_20d = ((close_last / close_20d_ago) - 1.0) * 100 if close_20d_ago else None
        logger.info(
            "trend_price_reconcile",
            symbol=symbol,
            close_last=close_last,
            close_20d_ago=close_20d_ago,
            pct_20d=pct_20d,
            recent_closes=recent_closes,
        )

        df["ema_5"] = ta.ema(close, length=5)
        df["ema_20"] = ta.ema(close, length=20)
        df["sma_200"] = ta.sma(close, length=200)
        df["mom_20"] = ta.mom(close, length=20)

        logger.info(
            "trend_indicator_availability",
            symbol=symbol,
            bars_count=len(df),
            ema_5_non_null=int(df["ema_5"].notna().sum()),
            ema_20_non_null=int(df["ema_20"].notna().sum()),
            sma_200_non_null=int(df["sma_200"].notna().sum()),
            mom_20_non_null=int(df["mom_20"].notna().sum()),
        )

        valid = df.dropna(subset=["c", "ema_5", "ema_20", "sma_200", "mom_20"])
        if valid.empty:
            logger.warning("trend_indicators_unavailable", symbol=symbol, bars_count=len(df))
            return 0.0, "Indicators unavailable"
        last = valid.iloc[-1]

        score = 50.0
        ema_component = 15 if last["ema_5"] > last["ema_20"] else -15
        ma200_component = 15 if last["c"] > last["sma_200"] else -15
        mom_component = max(min(float(last["mom_20"] or 0) / 2, 20), -20)
        score += ema_component
        score += ma200_component
        score += mom_component
        score = max(0.0, min(100.0, score))

        summary = (
            f"1W EMA5/EMA20={last['ema_5']:.2f}/{last['ema_20']:.2f}; "
            f"1Y MA200={last['sma_200']:.2f}; momentum20={last['mom_20']:.2f}."
        )
        logger.info(
            "trend_score_components",
            symbol=symbol,
            ema_component=ema_component,
            ma200_component=ma200_component,
            mom_component=mom_component,
            close=float(last["c"]),
            ema_5=float(last["ema_5"]),
            ema_20=float(last["ema_20"]),
            sma_200=float(last["sma_200"]),
            mom_20=float(last["mom_20"]),
        )
        logger.info(
            "trend_analyzed",
            symbol=symbol,
            trend_score=float(round(score, 2)),
            ema_5=float(last["ema_5"]),
            ema_20=float(last["ema_20"]),
            sma_200=float(last["sma_200"]),
            mom_20=float(last["mom_20"]),
        )
        return float(round(score, 2)), summary

