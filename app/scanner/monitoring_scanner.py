from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from structlog import get_logger

from app.cache.redis_client import RedisCache
from app.clients.massive_client import MassiveClient
from app.clients.moomoo_client import MoomooClient
from app.db.repositories import ScanRepository
from app.models.schemas import FilteredCandidate, OptionSnapshot
from app.scanner.filters import _is_expiry_in_current_week, liquidity_filter

logger = get_logger(__name__)


@dataclass
class ScannerResult:
    scanned: int
    spike_candidates: int
    filtered_candidates: list[FilteredCandidate]


class MonitoringScanner:
    def __init__(
        self,
        moomoo_client: MoomooClient,
        massive_client: MassiveClient,
        cache: RedisCache,
        repo: ScanRepository,
    ) -> None:
        self.moomoo_client = moomoo_client
        self.massive_client = massive_client
        self.cache = cache
        self.repo = repo

    def _to_datetime(self, value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return datetime.now(UTC)
        return datetime.now(UTC)

    def scan_symbol(self, symbol: str) -> list[FilteredCandidate]:
        """Scan for weekly options premium spikes on a given underlying symbol.
        
        Flow:
        1. Get expiration dates for the symbol via OpenD
        2. Query option chain for all available strikes
        3. Filter for weekly Friday expiries
        4. Detect premium spikes (>500% jump from cached value)
        5. Apply liquidity filters (OI, volume, bid-ask spread)
        6. Return candidates for downstream analysis
        """
        expiry_dates = self.moomoo_client.get_option_expiration_date(symbol)
        candidates: list[FilteredCandidate] = []
        
        for expiry in expiry_dates:
            if not _is_expiry_in_current_week(expiry):
                continue

            chain = self.moomoo_client.get_option_chain(symbol, start=expiry, end=expiry)
            logger.info(
                "option_chain_loaded",
                symbol=symbol,
                expiry=expiry,
                chain_count=len(chain),
            )

            for row in chain:
                option_symbol = str(row.get("code", "") or "")
                if not option_symbol:
                    continue

                try:
                    snapshot = self.moomoo_client.get_snapshot(option_symbol)
                except ValueError:
                    logger.warning("invalid_option_symbol_skipped", symbol=symbol, option_symbol=option_symbol)
                    continue

                if not snapshot:
                    logger.warning("option_snapshot_missing", symbol=symbol, option_symbol=option_symbol)
                    continue

                bid = float(snapshot.get("bid", 0.0) or row.get("bid", 0.0) or 0.0)
                ask = float(snapshot.get("ask", 0.0) or row.get("ask", 0.0) or 0.0)
                last_price = float(snapshot.get("last_price", 0.0) or row.get("last_price", 0.0) or 0.0)
                prev_close_price = float(
                    snapshot.get("prev_close_price", 0.0) or row.get("prev_close_price", 0.0) or 0.0
                )

                if bid > 0 and ask > 0:
                    premium = (bid + ask) / 2
                else:
                    premium = last_price

                oi = int(snapshot.get("option_open_interest", 0) or 0)
                volume = int(snapshot.get("volume", 0) or row.get("volume", 0) or 0)

                jump_pct = ((premium - prev_close_price) / prev_close_price) * 100 if prev_close_price > 0 else 0.0
                spread = max(ask - bid, 0.0)
                spread_ratio = (spread / premium) if premium > 0 else 0.0

                logger.info(
                    "option_filter_metrics",
                    symbol=symbol,
                    expiry=expiry,
                    option_symbol=option_symbol,
                    premium=premium,
                    prev_close_price=prev_close_price,
                    jump_pct=jump_pct,
                    oi=oi,
                    volume=volume,
                    bid=bid,
                    ask=ask,
                    spread=spread,
                    spread_ratio=spread_ratio,
                )

                self.repo.save_snapshot(
                    {
                        "symbol": symbol,
                        "option_symbol": option_symbol,
                        "expiry": expiry,
                        "snapshot_ts": self._to_datetime(snapshot.get("update_time", row.get("last_updated"))),
                        "premium": premium,
                        "oi": oi,
                        "volume": volume,
                        "bid": bid,
                        "ask": ask,
                        "raw_json": {"chain": row, "snapshot": snapshot},
                    }
                )

                if jump_pct <= 100:
                    logger.info(
                        "option_rejected_jump_threshold",
                        symbol=symbol,
                        expiry=expiry,
                        option_symbol=option_symbol,
                        jump_pct=jump_pct,
                        threshold=100,
                    )
                    continue

                passed, reason = liquidity_filter(oi=oi, volume=volume, bid=bid, ask=ask, premium=premium)
                self.repo.add_audit_log(
                    stage="liquidity_filter",
                    message=reason,
                    payload_json={"symbol": symbol, "option_symbol": option_symbol, "jump_pct": jump_pct},
                )
                if not passed:
                    logger.info(
                        "option_rejected_liquidity",
                        symbol=symbol,
                        expiry=expiry,
                        option_symbol=option_symbol,
                        reason=reason,
                        jump_pct=jump_pct,
                        oi=oi,
                        volume=volume,
                        bid=bid,
                        ask=ask,
                        premium=premium,
                        spread_ratio=spread_ratio,
                    )
                    continue

                candidates.append(
                    FilteredCandidate(
                        symbol=symbol,
                        option_symbol=option_symbol,
                        expiry=expiry,
                        premium_jump_pct=jump_pct,
                        snapshot=OptionSnapshot(
                            symbol=symbol,
                            option_symbol=option_symbol,
                            expiry=expiry,
                            premium=premium,
                            oi=oi,
                            volume=volume,
                            bid=bid,
                            ask=ask,
                            ts=self._to_datetime(snapshot.get("update_time", row.get("last_updated"))),
                            extra={"chain": row, "snapshot": snapshot},
                        ),
                    )
                )
        return candidates
