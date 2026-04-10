"""News-driven overreaction likelihood analysis."""

from __future__ import annotations

from app.clients.gemini_client import GeminiClient
from app.clients.massive_client import MassiveClient


class OverreactionAnalyzer:
    def __init__(self, massive: MassiveClient, gemini: GeminiClient) -> None:
        self.massive = massive
        self.gemini = gemini

    def analyze(self, symbol: str, option_type: str = "C") -> tuple[float, str]:
        news = self.massive.get_news(symbol=symbol, limit=15)
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
            f"Symbol: {symbol}\n"
            f"Option Type Context: {option_context}\n"
            f"News JSON: {news}"
        )
        result = self.gemini.generate_json(prompt)
        return float(result.get("overreaction_likelihood", 0.0)), str(result.get("explanation", ""))

