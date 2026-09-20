"""Golden Goose error-code taxonomy (Phase G — FIXES_50 #21).

Every failure the pipeline or its adapters produce maps onto one of these
codes; structured logs, the per-ASIN audit trail (#22), alerts (#25), and the
per-provider error budget (#26b) all reference them so an operator can filter
a scan record by a single stable token.

Pure / offline. The taxonomy is a contract, not an execution gate.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """Stable error codes for Golden Goose failures (FIXES_50 #21)."""

    PROVIDER_ERROR = "PROVIDER_ERROR"   # provider returned an error / bad data shape
    AUTH = "AUTH"                       # auth/config error talking to a provider
    RATE_LIMIT = "RATE_LIMIT"           # throttled by a provider
    PARSE = "PARSE"                     # payload did not parse as expected
    VALIDATION_ERROR = "VALIDATION_ERROR"  # candidate failed a quality gate
    TIMEOUT = "TIMEOUT"                 # call or scan exceeded its deadline
    UNKNOWN = "UNKNOWN"                 # anything not otherwise classified


ERROR_CODES = tuple(c.value for c in ErrorCode)


def valid_error_code(code: str) -> bool:
    return code.upper() in ERROR_CODES


def error_record(
    code: str,
    stage: str,
    message: str,
    *,
    scan_id: Optional[str] = None,
    asin: Optional[str] = None,
    provider: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a canonical error record for audit/alert consumers.

    Unknown codes are coerced to UNKNOWN so downstream filters never break.
    """
    c = code.upper() if valid_error_code(code) else ErrorCode.UNKNOWN.value
    record: Dict[str, Any] = {"code": c, "stage": stage, "message": message}
    if scan_id:
        record["scan_id"] = scan_id
    if asin:
        record["asin"] = asin
    if provider:
        record["provider"] = provider
    if extra:
        record.update(extra)
    return record