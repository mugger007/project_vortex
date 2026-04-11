from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.analysis.overreaction import OverreactionAnalyzer
from app.clients.finnhub_client import FinnhubClient
from app.clients.gemini_client import GeminiClient
from app.clients.yfinance_client import YFinanceClient
from app.config import get_settings


OUTPUT_FILE = Path("artifacts/test-output/test_overreaction_live_outputs.json")


def _save_output(test_name: str, payload: dict) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists():
        try:
            existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    existing[test_name] = {
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "payload": payload,
    }
    OUTPUT_FILE.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")


def _summarize_news_items(news: list[dict]) -> list[dict]:
    summarized: list[dict] = []
    for item in news:
        source = item.get("_source", "unknown")
        summarized.append(
            {
                "source": f"yfinance (Yahoo RSS)" if source == "yfinance_rss" else f"finnhub (API)" if source == "finnhub_api" else source,
                "title": item.get("title", ""),
                "article_url": item.get("article_url") or item.get("url") or item.get("amp_url"),
                "published_utc": item.get("published_utc") or item.get("publish_date") or item.get("datetime"),
                "publisher": (item.get("publisher") or {}).get("name")
                if isinstance(item.get("publisher"), dict)
                else item.get("publisher"),
            }
        )
    return summarized


@pytest.mark.live
class TestOverreactionLive:
    @pytest.fixture(scope="class", autouse=True)
    def _reset_output_file(self) -> None:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("{}", encoding="utf-8")

    def test_analyze_live(self, require_gemini, live_symbols) -> None:
        settings = get_settings()
        yfinance = YFinanceClient()
        try:
            finnhub = FinnhubClient() if settings.finnhub_api_key else None
        except ImportError:
            finnhub = None
        gemini = GeminiClient()
        analyzer = OverreactionAnalyzer(yfinance=yfinance, finnhub=finnhub, gemini=gemini)

        symbol = live_symbols["massive_symbol"]
        # Use the analyzer's merge method to get tagged news with sources
        news_json = analyzer._merge_news_sources(symbol=symbol, limit=15)
        news = json.loads(news_json) if news_json != "[]" else []
        likelihood, explanation = analyzer.analyze(symbol, option_type="C")
        news_articles = _summarize_news_items(news)

        _save_output(
            "test_analyze_live",
            {
                "symbol": symbol,
                "overreaction_likelihood": likelihood,
                "explanation": explanation,
                "news_count": len(news),
                "news_articles": news_articles,
            },
        )

        assert isinstance(likelihood, float)
        assert 0.0 <= likelihood <= 1.0
        assert isinstance(explanation, str)
        assert isinstance(news, list)