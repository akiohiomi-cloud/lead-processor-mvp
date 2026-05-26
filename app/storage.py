from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

from .config import get_settings

log = logging.getLogger(__name__)


class Storage(Protocol):
    def append(self, row: dict) -> None: ...


class ConsoleStorage:
    """DRY_RUN backend — appends each row as JSONL to logs/leads.jsonl."""

    def __init__(self, path: Path = Path("logs/leads.jsonl")) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, row: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        log.info("storage.append(dry_run) lead_id=%s", row.get("lead_id"))


class SheetsStorage:
    def append(self, row: dict) -> None:
        raise NotImplementedError("Stage 4 — gspread service account + append_row")


def get_storage() -> Storage:
    s = get_settings()
    return ConsoleStorage() if s.dry_run else SheetsStorage()
