"""Pattern-based redaction for logs, reports, and audit output (Phase 1).

Rule: credential VALUES never reach logs, reports, prompts, or commits.
This module is pure (stdlib only, no I/O) so every layer can import it:

- ``redact_text``       — redact a string (API keys, GitHub/AWS/Slack tokens,
                           JWTs, PEM private-key blocks, Authorization/Cookie
                           headers, sensitive key=value pairs, email addresses).
- ``redact_object``     — recursive redaction for dict/list structures.
- ``has_sensitive_key`` — key-name check for structured data.
- ``RedactionFilter``   — ``logging.Filter`` that redacts a record before
                           formatting (message + ``extra_data``).
- ``RedactingFormatter``— wraps ANY ``logging.Formatter`` and redacts the final
                           formatted string (catches message, args, extra_data
                           serialization, and exception tracebacks).

Design notes:
- ``redact_text`` is idempotent: redacting already-redacted text is a no-op.
- Patterns are deliberately conservative so ordinary log lines are not mangled;
  every pattern has a unit test with an OBVIOUSLY FAKE value in
  ``tests/security/test_redaction.py``.
- Never put a real credential value in this file. Tests use fake strings only.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Tuple

REDACTED = "[REDACTED]"

# ---------------------------------------------------------------------------
# Pattern table — most specific first; applied top-to-bottom.
# ---------------------------------------------------------------------------
_TOKEN_PATTERNS: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(
        r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"
        r"|\bgithub_pat_[A-Za-z0-9_]{30,}\b"
    )),
    ("openai_style_key", re.compile(r"\bsk[_-][A-Za-z0-9_-]{16,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]{8,}){1,2}\b")),
    (
        "pem_private_key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    (
        "authorization_header",
        re.compile(r"(?i)\b(?:authorization|proxy-authorization)\s*[:=]\s*[^\r\n]+"),
    ),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("cookie_header", re.compile(r"(?i)\b(?:set-cookie|cookie)\s*[:=]\s*[^\r\n]+")),
)

# key=value / "key": "value" pairs for sensitive names (value >= 4 chars).
_KV_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(password|passwd|pwd|secret|tokens?|api[_-]?key|"
    r"access[_-]?key|secret[_-]?key|private[_-]?key|client[_-]?secret|credentials?|"
    r"auth[_-]?token|session[_-]?id)\b([\"']?[ \t]*[:=][ \t]*)"
    r"('[^']*'|\"[^\"]*\"|[^\s,;\"']{4,})"
)

_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Names that mark a STRUCTURED value as sensitive (used by redact_object and
# available to audit code that builds its own views).
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(?:^|[\s_.-])(password|passwd|pwd|secret|tokens?|api[_-]?key|"
    r"access[_-]?key|secret[_-]?key|private[_-]?key|client[_-]?secret|"
    r"credentials?|authorization|bearer|cookies?|sessions?)(?=$|[\s_.-])"
)


def redact_text(text: str) -> str:
    """Return ``text`` with credential shapes replaced by ``[REDACTED]``.

    Idempotent: ``redact_text(redact_text(x)) == redact_text(x)``.
    """
    if not text:
        return text
    out = text
    for _name, pattern in _TOKEN_PATTERNS:
        out = pattern.sub(REDACTED, out)
    out = _KV_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", out)
    out = _EMAIL_PATTERN.sub(REDACTED, out)
    return out


def has_sensitive_key(key: str) -> bool:
    """True when a structured-data key name marks its value as sensitive."""
    return bool(_SENSITIVE_KEY_PATTERN.search(key or ""))


def redact_object(value: Any) -> Any:
    """Recursively redact dict/list structures and strings inside them.

    - dict entries whose KEY is sensitive are replaced by ``[REDACTED]``
      (``None``/empty values are preserved as-is);
    - other values are recursively redacted (strings via ``redact_text``).
    """
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if isinstance(key, str) and has_sensitive_key(key) and item not in (None, ""):
                out[key] = REDACTED
            else:
                out[key] = redact_object(item)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_object(item) for item in value]
    return value


class RedactionFilter(logging.Filter):
    """Redact a log record's rendered message (and ``extra_data``) in place."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            rendered = record.getMessage()
        except Exception:
            return True  # never break logging because of redaction
        red = redact_text(rendered)
        if red != rendered:
            record.msg = red
            record.args = ()
        extra = getattr(record, "extra_data", None)
        if isinstance(extra, (dict, list, tuple)):
            try:
                record.extra_data = redact_object(extra)
            except Exception:
                pass
        return True


class RedactingFormatter(logging.Formatter):
    """Wrap any formatter; redact the FINAL output string it produces."""

    def __init__(self, base: logging.Formatter) -> None:
        super().__init__()
        self.base = base

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        return redact_text(self.base.format(record))
