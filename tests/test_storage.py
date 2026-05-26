from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.classifier import ClassifiedLead
from app.config import get_settings
from app.normalizer import NormalizedLead
from app.storage import (
    COLUMNS,
    ConsoleStorage,
    SheetsStorage,
    _row_to_values,
    build_row,
    get_storage,
)


def _valid_lead() -> tuple[NormalizedLead, ClassifiedLead]:
    n = NormalizedLead(
        name="Іван",
        phone_raw="+380671234567",
        phone_e164="+380671234567",
        email_raw="i@x.co",
        email_normalized="i@x.co",
        message="hi",
        source="landing",
        is_valid=True,
        issues=[],
        dedup_key="abc",
        is_duplicate=False,
    )
    c = ClassifiedLead(summary="auto", score=75, reason="r", lead_class="hot")
    return n, c


def _invalid_lead() -> tuple[NormalizedLead, ClassifiedLead]:
    n = NormalizedLead(
        name="X",
        phone_raw="garbage",
        phone_e164=None,
        email_raw="bad",
        email_normalized=None,
        message=None,
        source=None,
        is_valid=False,
        issues=["phone: bad", "email: bad"],
    )
    c = ClassifiedLead(summary="s", score=0, reason="invalid", lead_class="junk")
    return n, c


def test_columns_contains_expected_keys():
    expected = {
        "received_at", "lead_id", "name", "phone", "email", "source", "message",
        "is_valid", "is_duplicate", "issues", "lead_class", "score", "summary", "reason",
    }
    assert set(COLUMNS) == expected


def test_build_row_has_all_columns():
    n, c = _valid_lead()
    row = build_row("LID", n, c)
    for col in COLUMNS:
        assert col in row, f"missing column {col}"


def test_build_row_uses_normalized_fields():
    n, c = _valid_lead()
    row = build_row("LID", n, c)
    assert row["phone"] == "+380671234567"
    assert row["email"] == "i@x.co"
    assert row["lead_id"] == "LID"
    assert row["score"] == 75
    assert row["lead_class"] == "hot"


def test_build_row_falls_back_to_raw_for_invalid():
    n, c = _invalid_lead()
    row = build_row("LID", n, c)
    assert row["phone"] == "garbage"
    assert row["email"] == "bad"
    assert row["issues"] == "phone: bad; email: bad"
    assert row["message"] == ""
    assert row["source"] == ""
    assert row["lead_class"] == "junk"


def test_build_row_received_at_passthrough():
    n, c = _valid_lead()
    row = build_row("LID", n, c, received_at="2026-01-01T00:00:00+00:00")
    assert row["received_at"] == "2026-01-01T00:00:00+00:00"


def test_row_to_values_order_matches_columns():
    n, c = _valid_lead()
    row = build_row("LID", n, c)
    values = _row_to_values(row)
    assert len(values) == len(COLUMNS)
    for i, col in enumerate(COLUMNS):
        assert values[i] == row[col]


def test_console_storage_writes_jsonl(tmp_path):
    path = tmp_path / "leads.jsonl"
    s = ConsoleStorage(path=path)
    s.append({"lead_id": "1", "name": "A"})
    s.append({"lead_id": "2", "name": "Б"})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["lead_id"] == "1"
    assert json.loads(lines[1])["name"] == "Б"


def test_factory_dry_run(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    get_settings.cache_clear()
    assert isinstance(get_storage(), ConsoleStorage)


def test_factory_real(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    get_settings.cache_clear()
    assert isinstance(get_storage(), SheetsStorage)


def test_sheets_storage_calls_append_row_raw(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "test-id")
    get_settings.cache_clear()

    fake_ws = MagicMock()
    fake_sh = MagicMock(sheet1=fake_ws)
    fake_client = MagicMock()
    fake_client.open_by_key.return_value = fake_sh

    with patch("gspread.service_account", return_value=fake_client) as m:
        s = SheetsStorage()
        n, c = _valid_lead()
        row = build_row("LID-1", n, c)
        s.append(row)

    m.assert_called_once()
    fake_client.open_by_key.assert_called_once_with("test-id")
    fake_ws.append_row.assert_called_once()
    call_args = fake_ws.append_row.call_args
    values = call_args.args[0]
    assert len(values) == len(COLUMNS)
    assert call_args.kwargs["value_input_option"] == "RAW"


def test_sheets_storage_caches_worksheet(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "test-id")
    get_settings.cache_clear()

    fake_ws = MagicMock()
    fake_sh = MagicMock(sheet1=fake_ws)
    fake_client = MagicMock()
    fake_client.open_by_key.return_value = fake_sh

    with patch("gspread.service_account", return_value=fake_client) as m:
        s = SheetsStorage()
        n, c = _valid_lead()
        row = build_row("LID-1", n, c)
        s.append(row)
        s.append(row)

    assert m.call_count == 1
    assert fake_client.open_by_key.call_count == 1
    assert fake_ws.append_row.call_count == 2


def test_pipeline_swallows_storage_error(monkeypatch):
    """Storage error must not crash the background task."""
    from app import api

    monkeypatch.setenv("DRY_RUN", "true")
    get_settings.cache_clear()

    failing = MagicMock()
    failing.append.side_effect = RuntimeError("sheets down")

    with patch("app.api.get_storage", return_value=failing):
        api._process_lead("LID", {
            "name": "X",
            "phone": "+380671234567",
            "email": "a@b.co",
            "message": None,
            "source": None,
        })

    failing.append.assert_called_once()
