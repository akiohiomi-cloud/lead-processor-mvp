from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.classifier import ClassifiedLead
from app.config import get_settings
from app.normalizer import NormalizedLead
from app.notifier import (
    ConsoleNotifier,
    TelegramNotifier,
    get_notifier,
    render_message,
)


def _lead(message="hi", lead_class="warm", score=55, **n_over) -> tuple[NormalizedLead, ClassifiedLead]:
    base = dict(
        name="Іван",
        phone_raw="+380671234567",
        phone_e164="+380671234567",
        email_raw="i@x.co",
        email_normalized="i@x.co",
        message=message,
        source="landing",
        is_valid=True,
        issues=[],
        dedup_key="abc",
        is_duplicate=False,
    )
    base.update(n_over)
    n = NormalizedLead(**base)
    c = ClassifiedLead(summary="auto summary", score=score, reason="auto reason", lead_class=lead_class)
    return n, c


def _junk_lead() -> tuple[NormalizedLead, ClassifiedLead]:
    n = NormalizedLead(
        name="X",
        phone_raw="+999",
        phone_e164=None,
        email_raw="bad",
        email_normalized=None,
        message=None,
        source=None,
        is_valid=False,
        issues=["phone: bad", "email: bad"],
    )
    c = ClassifiedLead(summary="Invalid lead: ...", score=0, reason="validation failed", lead_class="junk")
    return n, c


def test_render_message_escapes_html():
    n, c = _lead(message="<script>alert(1)</script>")
    out = render_message("LID", n, c)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_message_junk_has_warning_marker():
    n, c = _junk_lead()
    out = render_message("LID", n, c)
    assert "⚠️" in out
    assert "JUNK" in out


def test_render_message_normal_uses_class_label():
    n, c = _lead(lead_class="hot", score=85)
    out = render_message("LID", n, c)
    assert "HOT" in out
    assert "⚠️" not in out
    assert "Score: 85" in out


def test_render_message_includes_summary_and_id():
    n, c = _lead()
    out = render_message("LEAD-123", n, c)
    assert "auto summary" in out
    assert "LEAD-123" in out


def test_render_message_handles_invalid_lead_phone():
    n, c = _junk_lead()
    out = render_message("LID", n, c)
    assert "+999" in out
    assert "bad" in out


def test_render_message_marks_duplicates():
    n, c = _lead()
    n.is_duplicate = True
    out = render_message("LID", n, c)
    assert "Duplicate: yes" in out


def test_console_notifier_does_not_raise():
    ConsoleNotifier().notify("<b>hello</b>")


def test_factory_dry_run(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    get_settings.cache_clear()
    assert isinstance(get_notifier(), ConsoleNotifier)


def test_factory_real(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    get_settings.cache_clear()
    assert isinstance(get_notifier(), TelegramNotifier)


def test_telegram_skips_when_no_token(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CC")
    get_settings.cache_clear()
    with patch("httpx.Client") as m:
        TelegramNotifier().notify("hi")
    m.assert_not_called()


def test_telegram_skips_when_no_chat_id(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TT")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    get_settings.cache_clear()
    with patch("httpx.Client") as m:
        TelegramNotifier().notify("hi")
    m.assert_not_called()


def test_telegram_sends_correct_payload(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TT")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CC")
    get_settings.cache_clear()

    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_client = MagicMock()
    fake_client.post.return_value = fake_resp

    ctx = MagicMock()
    ctx.__enter__.return_value = fake_client
    ctx.__exit__.return_value = None

    with patch("httpx.Client", return_value=ctx) as m:
        TelegramNotifier().notify("<b>test</b>")

    m.assert_called_once_with(timeout=10.0)
    fake_client.post.assert_called_once()
    args, kwargs = fake_client.post.call_args
    assert args[0] == "https://api.telegram.org/botTT/sendMessage"
    assert kwargs["json"]["chat_id"] == "CC"
    assert kwargs["json"]["text"] == "<b>test</b>"
    assert kwargs["json"]["parse_mode"] == "HTML"
    assert kwargs["json"]["disable_web_page_preview"] is True


def test_telegram_swallows_http_error(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TT")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CC")
    get_settings.cache_clear()

    fake_client = MagicMock()
    fake_client.post.side_effect = httpx.ConnectError("network down")

    ctx = MagicMock()
    ctx.__enter__.return_value = fake_client
    ctx.__exit__.return_value = None

    with patch("httpx.Client", return_value=ctx):
        TelegramNotifier().notify("hi")


def test_pipeline_swallows_notifier_error(monkeypatch):
    """Notifier error must not crash the background task."""
    from app import api

    monkeypatch.setenv("DRY_RUN", "true")
    get_settings.cache_clear()

    failing = MagicMock()
    failing.notify.side_effect = RuntimeError("totally unexpected")

    with patch("app.api.get_notifier", return_value=failing):
        api._process_lead("LID", {
            "name": "X",
            "phone": "+380671234567",
            "email": "a@b.co",
            "message": None,
            "source": None,
        })

    failing.notify.assert_called_once()
