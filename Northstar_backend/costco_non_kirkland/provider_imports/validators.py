"""Provider import row validation.

PURE / OFFLINE. Validates raw provider rows against required qualification
fields. Missing fields remain `unknown` / `missing_required_fields`; strict mode
rejects any row missing required fields; allow-partial saves incomplete rows as
`needs_enrichment` (never qualified).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ..enums import ImportRowStatus

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")

# Required identity fields for any usable market snapshot.
REQUIRED_IDENTITY_FIELDS = ("asin", "title")

# Fields required for a candidate to be considered for QUALIFICATION.
REQUIRED_QUALIFICATION_FIELDS = (
    "asin",
    "buy_box_price",
    "active_seller_count",
    "active_fba_seller_count",
    "active_mfn_seller_count",
    "amazon_retail_active",
    "asin_sellability_status",
    "category_restriction_status",
    "brand_restriction_status",
    "product_restriction_status",
)


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def normalize_value(raw: Any) -> Optional[str]:
    """Normalize a raw cell to a trimmed string or None."""
    if is_missing(raw):
        return None
    s = str(raw).strip()
    return s or None


def parse_int(raw: Any) -> Optional[int]:
    v = normalize_value(raw)
    if v is None:
        return None
    try:
        return int(float(v.replace(",", "")))
    except (ValueError, TypeError):
        return None


def parse_float(raw: Any) -> Optional[float]:
    v = normalize_value(raw)
    if v is None:
        return None
    cleaned = v.replace("$", "").replace(",", "").replace(" USD", "").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def parse_bool_3way(raw: Any) -> Optional[bool]:
    """Parse true/false/unknown. Returns None for unknown/unavailable (never False)."""
    v = normalize_value(raw)
    if v is None:
        return None
    low = v.lower()
    if low in ("true", "yes", "1", "y", "present", "active", "in stock"):
        return True
    if low in ("false", "no", "0", "n", "absent", "inactive", "not present", "none"):
        return False
    return None


def valid_asin(asin: Optional[str]) -> bool:
    return bool(asin) and bool(ASIN_RE.match(asin.upper()))


def validate_row_required_fields(row: Dict[str, Any], *,
                                 required: Tuple[str, ...] = REQUIRED_QUALIFICATION_FIELDS,
                                 strict: bool = False) -> Tuple[bool, List[str]]:
    """Check whether a normalized row has all required fields.

    Returns (ok, missing_fields). In strict mode, ANY missing required field
    fails; otherwise the identity fields (asin, title) must be present.
    """
    missing = [f for f in required if is_missing(row.get(f))]
    if strict:
        return (len(missing) == 0, missing)
    identity_missing = [f for f in REQUIRED_IDENTITY_FIELDS if is_missing(row.get(f))]
    return (len(identity_missing) == 0, missing or identity_missing)


def classify_row(row: Dict[str, Any], *, strict: bool = False) -> str:
    """Classify a row outcome (ImportRowStatus value)."""
    if not valid_asin(row.get("asin")):
        return ImportRowStatus.IDENTITY_AMBIGUOUS.value
    ok, missing = validate_row_required_fields(row, strict=strict)
    if not ok:
        return ImportRowStatus.MISSING_REQUIRED_FIELDS.value
    return ImportRowStatus.IMPORTED.value