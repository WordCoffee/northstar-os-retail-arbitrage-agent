"""Golden Goose export-manifest schema + no-vendor-leakage validator (B7).

Implements docs/contracts/GOLDEN_GOOSE_SEAM_v1.md §4. Pure and offline: builds
and validates manifest dicts; no network, no file writes, no provider calls.

The manifest is the leak boundary. `assert_no_export_leakage()` enforces the
BFF §6 deny-list by key and by value, so an export can never reveal provider
names, credentials, model ids, routing, cost formulas, or internal paths.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, Mapping

MANIFEST_VERSION = "goose-export/v1"
EXPORT_TYPES = ("opportunities_json", "opportunities_csv", "export_manifest_json")
DEFAULT_DISCLAIMER = (
    "Estimates only. Not a recommendation to buy or an approval to resell."
)

# Key deny-list (case-insensitive, any depth). Mirrors BFF_CONTRACT_v1 §6.
FORBIDDEN_KEYS = {
    "provider", "vendor", "provider_id", "vendor_id", "api_key", "apikey",
    "secret", "token", "password", "credential", "authorization", "auth_header",
    "routing", "route", "model", "model_id", "prompt", "system_prompt",
    "cost_formula", "cost_cents", "unit_cost_usd", "internal", "raw",
    "report_path", "file_path", "filesystem", "path", "stack", "traceback",
    "exception", "env", "dotenv", "scan_id",
}

# Value deny-list (substring, case-insensitive). Mirrors BFF_CONTRACT_v1 §6.
FORBIDDEN_VALUE_TOKENS = (
    "bright data", "brightdata", "chocodata", "easyparser", "openwebninja",
    "unwrangle", "scavio", "canopy", "dataforseo", "firecrawl", "scrape.do",
    "rapidapi", "ollama", "openrouter", "deepseek", "relace", "deepinfra",
    "open-inference",
)

_ABS_PATH_RE = re.compile(r"([A-Za-z]:\\|/Users/|/home/|/tmp/|\\\\|^/)")
_SECRET_SHAPE_RE = re.compile(r"(sk-[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]{10,}|eyJ[A-Za-z0-9._-]{20,})")


class ExportLeakageError(ValueError):
    """Raised when a manifest/export would leak provider or internal data."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_manifest(
    *,
    export_id: str,
    job_id: str,
    export_type: str,
    row_count: int,
    columns: Iterable[str],
    tiers: Mapping[str, int] | None = None,
    filters: Mapping[str, object] | None = None,
) -> dict:
    """Build a conforming export manifest (B7 §4). Caller supplies the opaque
    ids; this function never accepts provider hints or file paths."""
    if export_type not in EXPORT_TYPES:
        raise ValueError("unknown export_type: %r" % (export_type,))
    return {
        "manifest_version": MANIFEST_VERSION,
        "export_id": export_id,
        "job_id": job_id,
        "created_at": _now(),
        "service": "golden_goose",
        "export_type": export_type,
        "row_count": int(row_count),
        "schema_version": "opportunities/v1",
        "tiers": dict(tiers or {}),
        "filters": dict(filters or {}),
        "columns": list(columns),
        "currency": "USD",
        "disclaimer": DEFAULT_DISCLAIMER,
    }


def _iter_kv(obj, path="manifest"):
    """Yield (key_or_None, value, path) for every node, including scalar leaves
    inside lists, so value scanning never skips list items."""
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            yield str(k), v, path
            yield from _iter_kv(v, "%s.%s" % (path, k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield None, v, "%s[%d]" % (path, i)
            yield from _iter_kv(v, "%s[%d]" % (path, i))
    else:
        yield None, obj, path


def assert_no_export_leakage(manifest: dict) -> dict:
    """Raise ExportLeakageError if the manifest leaks, else return it."""
    for key, value, path in _iter_kv(manifest):
        if key is not None and key.lower() in FORBIDDEN_KEYS:
            raise ExportLeakageError("forbidden key %r at %s" % (key, path))
        if isinstance(value, str):
            low = value.lower()
            for tok in FORBIDDEN_VALUE_TOKENS:
                if tok in low:
                    raise ExportLeakageError("forbidden value token %r at %s" % (tok, path))
            if _ABS_PATH_RE.search(value):
                raise ExportLeakageError("absolute filesystem path at %s" % (path,))
            if _SECRET_SHAPE_RE.search(value):
                raise ExportLeakageError("secret-shaped value at %s" % (path,))
    return manifest