from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api import app
from app.config import get_settings
from app.normalizer import _reset_dedup_for_tests


def _setup(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    get_settings.cache_clear()
    _reset_dedup_for_tests()


class _Capture:
    def __init__(self):
        self.rows: list[dict] = []
        self.messages: list[str] = []

    def storage(self):
        outer = self

        class S:
            def append(self, row):
                outer.rows.append(row)

        return S()

    def notifier(self):
        outer = self

        class N:
            def notify(self, msg):
                outer.messages.append(msg)

        return N()


def test_e2e_valid_lead_flows_through_full_pipeline(monkeypatch):
    _setup(monkeypatch)
    cap = _Capture()
    with (
        patch("app.api.get_storage", return_value=cap.storage()),
        patch("app.api.get_notifier", return_value=cap.notifier()),
    ):
        client = TestClient(app)
        r = client.post(
            "/lead",
            json={
                "name": "Test Lead",
                "phone": "+380 67 123 45 67",
                "email": "test@example.com",
                "message": "Want CRM for 15 users, budget 5k/mo",
                "source": "landing/hero",
            },
        )
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "accepted"
        assert len(body["lead_id"]) > 0

    assert len(cap.rows) == 1
    row = cap.rows[0]
    assert row["phone"] == "+380671234567"
    assert row["email"] == "test@example.com"
    assert row["is_valid"] is True
    assert row["is_duplicate"] is False
    assert row["lead_class"] == "warm"
    assert row["score"] == 50
    assert "[DRY_RUN]" in row["summary"]

    assert len(cap.messages) == 1
    msg = cap.messages[0]
    assert "WARM" in msg
    assert "Test Lead" in msg
    assert "+380671234567" in msg
    assert row["lead_id"] in msg


def test_e2e_junk_lead_marked_in_notification(monkeypatch):
    _setup(monkeypatch)
    cap = _Capture()
    with (
        patch("app.api.get_storage", return_value=cap.storage()),
        patch("app.api.get_notifier", return_value=cap.notifier()),
    ):
        client = TestClient(app)
        r = client.post(
            "/lead",
            json={"name": "Junk", "phone": "+999", "email": "bad"},
        )
        assert r.status_code == 202

    assert cap.rows[0]["lead_class"] == "junk"
    assert cap.rows[0]["is_valid"] is False
    assert "⚠️" in cap.messages[0]
    assert "JUNK" in cap.messages[0]


def test_e2e_duplicate_lead_flagged_on_second_submission(monkeypatch):
    _setup(monkeypatch)
    cap = _Capture()
    payload = {
        "name": "Twice",
        "phone": "+380671234567",
        "email": "twice@example.com",
    }
    with (
        patch("app.api.get_storage", return_value=cap.storage()),
        patch("app.api.get_notifier", return_value=cap.notifier()),
    ):
        client = TestClient(app)
        client.post("/lead", json=payload)
        client.post("/lead", json=payload)

    assert len(cap.rows) == 2
    assert cap.rows[0]["is_duplicate"] is False
    assert cap.rows[1]["is_duplicate"] is True
    assert "Duplicate: yes" in cap.messages[1]


def test_e2e_external_failures_do_not_break_response(monkeypatch):
    _setup(monkeypatch)

    broken_storage = MagicMock()
    broken_storage.append.side_effect = RuntimeError("sheets down")
    broken_notifier = MagicMock()
    broken_notifier.notify.side_effect = RuntimeError("tg down")

    with (
        patch("app.api.get_storage", return_value=broken_storage),
        patch("app.api.get_notifier", return_value=broken_notifier),
    ):
        client = TestClient(app)
        r = client.post(
            "/lead",
            json={
                "name": "X",
                "phone": "+380671234567",
                "email": "a@b.co",
            },
        )
        assert r.status_code == 202

    broken_storage.append.assert_called_once()
    broken_notifier.notify.assert_called_once()


def test_e2e_validation_failure_returns_422_without_background_task(monkeypatch):
    _setup(monkeypatch)
    cap = _Capture()
    with (
        patch("app.api.get_storage", return_value=cap.storage()),
        patch("app.api.get_notifier", return_value=cap.notifier()),
    ):
        client = TestClient(app)
        r = client.post("/lead", json={"name": "x", "phone": "+1"})
        assert r.status_code == 422

    assert cap.rows == []
    assert cap.messages == []
