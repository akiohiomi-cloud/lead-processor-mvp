from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.api import LeadIn, app

client = TestClient(app)


def _valid_payload() -> dict:
    return {
        "name": "Іван Петренко",
        "phone": "+380 67 123 45 67",
        "email": "ivan@example.com",
        "message": "Цікавить впровадження CRM",
        "source": "landing/cta-hero",
    }


def test_accepts_valid_payload():
    r = client.post("/lead", json=_valid_payload())
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "accepted"
    parsed = uuid.UUID(body["lead_id"])
    assert parsed.version == 4


def test_accepts_minimal_payload():
    payload = {"name": "X", "phone": "+1234", "email": "a@b.co"}
    r = client.post("/lead", json=payload)
    assert r.status_code == 202


def test_422_when_missing_required_field():
    payload = {"name": "X", "phone": "+1234"}
    r = client.post("/lead", json=payload)
    assert r.status_code == 422


def test_422_when_name_empty():
    payload = {"name": "", "phone": "+1234", "email": "a@b.co"}
    r = client.post("/lead", json=payload)
    assert r.status_code == 422


def test_422_when_name_whitespace_only():
    payload = {"name": "   ", "phone": "+1234", "email": "a@b.co"}
    r = client.post("/lead", json=payload)
    assert r.status_code == 422


def test_422_on_extra_field():
    payload = {**_valid_payload(), "evil_extra": "hack"}
    r = client.post("/lead", json=payload)
    assert r.status_code == 422


def test_422_on_wrong_type():
    payload = {**_valid_payload(), "name": 12345}
    r = client.post("/lead", json=payload)
    assert r.status_code == 422


def test_model_strips_whitespace():
    m = LeadIn(name="  Vasya  ", phone="  +1234  ", email="  a@b.co  ")
    assert m.name == "Vasya"
    assert m.phone == "+1234"
    assert m.email == "a@b.co"


def test_optional_fields_default_to_none():
    m = LeadIn(name="X", phone="+1234", email="a@b.co")
    assert m.message is None
    assert m.source is None
