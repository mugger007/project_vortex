import json
from typing import Any

from redis import Redis

from app.config import get_settings


class RedisCache:
    def __init__(self) -> None:
        self.client = Redis.from_url(get_settings().redis_url, decode_responses=True)

    def get_json(self, key: str) -> dict[str, Any] | None:
        raw = self.client.get(key)
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int = 3600) -> None:
        self.client.set(key, json.dumps(value), ex=ttl_seconds)

    def get_float(self, key: str) -> float | None:
        raw = self.client.get(key)
        return float(raw) if raw is not None else None

    def set_float(self, key: str, value: float, ttl_seconds: int = 3600) -> None:
        self.client.set(key, str(value), ex=ttl_seconds)
