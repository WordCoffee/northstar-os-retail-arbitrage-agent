"""Shared helpers for manual provider export imports.

PURE / OFFLINE. No network calls. Provides file hashing, provider detection,
CSV/JSON parsing, and row-status helpers.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..enums import ImportRowStatus

# Retired providers fail closed by name (kept in sync with providers.RETIRED_PROVIDERS).
RETIRED_PROVIDERS = ("sellersprite",)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str) -> str:
    """Compute the SHA-256 of a file (used for idempotency)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Provider / schema detection
# ---------------------------------------------------------------------------

PROVIDER_HINTS = {
    "selleramp": ("selleramp", "sas_", "sas ", "seller assistant", "selleramp"),
}

# Retired-provider filename hints: a file that names one of these is rejected as
# retired rather than silently treated as a supported provider.
RETIRED_PROVIDER_HINTS = ("sellersprite", "sprite")

SELLERAMP_FIELD_HINTS = (
    "asin", "title", "price", "buy box", "seller", "fba", "fbm", "offers",
    "monthly sales", "est sales",
)


def detect_provider(rows: Optional[List[Dict[str, Any]]] = None,
                    filename: Optional[str] = None,
                    explicit: Optional[str] = None) -> Tuple[Optional[str], str]:
    """Detect provider from filename + column hints.

    Returns (provider | None, note). Retired providers (SellerSprite) are
    rejected by name; unknown explicit providers are rejected. Explicit
    SellerAmp always wins (documented operator override).
    """
    filename_lower = (filename or "").lower()
    columns = set()
    if rows:
        for r in rows:
            columns.update((str(k).lower() for k in (r or {}).keys()))
            break

    if explicit:
        e = explicit.lower()
        if e in RETIRED_PROVIDERS:
            return None, f"retired provider {explicit!r} — trial expired; not supported"
        if e != "selleramp":
            return None, f"unsupported explicit provider {explicit!r}"
        # Explicit choice always wins (documented operator override).
        return e, "explicit provider override"

    for hint in RETIRED_PROVIDER_HINTS:
        if hint in filename_lower:
            return None, f"retired provider file detected ({hint!r}) — not supported"

    score = 0
    for hint in PROVIDER_HINTS["selleramp"]:
        if hint in filename_lower:
            score += 2
    for col in columns:
        c = col.lower()
        for h in SELLERAMP_FIELD_HINTS:
            if h in c:
                score += 1

    if score > 0:
        return "selleramp", "detected via column hints"
    return None, "no provider hints found; --provider required"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_csv_text(text: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for r in reader:
        if r:
            rows.append({k: ("" if v is None else v) for k, v in r.items()})
    return rows


def parse_json_text(text: str) -> List[Dict[str, Any]]:
    data = json.loads(text)
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        for key in ("records", "items", "asins", "rows", "data"):
            if isinstance(data.get(key), list):
                return [d for d in data[key] if isinstance(d, dict)]
        # A single record dict
        if any(isinstance(v, (str, int, float)) for v in data.values()):
            return [data]
    return []


def parse_provider_file(path: str, *, explicit_provider: Optional[str] = None,
                        schema_version: Optional[str] = None) -> Dict[str, Any]:
    """Parse a local export file (CSV or JSON) with provider detection.

    Returns a dict with: provider, schema_version, rows (raw dicts), filename,
    sha256, parse_kind. Raises ValueError on unsupported file type.
    """
    with open(path, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    lower = path.lower()
    if lower.endswith(".csv"):
        rows = parse_csv_text(text)
        kind = "csv"
    elif lower.endswith(".json"):
        rows = parse_json_text(text)
        kind = "json"
    else:
        raise ValueError(f"Unsupported file type (expected .csv or .json): {path}")

    provider, note = detect_provider(rows, filename=path, explicit=explicit_provider)
    return {
        "provider": provider,
        "provider_detection_note": note,
        "schema_version": schema_version,
        "rows": rows,
        "filename": path,
        "sha256": sha256_file(path),
        "parse_kind": kind,
        "row_count": len(rows),
    }


# ---------------------------------------------------------------------------
# Row status helpers
# ---------------------------------------------------------------------------

def row_status_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    out = {s.value: 0 for s in ImportRowStatus}
    for r in rows:
        status = r.get("_import_status")
        if status in out:
            out[status] += 1
    return out


class ImportErrorKind:
    """Typed import error kinds (fail-closed)."""
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    AMBIGUOUS_PROVIDER = "ambiguous_provider"
    UNSUPPORTED_FILE = "unsupported_file"
    PARSE_ERROR = "parse_error"
    REQUIRED_FIELD_MISSING = "required_field_missing"
    IDENTITY_AMBIGUOUS = "identity_ambiguous"