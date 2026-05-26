from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .classifier import ClassifiedLead
from .config import get_settings
from .normalizer import NormalizedLead

log = logging.getLogger(__name__)


COLUMNS: tuple[str, ...] = (
    "received_at",
    "lead_id",
    "name",
    "phone",
    "email",
    "source",
    "message",
    "is_valid",
    "is_duplicate",
    "issues",
    "lead_class",
    "score",
    "summary",
    "reason",
)


def build_row(
    lead_id: str,
    normalized: NormalizedLead,
    classified: ClassifiedLead,
    received_at: str | None = None,
) -> dict:
    n, c = normalized, classified
    return {
        "received_at": received_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lead_id": lead_id,
        "name": n.name,
        "phone": n.phone_e164 or n.phone_raw,
        "email": n.email_normalized or n.email_raw,
        "source": n.source or "",
        "message": n.message or "",
        "is_valid": n.is_valid,
        "is_duplicate": n.is_duplicate,
        "issues": "; ".join(n.issues),
        "lead_class": c.lead_class,
        "score": c.score,
        "summary": c.summary,
        "reason": c.reason,
    }


def _row_to_values(row: dict) -> list:
    return [row.get(col, "") for col in COLUMNS]


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
    """Real Google Sheets via gspread service account. Worksheet cached after first append."""

    def __init__(self) -> None:
        self._worksheet = None

    def _get_worksheet(self):
        if self._worksheet is not None:
            return self._worksheet
        import gspread

        s = get_settings()
        client = gspread.service_account(filename=s.google_service_account_path)
        sh = client.open_by_key(s.google_sheets_id)
        self._worksheet = sh.sheet1
        return self._worksheet

    def append(self, row: dict) -> None:
        ws = self._get_worksheet()
        ws.append_row(_row_to_values(row), value_input_option="USER_ENTERED")
        log.info("storage.append(sheets) lead_id=%s", row.get("lead_id"))


def get_storage() -> Storage:
    s = get_settings()
    return ConsoleStorage() if s.dry_run else SheetsStorage()
