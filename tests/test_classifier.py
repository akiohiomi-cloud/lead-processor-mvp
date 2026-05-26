from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.classifier import LeadClassification, _derive_class, classify
from app.config import get_settings
from app.normalizer import NormalizedLead


@pytest.fixture
def real_mode_env(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _valid_lead(**overrides) -> NormalizedLead:
    base = dict(
        name="Іван",
        phone_raw="+380671234567",
        phone_e164="+380671234567",
        email_raw="i@x.co",
        email_normalized="i@x.co",
        message="Цікавить CRM, 15 юзерів, бюджет 5к/міс.",
        source="landing",
        is_valid=True,
        issues=[],
        dedup_key="abc",
        is_duplicate=False,
    )
    base.update(overrides)
    return NormalizedLead(**base)


def _invalid_lead() -> NormalizedLead:
    return NormalizedLead(
        name="X",
        phone_raw="bad",
        phone_e164=None,
        email_raw="bad",
        email_normalized=None,
        message=None,
        source=None,
        is_valid=False,
        issues=["phone: not a valid number", "email: bad"],
    )


def _mock_parsed_message(summary: str, score: int, reason: str, stop_reason: str = "end_turn"):
    parsed = MagicMock()
    parsed.parsed_output = LeadClassification(summary=summary, score=score, reason=reason)
    parsed.stop_reason = stop_reason
    return parsed


def _mock_client_returning(*parsed_messages) -> MagicMock:
    client = MagicMock()
    if len(parsed_messages) == 1:
        client.messages.parse.return_value = parsed_messages[0]
    else:
        client.messages.parse.side_effect = list(parsed_messages)
    return client


def test_derive_class_thresholds():
    assert _derive_class(100) == "hot"
    assert _derive_class(70) == "hot"
    assert _derive_class(69) == "warm"
    assert _derive_class(40) == "warm"
    assert _derive_class(39) == "cold"
    assert _derive_class(0) == "cold"


def test_invalid_lead_returns_junk_without_calling_ai(real_mode_env):
    client = MagicMock()
    out = classify(_invalid_lead(), client=client)
    assert out.lead_class == "junk"
    assert out.score == 0
    assert "Invalid lead" in out.summary
    client.messages.parse.assert_not_called()


def test_dry_run_returns_canned_response(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    get_settings.cache_clear()
    out = classify(_valid_lead(message="hello"))
    assert "[DRY_RUN]" in out.summary
    assert out.score == 50
    assert out.lead_class == "warm"


def test_missing_api_key_returns_canned(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    out = classify(_valid_lead())
    assert "[DRY_RUN]" in out.summary
    assert out.lead_class == "warm"


def test_real_path_hot_score(real_mode_env):
    client = _mock_client_returning(_mock_parsed_message("auto", 85, "high signal"))
    out = classify(_valid_lead(), client=client)
    assert out.lead_class == "hot"
    assert out.score == 85
    assert out.summary == "auto"


def test_real_path_warm_score(real_mode_env):
    client = _mock_client_returning(_mock_parsed_message("auto", 55, "ok"))
    out = classify(_valid_lead(), client=client)
    assert out.lead_class == "warm"


def test_real_path_cold_score(real_mode_env):
    client = _mock_client_returning(_mock_parsed_message("auto", 20, "weak"))
    out = classify(_valid_lead(), client=client)
    assert out.lead_class == "cold"


def test_score_clamped_to_100(real_mode_env):
    fake = MagicMock()
    fake.parsed_output = MagicMock(summary="x", score=200, reason="y")
    fake.stop_reason = "end_turn"
    client = _mock_client_returning(fake)
    out = classify(_valid_lead(), client=client)
    assert out.score == 100
    assert out.lead_class == "hot"


def test_score_clamped_to_0(real_mode_env):
    fake = MagicMock()
    fake.parsed_output = MagicMock(summary="x", score=-50, reason="y")
    fake.stop_reason = "end_turn"
    client = _mock_client_returning(fake)
    out = classify(_valid_lead(), client=client)
    assert out.score == 0
    assert out.lead_class == "cold"


def test_max_tokens_triggers_one_retry(real_mode_env):
    first = _mock_parsed_message("truncated", 50, "cut", stop_reason="max_tokens")
    second = _mock_parsed_message("complete", 75, "ok", stop_reason="end_turn")
    client = _mock_client_returning(first, second)
    out = classify(_valid_lead(), client=client)
    assert client.messages.parse.call_count == 2
    assert out.summary == "complete"
    assert out.lead_class == "hot"


def test_exception_returns_unknown(real_mode_env):
    client = MagicMock()
    client.messages.parse.side_effect = RuntimeError("api down")
    out = classify(_valid_lead(), client=client)
    assert out.lead_class == "unknown"
    assert out.score == 0
    assert "error" in out.reason.lower()


def test_no_parsed_output_returns_unknown(real_mode_env):
    fake = MagicMock()
    fake.parsed_output = None
    fake.stop_reason = "refusal"
    client = _mock_client_returning(fake)
    out = classify(_valid_lead(), client=client)
    assert out.lead_class == "unknown"
    assert "refusal" in out.reason
