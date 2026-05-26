from __future__ import annotations

import pytest

from app.normalizer import _reset_dedup_for_tests, normalize


@pytest.fixture(autouse=True)
def _clear_dedup():
    _reset_dedup_for_tests()
    yield
    _reset_dedup_for_tests()


def test_international_ua_phone_to_e164():
    n = normalize("X", "+380 67 123 45 67", "a@b.co")
    assert n.phone_e164 == "+380671234567"
    assert n.is_valid


def test_local_ua_phone_uses_region():
    n = normalize("X", "067 123 45 67", "a@b.co")
    assert n.phone_e164 == "+380671234567"
    assert n.is_valid


def test_invalid_phone_flags_issue():
    n = normalize("X", "12345", "a@b.co")
    assert n.phone_e164 is None
    assert not n.is_valid
    assert any("phone" in i for i in n.issues)


def test_unparseable_phone_flags_issue():
    n = normalize("X", "garbage!!", "a@b.co")
    assert n.phone_e164 is None
    assert not n.is_valid
    assert any("phone" in i for i in n.issues)


def test_invalid_email_flags_issue():
    n = normalize("X", "+380671234567", "not-an-email")
    assert n.email_normalized is None
    assert not n.is_valid
    assert any("email" in i for i in n.issues)


def test_uppercase_email_domain_lowercased():
    n = normalize("X", "+380671234567", "Vasya@Example.COM")
    assert n.email_normalized is not None
    assert n.email_normalized.endswith("example.com")


def test_dedup_key_is_sha256_hex():
    n = normalize("X", "+380671234567", "a@b.co")
    assert n.dedup_key is not None
    assert len(n.dedup_key) == 64
    assert all(c in "0123456789abcdef" for c in n.dedup_key)


def test_duplicate_lead_flagged():
    n1 = normalize("X", "+380671234567", "a@b.co")
    n2 = normalize("Y", "+380671234567", "a@b.co")
    assert not n1.is_duplicate
    assert n2.is_duplicate
    assert n1.dedup_key == n2.dedup_key


def test_distinct_leads_not_duplicates():
    n1 = normalize("X", "+380671234567", "a@b.co")
    n2 = normalize("Y", "+380671234568", "c@d.co")
    assert not n1.is_duplicate
    assert not n2.is_duplicate
    assert n1.dedup_key != n2.dedup_key


def test_invalid_lead_has_no_dedup_key():
    n = normalize("X", "garbage", "a@b.co")
    assert n.dedup_key is None
    assert not n.is_duplicate


def test_two_invalid_calls_have_independent_issues():
    n1 = normalize("X", "garbage", "garbage")
    n2 = normalize("Y", "+380671234567", "a@b.co")
    assert len(n1.issues) == 2
    assert len(n2.issues) == 0
