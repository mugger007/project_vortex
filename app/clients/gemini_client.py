"""Gemini API client for JSON synthesis responses."""

from __future__ import annotations

import json
import time
from collections import deque
from typing import Any

from google import genai

from app.config import get_settings


class GeminiClient:
    """Client for Gemini JSON synthesis with model fallback and throttling."""

    DEFAULT_MODEL = "gemini-2.5-flash"
    BACKUP_MODELS = ["gemini-3.1-flash-lite-preview", "gemini-2.5-flash-lite"]
    MODEL_RPM = {
        "gemini-3.1-flash-lite-preview": 15,
        "gemini-2.5-flash-lite": 10,
        "gemini-2.5-flash": 5,
    }

    def __init__(self) -> None:
        """Initialize the Gemini SDK client and per-model rate tracking."""
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self._call_timestamps: dict[str, deque[float]] = {
            model: deque() for model in self.MODEL_RPM
        }

    def _models_in_order(self) -> list[str]:
        """Return the configured Gemini models in preferred fallback order."""
        ordered = [self.DEFAULT_MODEL, *self.BACKUP_MODELS]
        seen: set[str] = set()
        unique: list[str] = []
        for model in ordered:
            if model in seen:
                continue
            seen.add(model)
            unique.append(model)
        return unique

    def _throttle(self, model: str) -> None:
        """Sleep until the per-model RPM window allows another request."""
        rpm = self.MODEL_RPM.get(model, 1)
        timestamps = self._call_timestamps.setdefault(model, deque())
        now = time.time()
        while timestamps and now - timestamps[0] > 60:
            timestamps.popleft()
        if len(timestamps) >= rpm:
            sleep_for = 60 - (now - timestamps[0]) + 0.1
            if sleep_for > 0:
                time.sleep(sleep_for)
        timestamps.append(time.time())

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Strip code fences and parse a strict JSON response body."""
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        return json.loads(cleaned)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        """Generate JSON by trying the primary model and then configured backups."""
        last_error: Exception | None = None

        for model in self._models_in_order():
            try:
                self._throttle(model)
                response = self.client.models.generate_content(model=model, contents=prompt)
                return self._parse_json_response(response.text or "")
            except Exception as exc:
                last_error = exc
                continue

        raise RuntimeError("All Gemini models failed to return a valid JSON response") from last_error

