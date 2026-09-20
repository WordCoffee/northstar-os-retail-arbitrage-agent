"""Phase G — FIXES_50 #21 error-code taxonomy tests (offline)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder.gg_errors import (  # noqa: E402
    ERROR_CODES,
    ErrorCode,
    error_record,
    valid_error_code,
)


def test_taxonomy_honors_operator_set():
    for code in ("PROVIDER_ERROR", "VALIDATION_ERROR", "TIMEOUT", "RATE_LIMIT", "UNKNOWN"):
        assert code in ERROR_CODES


def test_doc_taxonomy_superset():
    for code in ("AUTH", "PARSE"):
        assert valid_error_code(code) is True


def test_unknown_code_coerced_to_unknown():
    r = error_record("BOGUS_CODE", "matching", "x")
    assert r["code"] == "UNKNOWN"


def test_record_carries_context():
    r = error_record("TIMEOUT", "enrich", "provider hung",
                     scan_id="scan1", asin="B0X", provider="chocodata",
                     extra={"ms": 120_000})
    assert r["scan_id"] == "scan1" and r["asin"] == "B0X"
    assert r["provider"] == "chocodata" and r["ms"] == 120_000


def test_codes_are_enum_values():
    assert ErrorCode.PROVIDER_ERROR.value == "PROVIDER_ERROR"
    assert len(ERROR_CODES) == len(set(ERROR_CODES))