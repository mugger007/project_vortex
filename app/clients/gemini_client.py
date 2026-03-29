from __future__ import annotations

import json
from typing import Any

from google import genai

from app.config import get_settings


class GeminiClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.model_name = settings.gemini_model
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        response = self.client.models.generate_content(model=self.model_name, contents=prompt)
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        return json.loads(text)
