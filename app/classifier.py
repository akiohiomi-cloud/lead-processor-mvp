from __future__ import annotations

import logging
from dataclasses import dataclass

import anthropic
from pydantic import BaseModel, Field

from .config import get_settings
from .normalizer import NormalizedLead

log = logging.getLogger(__name__)


class LeadClassification(BaseModel):
    """Schema for Anthropic Structured Outputs."""

    summary: str = Field(description="One-paragraph summary of the lead and their intent")
    score: int = Field(ge=0, le=100, description="Lead quality score 0-100")
    reason: str = Field(description="Brief justification for the score")


@dataclass
class ClassifiedLead:
    summary: str
    score: int
    reason: str
    lead_class: str  # hot | warm | cold | junk | unknown


_SYSTEM_PROMPT = """You are a lead-qualification assistant for a marketing services agency.
Given a lead submitted via a landing-page form, return:
- summary: one short paragraph (max 280 chars) describing the lead and their apparent need.
- score: integer 0-100 representing lead quality.
- reason: 1-2 sentences justifying the score.

TODO (Mesiaf): fill in scoring criteria here — urgency signals, stated budget, decision authority,
fit with our services, contact-quality hints, etc.

If the message is empty or low-signal, return a low score with reason "low signal".
Stay neutral and concise.

Reply in Ukrainian — the team reviewing the leads works in Ukrainian."""


def _derive_class(score: int) -> str:
    if score >= 70:
        return "hot"
    if score >= 40:
        return "warm"
    return "cold"


def _build_user_message(lead: NormalizedLead) -> str:
    return (
        f"Name: {lead.name}\n"
        f"Phone (E.164): {lead.phone_e164}\n"
        f"Email: {lead.email_normalized}\n"
        f"Source: {lead.source or 'unknown'}\n"
        f"Message: {lead.message or '(empty)'}"
    )


def _call_anthropic(
    lead: NormalizedLead,
    client: anthropic.Anthropic,
    model: str,
) -> tuple[LeadClassification | None, str | None]:
    result = client.messages.parse(
        model=model,
        max_tokens=400,
        temperature=0,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(lead)}],
        output_format=LeadClassification,
        timeout=20.0,
    )
    return result.parsed_output, result.stop_reason


def classify(
    lead: NormalizedLead,
    client: anthropic.Anthropic | None = None,
) -> ClassifiedLead:
    if not lead.is_valid:
        return ClassifiedLead(
            summary=f"Invalid lead: {'; '.join(lead.issues) or 'no details'}",
            score=0,
            reason="validation failed",
            lead_class="junk",
        )

    settings = get_settings()

    if settings.dry_run or not settings.anthropic_api_key:
        return ClassifiedLead(
            summary=f"[DRY_RUN] {(lead.message or '(no message)')[:200]}",
            score=50,
            reason="dry-run mode: AI not called",
            lead_class=_derive_class(50),
        )

    if client is None:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        parsed, stop_reason = _call_anthropic(lead, client, settings.anthropic_model)
        if stop_reason == "max_tokens":
            log.info("classifier.retry reason=max_tokens")
            parsed, stop_reason = _call_anthropic(lead, client, settings.anthropic_model)

        if parsed is None:
            log.warning("classifier.no_output stop_reason=%s", stop_reason)
            return ClassifiedLead(
                summary=f"AI returned no parseable output: {(lead.message or '')[:200]}",
                score=0,
                reason=f"no parsed_output (stop_reason={stop_reason})",
                lead_class="unknown",
            )

        score = max(0, min(100, int(parsed.score)))
        return ClassifiedLead(
            summary=parsed.summary,
            score=score,
            reason=parsed.reason,
            lead_class=_derive_class(score),
        )
    except Exception as e:
        log.warning("classifier.error %s: %s", type(e).__name__, e)
        return ClassifiedLead(
            summary=f"Classifier error fallback: {(lead.message or '')[:200]}",
            score=0,
            reason=f"error: {type(e).__name__}",
            lead_class="unknown",
        )
