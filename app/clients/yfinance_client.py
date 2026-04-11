"""YFinance client helpers for quote and historical index/equity data."""

from __future__ import annotations

import html
import json
import re
from email.utils import parsedate_to_datetime
from datetime import UTC, datetime, timezone
from typing import Any

import httpx
import feedparser
import pandas as pd
import yfinance as yf


class YFinanceClient:
    """Thin adapter around yfinance for history, fast-info, spot price, and news access."""

    def get_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        """Return a historical OHLCV DataFrame for the requested symbol and window."""
        return yf.Ticker(symbol).history(period=period, interval=interval)

    def get_fast_info(self, symbol: str) -> dict[str, Any]:
        """Return yfinance fast_info as a plain dictionary."""
        info = yf.Ticker(symbol).fast_info
        # yfinance returns a lazy mapping; normalize to plain dict for callers.
        return dict(info)

    def get_last_price(self, symbol: str) -> float:
        """Return the latest spot price from yfinance fast_info or raise on missing data."""
        fast_info = self.get_fast_info(symbol)
        last_price = float(fast_info.get("lastPrice") or 0.0)
        if last_price <= 0:
            raise ValueError(f"yfinance fast_info.lastPrice unavailable for {symbol}")
        return last_price

    def get_news(self, symbol: str, limit: int = 15) -> str:
        """Fetch recent news for the symbol via Yahoo Finance RSS and return as JSON string.
        Only includes articles published within the last 24 hours.
        """
        try:
            feed_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&lang=en-US"
            feed = feedparser.parse(feed_url)
            raw_news = feed.entries or []
            publisher = getattr(feed.feed, "title", None) or "Yahoo Finance RSS"
            enriched_news = sorted(
                (
                    {
                        "title": item.get("title", ""),
                        "publisher": publisher,
                        "link": item.get("link", ""),
                        "published_utc": self._extract_published_utc(item),
                        "content": self._get_article_text(str(item.get("link", ""))),
                    }
                    for item in raw_news[:limit]
                    if self._is_within_24_hours(item)
                ),
                key=self._news_sort_key,
                reverse=True,
            )
            return json.dumps(enriched_news, indent=2)
        except Exception:
            return "[]"

    def _extract_published_utc(self, item: dict[str, Any]) -> str:
        """Normalize the publish timestamp from a Yahoo RSS item to UTC ISO 8601."""
        raw_candidates = (
            item.get("published_parsed"),
            item.get("updated_parsed"),
            item.get("providerPublishTime"),
            item.get("published_utc"),
            item.get("publish_date"),
            item.get("pubDate"),
            item.get("published"),
            item.get("updated"),
            item.get("datetime"),
        )

        for raw_value in raw_candidates:
            if raw_value in (None, ""):
                continue

            if hasattr(raw_value, "tm_year"):
                try:
                    return datetime(*raw_value[:6], tzinfo=UTC).isoformat()
                except (TypeError, ValueError):
                    continue

            if isinstance(raw_value, (int, float)):
                seconds = float(raw_value)
                if seconds > 1_000_000_000_000:
                    seconds /= 1000.0
                return datetime.fromtimestamp(seconds, tz=UTC).isoformat()

            text_value = str(raw_value).strip()
            if not text_value:
                continue

            if text_value.isdigit():
                seconds = float(text_value)
                if seconds > 1_000_000_000_000:
                    seconds /= 1000.0
                return datetime.fromtimestamp(seconds, tz=UTC).isoformat()

            try:
                parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC).isoformat()
            except ValueError:
                try:
                    parsed = parsedate_to_datetime(text_value)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=UTC)
                    return parsed.astimezone(UTC).isoformat()
                except (TypeError, ValueError):
                    continue

        return ""

    def _is_within_24_hours(self, item: dict[str, Any]) -> bool:
        """Check if an article was published within the last 24 hours."""
        published = str(item.get("published_utc") or self._extract_published_utc(item)).strip()
        if not published:
            return False

        try:
            parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            parsed_utc = parsed.astimezone(UTC)
            now_utc = datetime.now(UTC)
            age_seconds = (now_utc - parsed_utc).total_seconds()
            return age_seconds <= 86400  # 24 hours in seconds
        except ValueError:
            return False

    def _news_sort_key(self, item: dict[str, Any]) -> datetime:
        """Sort news items by recency, falling back to the oldest possible timestamp."""
        published = str(item.get("published_utc", "")).strip()
        if not published:
            return datetime.min.replace(tzinfo=timezone.utc)

        try:
            parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)

    def _get_article_text(self, url: str, max_chars: int = 3000) -> str:
        """Fetch a linked article and extract a plain-text excerpt."""
        if not url:
            return ""

        try:
            response = httpx.get(
                url,
                follow_redirects=True,
                timeout=10.0,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            html_text = response.text
        except Exception:
            return ""

        snippets: list[str] = []
        for match in re.findall(r"<meta[^>]+(?:name|property)=[\"'](?:description|og:description)[\"'][^>]+content=[\"']([^\"']+)[\"']", html_text, flags=re.IGNORECASE):
            cleaned = html.unescape(re.sub(r"\s+", " ", match)).strip()
            if self._is_meaningful_snippet(cleaned):
                snippets.append(cleaned)

        for paragraph in re.findall(r"<p[^>]*>(.*?)</p>", html_text, flags=re.IGNORECASE | re.DOTALL):
            cleaned = re.sub(r"<[^>]+>", " ", paragraph)
            cleaned = html.unescape(re.sub(r"\s+", " ", cleaned)).strip()
            if self._is_meaningful_snippet(cleaned):
                snippets.append(cleaned)

        deduped = list(dict.fromkeys(snippets))
        return "\n".join(deduped[:5])[:max_chars]

    def _is_meaningful_snippet(self, text: str) -> bool:
        """Reject page chrome, CSS, and other non-article noise."""
        if not text or len(text) < 40:
            return False

        lowered = text.lower()
        noise_markers = (
            "oops, something went wrong",
            "skip to navigation",
            "skip to main content",
            "skip to right column",
            "--yb-",
            "css",
        )
        if any(marker in lowered for marker in noise_markers):
            return False
        if lowered.startswith(":root,html") or lowered.startswith("body {"):
            return False
        return True