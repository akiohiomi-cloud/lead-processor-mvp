from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_cwd(monkeypatch, tmp_path):
    """Run each test from a temp dir.

    ConsoleStorage uses the relative path 'logs/leads.jsonl' — without this
    fixture every test that triggers the background pipeline (via TestClient
    or direct _process_lead call) would leave artefact rows in the project's
    real logs/leads.jsonl. Tests that mock get_storage explicitly aren't
    affected; tests that don't mock end up writing into tmp_path instead.
    """
    monkeypatch.chdir(tmp_path)
