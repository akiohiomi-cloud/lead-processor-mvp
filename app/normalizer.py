from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

import phonenumbers
from email_validator import EmailNotValidError, validate_email

from .config import get_settings

log = logging.getLogger(__name__)

_SEEN_DEDUP_KEYS: set[str] = set()


@dataclass
class NormalizedLead:
    name: str
    phone_raw: str
    phone_e164: str | None
    email_raw: str
    email_normalized: str | None
    message: str | None
    source: str | None
    is_valid: bool
    issues: list[str] = field(default_factory=list)
    dedup_key: str | None = None
    is_duplicate: bool = False


def _normalize_phone(phone: str, region: str) -> tuple[str | None, str | None]:
    try:
        parsed = phonenumbers.parse(phone, region)
    except phonenumbers.NumberParseException as e:
        return None, f"phone: parse failed ({e})"
    if not phonenumbers.is_valid_number(parsed):
        return None, "phone: not a valid number"
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return e164, None


def _normalize_email(email: str) -> tuple[str | None, str | None]:
    try:
        result = validate_email(email, check_deliverability=False)
    except EmailNotValidError as e:
        return None, f"email: {e}"
    return result.normalized, None


def _dedup_key(phone_e164: str, email_norm: str) -> str:
    raw = f"{phone_e164}:{email_norm}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize(
    name: str,
    phone: str,
    email: str,
    message: str | None = None,
    source: str | None = None,
) -> NormalizedLead:
    s = get_settings()
    issues: list[str] = []

    phone_e164, perr = _normalize_phone(phone, s.phone_default_region)
    if perr:
        issues.append(perr)
    email_norm, eerr = _normalize_email(email)
    if eerr:
        issues.append(eerr)

    is_valid = phone_e164 is not None and email_norm is not None
    dedup_key: str | None = None
    is_duplicate = False
    if is_valid:
        dedup_key = _dedup_key(phone_e164, email_norm)
        if dedup_key in _SEEN_DEDUP_KEYS:
            is_duplicate = True
        else:
            _SEEN_DEDUP_KEYS.add(dedup_key)

    return NormalizedLead(
        name=name,
        phone_raw=phone,
        phone_e164=phone_e164,
        email_raw=email,
        email_normalized=email_norm,
        message=message,
        source=source,
        is_valid=is_valid,
        issues=issues,
        dedup_key=dedup_key,
        is_duplicate=is_duplicate,
    )


def _reset_dedup_for_tests() -> None:
    _SEEN_DEDUP_KEYS.clear()
