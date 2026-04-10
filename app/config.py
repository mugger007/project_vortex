"""Application settings and environment configuration models."""

import logging
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    streamlit_port: int = Field(default=8501, alias="STREAMLIT_PORT")

    scan_interval_minutes: int = Field(default=10, alias="SCAN_INTERVAL_MINUTES")
    watchlist: list[str] = Field(default_factory=lambda: ["SNOW"], alias="WATCHLIST")

    postgres_dsn: str = Field(alias="POSTGRES_DSN")

    massive_api_key: str = Field(alias="MASSIVE_API_KEY")
    massive_base_url: str = Field(alias="MASSIVE_BASE_URL")
    alpha_vantage_api_key: str | None = Field(default=None, alias="ALPHA_VANTAGE_API_KEY")

    moomoo_opend_host: str = Field(default="127.0.0.1", alias="MOOMOO_OPEND_HOST")
    moomoo_opend_port: int = Field(default=11111, alias="MOOMOO_OPEND_PORT")

    gemini_api_key: str = Field(alias="GEMINI_API_KEY")

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")
    alert_email_to: str | None = Field(default=None, alias="ALERT_EMAIL_TO")
    alert_email_from: str | None = Field(default=None, alias="ALERT_EMAIL_FROM")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")

    backtest_mode: bool = Field(default=False, alias="BACKTEST_MODE")

    @field_validator("watchlist", mode="before")
    @classmethod
    def _parse_watchlist(cls, value: object) -> object:
        if isinstance(value, str):
            parsed = [item.strip().upper() for item in value.split(",") if item.strip()]
            if not parsed:
                logger.warning("WATCHLIST is set but contains no valid tickers")
            return parsed
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

