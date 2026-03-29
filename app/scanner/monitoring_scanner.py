from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from structlog import get_logger

from app.cache.redis_client import RedisCache
from app.clients.moomoo_client import MoomooClient
from app.db.repositories import ScanRepository
from app.models.schemas import FilteredCandidate, OptionSnapshot
from app.scanner.filters import is_weekly_friday_expiry, liquidity_filter

logger = get_logger(__name__)


@dataclass
class ScannerResult:
    scanned: int
    spike_candidates: int
    filtered_candidates: list[FilteredCandidate]


class MonitoringScanner:
    def __init__(self, moomoo_client: MoomooClient, cache: RedisCache, repo: ScanRepository) -> None:
        self.moomoo_client = moomoo_client
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
            if not is_weekly_friday_expiry(expiry):
                continue
            
            # Get option chain for this expiration
            chain = self.moomoo_client.get_option_chain(symbol, start=expiry, end=expiry)
            
            for row in chain:
                # Extract fields from Moomoo option chain DataFrame (converted to dict)
                option_symbol = row.get("code", "")
                
                if not option_symbol:
                    continue

                # Extract premium (use bid-ask midpoint or last price)
                bid = float(row.get("bid", 0.0) or 0.0)
                ask = float(row.get("ask", 0.0) or 0.0)
                last_price = float(row.get("last_price", 0.0) or 0.0)
                
                if bid > 0 and ask > 0:
                    premium = (bid + ask) / 2
                else:
                    premium = last_price
                
                oi = int(row.get("open_interest", 0) or 0)
                volume = int(row.get("volume", 0) or 0)

                cache_key = f"snapshot:{option_symbol}"
                prev = self.cache.get_float(cache_key)
                jump_pct = ((premium - prev) / prev) * 100 if prev and prev > 0 else 0.0

                self.cache.set_float(cache_key, premium, ttl_seconds=86_400)
                self.repo.save_snapshot(
                    {
                        "symbol": symbol,
                        "option_symbol": option_symbol,
                        "expiry": expiry,
                        "snapshot_ts": self._to_datetime(row.get("last_updated")),
                        "premium": premium,
                        "oi": oi,
                        "volume": volume,
                        "bid": bid,
                        "ask": ask,
                        "raw_json": row,
                    }
                )

                if jump_pct <= 500:
                    continue

                passed, reason = liquidity_filter(oi=oi, volume=volume, bid=bid, ask=ask, premium=premium)
                self.repo.add_audit_log(
                    stage="liquidity_filter",
                    message=reason,
                    payload_json={"symbol": symbol, "option_symbol": option_symbol, "jump_pct": jump_pct},
                )
                if not passed:
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
                            ts=self._to_datetime(row.get("last_updated")),
                            extra=row,
                        ),
                    )
                )
        return candidates
