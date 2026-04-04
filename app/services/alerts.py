"""Alert delivery service for high-confidence recommendations."""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

import httpx

from app.config import get_settings
from app.models.schemas import RecommendationCard


class AlertService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _send_telegram(self, message: str) -> None:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        httpx.post(url, json={"chat_id": self.settings.telegram_chat_id, "text": message}, timeout=10.0)

    def _send_email(self, subject: str, message: str) -> None:
        if not all(
            [
                self.settings.alert_email_from,
                self.settings.alert_email_to,
                self.settings.smtp_host,
                self.settings.smtp_user,
                self.settings.smtp_password,
            ]
        ):
            return

        mime = MIMEText(message)
        mime["Subject"] = subject
        mime["From"] = self.settings.alert_email_from
        mime["To"] = self.settings.alert_email_to

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
            server.starttls()
            server.login(self.settings.smtp_user, self.settings.smtp_password)
            server.send_message(mime)

    def notify_high_confidence(self, card: RecommendationCard) -> None:
        if card.data.confidence < 80 or card.rejected:
            return
        message = (
            f"{card.symbol} {card.option_symbol}: {card.data.recommendation} "
            f"({card.data.confidence}) - {card.data.explanation}"
        )
        self._send_telegram(message)
        self._send_email(subject=f"Weekly Option Setup: {card.symbol}", message=message)

