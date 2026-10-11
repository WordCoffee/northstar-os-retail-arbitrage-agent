"""Phase 1 security-harness tests — redaction primitives.

All values in this file are OBVIOUSLY FAKE. No real credential appears here.
Run: python -m pytest tests/security -q   (from the repo root)
"""
from __future__ import annotations

import logging

from northstar.security.redaction import (
    REDACTED,
    RedactingFormatter,
    RedactionFilter,
    has_sensitive_key,
    redact_object,
    redact_text,
)

# --- fake fixtures (never real) ----------------------------------------------
FAKE_OPENAI = "sk-FAKEFAKEFAKEFAKE123456"
FAKE_GITHUB = "ghp_" + "F" * 40
FAKE_AWS = "AKIA" + "FAKEFAKEFAKE0000"
FAKE_SLACK = "xoxb-FAKE-123456789012"
FAKE_JWT = "eyJFAKEFAKEFAKE.eyJFAKEFAKEFAKE.signatureFAKE"
FAKE_EMAIL = "fake.person@example.com"
FAKE_PASSWORD = "CorrectHorseBatteryStaple99"
FAKE_KEYVALUE = "FAKEKEY1234567890"
FAKE_PEM = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "FAKEPEMCONTENTNOTAREALKEY\n"
    "-----END RSA PRIVATE KEY-----"
)


class TestRedactText:
    def test_openai_style_key_is_redacted(self):
        out = redact_text(f"provider key loaded: {FAKE_OPENAI} ok")
        assert FAKE_OPENAI not in out
        assert REDACTED in out

    def test_github_token_is_redacted(self):
        out = redact_text(f"clone token {FAKE_GITHUB}")
        assert FAKE_GITHUB not in out
        assert REDACTED in out

    def test_aws_access_key_is_redacted(self):
        out = redact_text(f"aws key id {FAKE_AWS}")
        assert FAKE_AWS not in out
        assert REDACTED in out

    def test_slack_token_is_redacted(self):
        out = redact_text(f"slack {FAKE_SLACK}")
        assert FAKE_SLACK not in out
        assert REDACTED in out

    def test_jwt_is_redacted(self):
        out = redact_text(f"session jwt {FAKE_JWT}")
        assert FAKE_JWT not in out
        assert REDACTED in out

    def test_pem_private_key_is_redacted(self):
        out = redact_text(f"key material:\n{FAKE_PEM}\ndone")
        assert "FAKEPEMCONTENTNOTAREALKEY" not in out
        assert REDACTED in out

    def test_authorization_header_is_redacted(self):
        out = redact_text(f"Authorization: Bearer {FAKE_OPENAI}")
        assert FAKE_OPENAI not in out
        assert REDACTED in out

    def test_cookie_header_is_redacted(self):
        out = redact_text("Set-Cookie: session=FAKEcookievalue123; HttpOnly")
        assert "FAKEcookievalue123" not in out
        assert REDACTED in out

    def test_sensitive_key_value_pairs_are_redacted(self):
        out = redact_text(f"api_key={FAKE_KEYVALUE} password={FAKE_PASSWORD}")
        assert FAKE_KEYVALUE not in out
        assert FAKE_PASSWORD not in out
        assert REDACTED in out

    def test_compound_env_names_are_redacted(self):
        # Regression: `SCAVIO_API_KEY=...` style names (underscore-joined,
        # no word boundary before the keyword) must still redact.
        out = redact_text("SCAVIO_API_KEY=K7q2Wm9Zb4Tt6Yp1")
        assert "K7q2Wm9Zb4Tt6Yp1" not in out
        out2 = redact_text("BRIGHTDATA_API_KEY=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        assert "aaaaaaaa-bbbb" not in out2

    def test_sk_underscore_key_is_redacted(self):
        fake = "sk_" + "F" * 40
        out = redact_text(f"key {fake} ok")
        assert fake not in out
        assert REDACTED in out

    def test_all_github_prefixes_are_redacted(self):
        # Multi-prefix regression (the 2026-09 leak audit missed `ghp_`).
        for prefix in ("ghp", "gho", "ghu", "ghs", "ghr"):
            fake = prefix + "_" + "F" * 40
            out = redact_text(f"token {fake} end")
            assert fake not in out, prefix
        pat = "github_pat_" + "F" * 40
        assert pat not in redact_text(f"pat {pat} end")

    def test_email_is_redacted(self):
        out = redact_text(f"owner login: {FAKE_EMAIL}")
        assert FAKE_EMAIL not in out
        assert REDACTED in out

    def test_benign_lines_are_untouched(self):
        sample = "Loaded 25 items in 120ms from costco.com (batch 3/9) rss=0.46GB"
        assert redact_text(sample) == sample

    def test_idempotent(self):
        once = redact_text(f"Authorization: Bearer {FAKE_OPENAI} and {FAKE_EMAIL}")
        assert redact_text(once) == once


class TestRedactObject:
    def test_dict_values_by_sensitive_key(self):
        out = redact_object({"password": FAKE_PASSWORD, "note": "ok", "count": 3})
        assert out["password"] == REDACTED
        assert out["note"] == "ok"
        assert out["count"] == 3

    def test_nested_structures(self):
        obj = {
            "outer": {"api_key": FAKE_KEYVALUE, "keep": "x"},
            "list": [{"token": FAKE_KEYVALUE}],
        }
        out = redact_object(obj)
        assert out["outer"]["api_key"] == REDACTED
        assert out["outer"]["keep"] == "x"
        assert out["list"][0]["token"] == REDACTED

    def test_string_values_are_text_redacted(self):
        out = redact_object({"detail": f"sent to {FAKE_EMAIL}"})
        assert FAKE_EMAIL not in out["detail"]

    def test_none_and_empty_preserved(self):
        out = redact_object({"password": None, "token": ""})
        assert out["password"] is None
        assert out["token"] == ""


class TestHasSensitiveKey:
    def test_positive(self):
        for key in (
            "password",
            "api_key",
            "x-api-key",
            "session_id",
            "cookies",
            "authorization",
        ):
            assert has_sensitive_key(key), key

    def test_negative(self):
        for key in ("tokenizer", "author", "model", "count", "note"):
            assert not has_sensitive_key(key), key


class TestLoggingPieces:
    def test_filter_redacts_record_message(self):
        record = logging.LogRecord(
            name="t",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="api_key=%s",
            args=(FAKE_KEYVALUE,),
            exc_info=None,
        )
        assert RedactionFilter().filter(record) is True
        assert FAKE_KEYVALUE not in record.getMessage()
        assert REDACTED in record.getMessage()

    def test_filter_redacts_extra_data(self):
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="provider call",
            args=(),
            exc_info=None,
        )
        record.extra_data = {"token": FAKE_KEYVALUE, "note": "fine"}
        RedactionFilter().filter(record)
        assert record.extra_data["token"] == REDACTED
        assert record.extra_data["note"] == "fine"

    def test_formatter_wraps_any_formatter(self):
        base = logging.Formatter("%(levelname)s %(message)s")
        record = logging.LogRecord(
            name="t",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg=f"cookie={FAKE_KEYVALUE}",
            args=(),
            exc_info=None,
        )
        out = RedactingFormatter(base).format(record)
        assert FAKE_KEYVALUE not in out
        assert REDACTED in out
