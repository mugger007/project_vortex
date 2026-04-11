"""News-driven overreaction likelihood analysis."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timezone
from typing import Any

from app.clients.finnhub_client import FinnhubClient
from app.clients.gemini_client import GeminiClient
from app.clients.yfinance_client import YFinanceClient

logger = logging.getLogger(__name__)


class OverreactionAnalyzer:
    def __init__(self, yfinance: YFinanceClient, finnhub: FinnhubClient | None, gemini: GeminiClient) -> None:
        self.yfinance = yfinance
        self.finnhub = finnhub
        self.gemini = gemini

    def _merge_news_sources(self, symbol: str, limit: int = 15) -> str:
        """Fetch and merge news from both yfinance and finnhub (if available)."""
        combined_articles = []

        # Fetch from yfinance (Yahoo Finance RSS feed)
        try:
            logger.info(f"Fetching news for {symbol} from yfinance (Yahoo RSS feed)")
            yfinance_json = self.yfinance.get_news(symbol=symbol, limit=limit)
            yfinance_news = json.loads(yfinance_json) if yfinance_json != "[]" else []
            # Tag articles with source
            for article in yfinance_news:
                article["_source"] = "yfinance_rss"
            logger.info(f"Fetched {len(yfinance_news)} articles from yfinance")
            combined_articles.extend(yfinance_news)
        except Exception as e:
            logger.warning(f"Failed to fetch news from yfinance: {e}")

        # Fetch from finnhub if available (Finnhub API)
        if self.finnhub:
            try:
                logger.info(f"Fetching news for {symbol} from finnhub API")
                finnhub_json = self.finnhub.get_news(symbol=symbol, limit=limit)
                finnhub_news = json.loads(finnhub_json) if finnhub_json != "[]" else []
                # Tag articles with source
                for article in finnhub_news:
                    article["_source"] = "finnhub_api"
                logger.info(f"Fetched {len(finnhub_news)} articles from finnhub")
                combined_articles.extend(finnhub_news)
            except Exception as e:
                logger.warning(f"Failed to fetch news from finnhub: {e}")
        else:
            logger.debug("Finnhub client not available, skipping Finnhub source")

        # Sort by recency (most recent first) and limit to requested count
        def sort_key(item: dict[str, Any]) -> datetime:
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

        sorted_articles = sorted(combined_articles, key=sort_key, reverse=True)[:limit]
        return json.dumps(sorted_articles, indent=2) if sorted_articles else "[]"

    def analyze(self, symbol: str, option_type: str = "C") -> tuple[float, str]:
        news_json = self._merge_news_sources(symbol=symbol, limit=15)
        normalized_option_type = (option_type or "C").strip().upper()
        option_context = (
            "P (put): bearish position that profits if the stock moves down"
            if normalized_option_type == "P"
            else "C (call): bullish position that profits if the stock moves up"
        )
        prompt = (
            "You are a US equity options analyst. Evaluate whether recent news-driven move is "
            "likely an overreaction for short-premium selling. Return strict JSON with keys "
            "overreaction_likelihood (0..1 float), explanation (string <= 120 words).\n"
            "First review the article titles and ignore any items that are not clearly applicable to the company or stock. "
            "Prioritize the most recent relevant articles first and disregard obviously outdated items. "
            "Then use the linked article content excerpts for the relevant items only.\n"
            f"Symbol: {symbol}\n"
            f"Option Type Context: {option_context}\n"
            f"Recent News (titles and linked content from yfinance and finnhub): {news_json}"
        )
        result = self.gemini.generate_json(prompt)
        return float(result.get("overreaction_likelihood", 0.0)), str(result.get("explanation", ""))

