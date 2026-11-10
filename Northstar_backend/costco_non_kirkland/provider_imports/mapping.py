"""Canonical provider market-snapshot mapping (Phase 3).

PURE / OFFLINE. Maps a raw provider export row into the canonical market
snapshot contract with full provenance. Unavailable fields stay
`unknown` / `not_reported` — never zero or negative. This extends the existing
`snapshot.build_market_snapshot` provenance envelope.

The provenance object for each canonical field:
    provider_name, provider_export_filename, provider_export_sha256,
    provider_schema_version, provider_row_number, provider_record_id,
    provider_snapshot_id, observed_at, ingested_at, field_provenance,
    field_confidence, is_provider_reported, raw_source_reference,
    freshness_status.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..enums import CaptureStatus, SnapshotEvidenceClass
from .schemas import (
    CANONICAL_FIELDS,
    NOT_AVAILABLE,
    NOT_REPORTED,
    UNKNOWN,
    REQUIRES_MANUAL_REVIEW,
    resolve_mapping,
)
from .validators import (
    parse_bool_3way,
    parse_float,
    parse_int,
    normalize_value,
    valid_asin,
)

MARKET_SNAPSHOT_SCHEMA_VERSION = "provider-market-snapshot-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freshness_status(observed_at: Optional[str]) -> str:
    if not observed_at:
        return "unknown"
    try:
        from datetime import datetime as _dt
        dt = _dt.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        age = (_dt.now(tz=dt.tzinfo if dt.tzinfo else None) - dt).total_seconds()
        if age is None or dt.tzinfo is None:
            return "unknown"
        hours = age / 3600.0
        if hours <= 24:
            return "fresh"
        if hours <= 72:
            return "aging"
        return "stale"
    except (ValueError, TypeError):
        return "unknown"


def map_row_to_canonical(row: Dict[str, Any], *, provider: str, kind: str,
                         provider_export_filename: str, provider_export_sha256: str,
                         provider_schema_version: str, provider_row_number: int,
                         provider_record_id: Optional[str] = None,
                         provider_snapshot_id: Optional[str] = None,
                         observed_at: Optional[str] = None,
                         ingested_at: Optional[str] = None) -> Dict[str, Any]:
    """Map a raw provider row into the canonical market-snapshot contract.

    Returns:
    {
      "schema_version": "provider-market-snapshot-v1",
      "provider": provider,
      "asin": <normalized asin or None>,
      "fields": { canonical_field: provenance_envelope },
      "capture_statuses": {...},
      "identity": {...},   # canonical identity group
      "marketplace": {...},
      "demand": {...},
      "fees": {...},
      "size": {...},
      "risk": {...},
      "provenance": {...},
    }
    """
    ingested_at = ingested_at or _now()
    observed_at = observed_at or ingested_at
    row_number = provider_row_number

    # Build a flat canonical value map first.
    canonical_values: Dict[str, Any] = {}
    used_keys: Dict[str, str] = {}  # canonical_field -> raw_key

    if kind == "csv":
        for raw_key, raw_val in row.items():
            canonical = resolve_mapping(provider, "csv", raw_key)
            if canonical and canonical not in used_keys:
                canonical_values[canonical] = raw_val
                used_keys[canonical] = str(raw_key)
    else:  # json
        for raw_key, raw_val in row.items():
            canonical = resolve_mapping(provider, "json", str(raw_key))
            if canonical and canonical not in used_keys:
                canonical_values[canonical] = raw_val
                used_keys[canonical] = str(raw_key)

    # --- normalize typed values ---------------------------------------------
    norm: Dict[str, Any] = {}
    for fld in CANONICAL_FIELDS:
        raw = canonical_values.get(fld)
        if fld in ("asin", "parent_asin"):
            v = normalize_value(raw)
            norm[fld] = v.upper() if v else None
        elif fld == "title":
            norm[fld] = normalize_value(raw)
        elif fld in ("buy_box_price", "lowest_price", "lowest_fba_price", "lowest_mfn_price",
                     "referral_fee_amount", "fba_fulfillment_fee", "storage_fee_estimate",
                     "estimated_monthly_revenue"):
            norm[fld] = parse_float(raw)
        elif fld in ("referral_fee_rate",):
            v = parse_float(raw)
            # Allow both "0.15" and "15%" representations.
            if v is not None and isinstance(v, float):
                if isinstance(raw, str) and raw.strip().endswith("%"):
                    v = v / 100.0
                elif v > 1.0:
                    v = v / 100.0
            norm[fld] = v
        elif fld in ("shipping_weight_lb",):
            norm[fld] = parse_float(raw)
        elif fld in ("active_seller_count", "active_fba_seller_count", "active_mfn_seller_count",
                     "item_count", "pack_count", "unit_count"):
            norm[fld] = parse_int(raw)
        elif fld in ("amazon_retail_active", "brand_owner_seller_active", "standard_size_status"):
            norm[fld] = parse_bool_3way(raw)
        elif fld in ("estimated_monthly_sales",):
            norm[fld] = parse_float(raw)
        else:
            norm[fld] = normalize_value(raw)

    # --- provenance envelopes --------------------------------------------------
    fields: Dict[str, Dict[str, Any]] = {}
    for fld in CANONICAL_FIELDS:
        value = norm.get(fld)
        present = value is not None
        fields[fld] = {
            "value": value,
            "provider_name": provider,
            "provider_export_filename": provider_export_filename,
            "provider_export_sha256": provider_export_sha256,
            "provider_schema_version": provider_schema_version,
            "provider_row_number": row_number,
            "provider_record_id": provider_record_id,
            "provider_snapshot_id": provider_snapshot_id,
            "observed_at": observed_at,
            "ingested_at": ingested_at,
            "field_provenance": used_keys.get(fld),
            "field_confidence": 0.9 if present else None,
            "is_provider_reported": present,
            "raw_source_reference": f"{provider_export_filename}#{row_number}",
            "freshness_status": _freshness_status(observed_at) if present else "unknown",
        }

    capture_statuses = {
        fld: (CaptureStatus.CAPTURED.value if fields[fld]["value"] is not None
              else CaptureStatus.UNAVAILABLE.value)
        for fld in CANONICAL_FIELDS
    }

    asin = norm.get("asin")
    return {
        "schema_version": MARKET_SNAPSHOT_SCHEMA_VERSION,
        "provider": provider,
        "asin": asin,
        "capture_statuses": capture_statuses,
        "fields": fields,
        "identity": {f: norm.get(f) for f in CANONICAL_FIELDS if CANONICAL_FIELDS[f] == "identity"},
        "marketplace": {f: norm.get(f) for f in CANONICAL_FIELDS if CANONICAL_FIELDS[f] == "marketplace"},
        "demand": {f: norm.get(f) for f in CANONICAL_FIELDS if CANONICAL_FIELDS[f] == "demand"},
        "fees": {f: norm.get(f) for f in CANONICAL_FIELDS if CANONICAL_FIELDS[f] == "fees"},
        "size": {f: norm.get(f) for f in CANONICAL_FIELDS if CANONICAL_FIELDS[f] == "size"},
        "risk": {f: norm.get(f) for f in CANONICAL_FIELDS if CANONICAL_FIELDS[f] == "risk"},
    }


def ensure_provider_provenance(market_snapshot: Dict[str, Any]) -> bool:
    """Verify every captured field carries approved provider-export provenance.

    Fail-closed: a field that claims a value WITHOUT an approved provider source
    (or provenance) is not allowed. Returns True if all present fields are
    provider-reported; False otherwise.
    """
    from ..amazon_guard import authorized_market_source
    provider = market_snapshot.get("provider")
    if not authorized_market_source(provider):
        return False
    fields = market_snapshot.get("fields", {})
    for fld, meta in fields.items():
        if meta.get("value") is not None:
            if not meta.get("is_provider_reported"):
                return False
            if not meta.get("provider_export_sha256"):
                return False
    return True