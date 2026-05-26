from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import app
from app.config import get_settings


def test_health_ok():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "dry_run" in body


def test_storage_factory_dry_run(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    get_settings.cache_clear()
    from app.storage import ConsoleStorage, get_storage

    assert isinstance(get_storage(), ConsoleStorage)


def test_notifier_factory_dry_run(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    get_settings.cache_clear()
    from app.notifier import ConsoleNotifier, get_notifier

    assert isinstance(get_notifier(), ConsoleNotifier)


def test_storage_factory_real_when_dry_run_off(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    get_settings.cache_clear()
    from app.storage import SheetsStorage, get_storage

    assert isinstance(get_storage(), SheetsStorage)
