from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.cache.redis_client import RedisCache
from app.clients.massive_client import MassiveClient
from app.db.repositories import ScanRepository
from app.models.schemas import FilteredCandidate, OptionSnapshot
from app.scanner.filters import is_weekly_friday_expiry, liquidity_filter


@dataclass
class ScannerResult:
    scanned: int
    spike_candidates: int
    filtered_candidates: list[FilteredCandidate]


class MonitoringScanner:
    def __init__(self, massive_client: MassiveClient, cache: RedisCache, repo: ScanRepository) -> None:
        self.massive_client = massive_client
        self.cache = cache
        self.repo = repo

    def _extract_premium(self, snapshot: dict) -> float:
        last = snapshot.get("last_quote", {})
        bid = float(last.get("bid", 0.0) or 0.0)
        ask = float(last.get("ask", 0.0) or 0.0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2
        return float(snapshot.get("day", {}).get("close", 0.0) or 0.0)

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
        chain = self.massive_client.get_options_chain_snapshot(symbol)
        candidates: list[FilteredCandidate] = []
        for row in chain:
            details = row.get("details", {})
            expiry = details.get("expiration_date", "")
            option_symbol = row.get("ticker", "")
            if not option_symbol or not is_weekly_friday_expiry(expiry):
                continue

            premium = self._extract_premium(row)
            day = row.get("day", {})
            oi = int(row.get("open_interest", 0) or 0)
            volume = int(day.get("volume", 0) or 0)
            bid = float(row.get("last_quote", {}).get("bid", 0.0) or 0.0)
            ask = float(row.get("last_quote", {}).get("ask", 0.0) or 0.0)

            cache_key = f"snapshot:{option_symbol}"
            prev = self.cache.get_float(cache_key)
            jump_pct = ((premium - prev) / prev) * 100 if prev and prev > 0 else 0.0

            self.cache.set_float(cache_key, premium, ttl_seconds=86_400)
            self.repo.save_snapshot(
                {
                    "symbol": symbol,
                    "option_symbol": option_symbol,
                    "expiry": expiry,
                    "snapshot_ts": self._to_datetime(row.get("fmv_last_updated") or row.get("last_updated")),
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
