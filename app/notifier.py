from __future__ import annotations

import html
import logging
from typing import Protocol

import httpx

from .classifier import ClassifiedLead
from .config import get_settings
from .normalizer import NormalizedLead

log = logging.getLogger(__name__)


def render_message(lead_id: str, n: NormalizedLead, c: ClassifiedLead) -> str:
    """HTML-formatted Telegram message. Every dynamic field is html.escape()'d."""
    e = html.escape

    label = "⚠️ JUNK" if c.lead_class == "junk" else c.lead_class.upper()

    lines = [
        f"<b>{e(label)}</b>",
        f"Score: {c.score}",
        "",
        f"Name: {e(n.name)}",
        f"Phone: <code>{e(n.phone_e164 or n.phone_raw or '-')}</code>",
        f"Email: {e(n.email_normalized or n.email_raw or '-')}",
    ]
    if n.source:
        lines.append(f"Source: {e(n.source)}")
    if n.message:
        lines.append("")
        lines.append("Message:")
        lines.append(e(n.message))
    if n.issues:
        lines.append("")
        lines.append(f"Issues: {e('; '.join(n.issues))}")
    if n.is_duplicate:
        lines.append("Duplicate: yes")
    lines.extend([
        "",
        f"Summary: {e(c.summary)}",
        f"Reason: {e(c.reason)}",
        "",
        f"ID: <code>{e(lead_id)}</code>",
    ])
    return "\n".join(lines)


class Notifier(Protocol):
    def notify(self, message: str) -> None: ...


class ConsoleNotifier:
    """DRY_RUN backend — logs the rendered message instead of sending."""

    def notify(self, message: str) -> None:
        log.info("notifier.notify(dry_run)\n%s", message)


class TelegramNotifier:
    """Real Telegram bot API via httpx."""

    def __init__(self) -> None:
        s = get_settings()
        self.token = s.telegram_bot_token
        self.chat_id = s.telegram_chat_id

    def notify(self, message: str) -> None:
        if not self.token or not self.chat_id:
            log.warning("notifier.skip missing token or chat_id")
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.post(url, json=payload)
                r.raise_for_status()
            log.info("notifier.sent chat_id=%s", self.chat_id)
        except httpx.HTTPError as e:
            log.warning("notifier.http_error %s: %s", type(e).__name__, e)


def get_notifier() -> Notifier:
    s = get_settings()
    return ConsoleNotifier() if s.dry_run else TelegramNotifier()
