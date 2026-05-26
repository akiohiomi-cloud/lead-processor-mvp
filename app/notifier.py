from __future__ import annotations

import logging
from typing import Protocol

from .config import get_settings

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def notify(self, message: str) -> None: ...


class ConsoleNotifier:
    """DRY_RUN backend — logs the rendered message instead of sending."""

    def notify(self, message: str) -> None:
        log.info("notifier.notify(dry_run)\n%s", message)


class TelegramNotifier:
    def notify(self, message: str) -> None:
        raise NotImplementedError("Stage 5 — httpx POST sendMessage + HTML escape")


def get_notifier() -> Notifier:
    s = get_settings()
    return ConsoleNotifier() if s.dry_run else TelegramNotifier()
