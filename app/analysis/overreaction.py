"""News-driven overreaction likelihood analysis."""

from __future__ import annotations

from app.clients.gemini_client import GeminiClient
from app.clients.massive_client import MassiveClient


class OverreactionAnalyzer:
    def __init__(self, massive: MassiveClient, gemini: GeminiClient) -> None:
        self.massive = massive
        self.gemini = gemini

    def analyze(self, symbol: str) -> tuple[float, str]:
        news = self.massive.get_news(symbol=symbol, limit=15)
        prompt = (
            "You are a US equity options analyst. Evaluate whether recent news-driven move is "
            "likely an overreaction for short-premium selling. Return strict JSON with keys "
            "overreaction_likelihood (0..1 float), explanation (string <= 120 words).\n"
            f"Symbol: {symbol}\n"
            f"News JSON: {news}"
        )
        result = self.gemini.generate_json(prompt)
        return float(result.get("overreaction_likelihood", 0.0)), str(result.get("explanation", ""))

