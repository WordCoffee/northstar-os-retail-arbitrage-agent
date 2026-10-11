"""Phase 1 security primitives (redaction + secret scanning).

Everything in this package is offline and deterministic; see
``tests/security/`` for the harness that every later phase must keep green.
"""
from .redaction import (
    REDACTED,
    RedactingFormatter,
    RedactionFilter,
    has_sensitive_key,
    redact_object,
    redact_text,
)
from .env_config import (
    MissingSecretError,
    get_secret,
    redacted_summary,
    require_secret,
    secret_presence,
)

__all__ = [
    "REDACTED",
    "RedactingFormatter",
    "RedactionFilter",
    "has_sensitive_key",
    "redact_object",
    "redact_text",
    "MissingSecretError",
    "get_secret",
    "redacted_summary",
    "require_secret",
    "secret_presence",
]
