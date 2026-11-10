"""Costco Catalog Enrichment & Identity Resolution (offline).

PURE / OFFLINE. Establishes whether a local Costco source record is
*identity-ready* for provider research, using tri-state / null-first rules.

Hard rules:
  * A Costco item number is NOT a UPC/EAN/GTIN, NOT an MPN, and NOT an ASIN.
  * Unknown UPC/GTIN/MPN is NOT an identifier.
  * Unknown weight is NOT <= 3 lb. Unknown dimensions are NOT standard-size.
  * Unknown split-pack status is NOT approved_split.
  * Unknown pack count is NOT an exact pack match.
  * Unknown brand is NOT automatically non-Kirkland.
  * Missing enrichment data is NOT an error-free field.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Canonical enrichment contract fields (superset).
ENRICHMENT_CONTRACT_FIELDS = (
    # source identity
    "costco_item_number", "source_record_id", "source_dataset", "source_url",
    "brand", "manufacturer", "title", "description", "category_path",
    "costco_price", "sale_price", "unit_price", "currency", "availability",
    "warehouse_location", "purchase_limit", "coupon_instant_savings",
    "observed_at", "source_freshness",
    # identifiers
    "upc", "ean", "gtin", "mpn", "manufacturer_model", "identifier_type",
    "identifier_value", "identifier_source", "identifier_observed_at",
    "identifier_capture_status", "identifier_confidence",
    # pack / physical
    "outer_pack_count", "inner_unit_count", "unit_count", "unit_measure",
    "net_weight", "shipping_weight", "package_length", "package_width",
    "package_height", "size_tier_input", "packaging_description",
    "retail_ready_inner_units", "not_for_individual_resale_flag",
    "split_pack_status", "split_pack_reason",
    # evidence / provenance
    "image_reference", "specification_reference", "source_snapshot_reference",
    "field_provenance", "field_capture_status", "field_limitations",
    "raw_provider_reference", "provider_name", "provider_record_id",
    "provider_snapshot_id", "captured_at", "ingested_at", "freshness_status",
)

IDENTIFIER_FIELDS = ("upc", "ean", "gtin", "mpn")

# Typed capture outcomes for enrichment fields.
CAPTURE_STATUSES = (
    "captured", "field_not_returned", "field_not_supported", "parse_error",
    "stale", "identifier_conflict", "insufficient_source_identity",
    "provider_unavailable", "provider_not_configured",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def normalize_upc(v: Any) -> Optional[str]:
    """Normalize a UPC/EAN/GTIN to digits; None if not a plausible code."""
    s = _clean(v)
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    # GTIN lengths: 8, 12, 13, 14
    if len(digits) in (8, 12, 13, 14):
        return digits
    return None


def has_strong_identifier(record: Dict[str, Any]) -> bool:
    """True when the record has a real product identifier (NOT the item number).

    A strong identifier is a UPC/EAN/GTIN *or* an MPN (MPN requires brand to be
    strong, but presence alone qualifies as 'identifier present').
    """
    for f in ("upc", "ean", "gtin"):
        if normalize_upc(record.get(f)):
            return True
    if _clean(record.get("mpn") or record.get("manufacturer_part_number")):
        return True
    return False


def identifier_kind(record: Dict[str, Any]) -> Optional[str]:
    for f in ("upc", "ean", "gtin"):
        if normalize_upc(record.get(f)):
            return f
    if _clean(record.get("mpn") or record.get("manufacturer_part_number")):
        return "mpn"
    return None


def _weight_known(record: Dict[str, Any], enrichment: Optional[Dict[str, Any]]) -> bool:
    for src in (enrichment or {}, record):
        for f in ("shipping_weight", "net_weight", "size_or_weight_raw", "size_or_weight"):
            if _clean(src.get(f)):
                return True
    return False


def _dimensions_known(enrichment: Optional[Dict[str, Any]]) -> bool:
    e = enrichment or {}
    return all(_clean(e.get(f)) for f in ("package_length", "package_width", "package_height"))


def _pack_known(record: Dict[str, Any], enrichment: Optional[Dict[str, Any]]) -> bool:
    for src in (enrichment or {}, record):
        if src.get("normalized_unit_count") is not None:
            return True
        if _clean(src.get("outer_pack_count")) or _clean(src.get("costco_pack_raw")) or _clean(src.get("unit_count")):
            return True
    return False


def _split_status(record: Dict[str, Any], enrichment: Optional[Dict[str, Any]]) -> str:
    for src in (enrichment or {}, record):
        s = _clean(src.get("split_pack_status") or src.get("split_state"))
        if s:
            return s
    return "unknown"


@dataclass
class IdentityReadiness:
    identity_ready: bool = False
    probable_only: bool = False
    identifier_resolution_required: bool = False
    eligible: bool = True
    missing_identity_fields: List[str] = field(default_factory=list)
    missing_physical_fields: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    identifier_kind: Optional[str] = None
    split_pack_status: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_ready": self.identity_ready,
            "probable_only": self.probable_only,
            "identifier_resolution_required": self.identifier_resolution_required,
            "eligible": self.eligible,
            "missing_identity_fields": list(self.missing_identity_fields),
            "missing_physical_fields": list(self.missing_physical_fields),
            "reasons": list(self.reasons),
            "identifier_kind": self.identifier_kind,
            "split_pack_status": self.split_pack_status,
        }


def assess_identity_readiness(record: Dict[str, Any], enrichment: Optional[Dict[str, Any]] = None,
                              *, allow_probable: bool = False) -> IdentityReadiness:
    """Classify a Costco source record for exact provider-research readiness."""
    r = IdentityReadiness()
    record = record or {}
    enrichment = enrichment or {}

    # --- eligibility (exclusions already applied elsewhere) ---
    if not record.get("eligible_for_costco_non_kirkland_workflow", True):
        r.eligible = False
        r.reasons.append("not_eligible_excluded")
    if not _clean(record.get("brand_normalized") or record.get("brand_raw")):
        r.missing_identity_fields.append("brand")
        r.reasons.append("unknown_brand_not_assumed_non_kirkland")

    if record.get("costco_price") is None:
        r.missing_identity_fields.append("costco_price")
    if not _clean(record.get("observed_at")):
        r.missing_identity_fields.append("observed_at")

    if not _pack_known(record, enrichment):
        r.missing_identity_fields.append("pack_unit_configuration")

    r.identifier_kind = identifier_kind({**enrichment, **record})
    if not has_strong_identifier({**enrichment, **record}):
        r.missing_identity_fields.append("upc_ean_gtin_or_mpn")
        r.reasons.append("identifier_resolution_required")

    # physical (weight/dimensions)
    if not _weight_known(record, enrichment):
        r.missing_physical_fields.append("weight")
    if not _dimensions_known(enrichment):
        r.missing_physical_fields.append("dimensions")

    r.split_pack_status = _split_status(record, enrichment)
    if r.split_pack_status == "unknown":
        r.reasons.append("unknown_split_pack_not_approved_split")

    # --- decision ---
    if not r.eligible:
        r.reasons.append("not_eligible_excluded")
        return r
    has_ident = not r.missing_identity_fields or (
        r.missing_identity_fields == [] )
    ident_ok = "upc_ean_gtin_or_mpn" not in r.missing_identity_fields
    base_ok = (r.eligible
               and "brand" not in r.missing_identity_fields
               and "costco_price" not in r.missing_identity_fields
               and "observed_at" not in r.missing_identity_fields
               and "pack_unit_configuration" not in r.missing_identity_fields)

    if base_ok and ident_ok:
        # identity-ready requires physical sufficiency OR explicit enrichment request
        physical_ok = (not r.missing_physical_fields) or bool(enrichment.get("physical_enrichment_requested"))
        if physical_ok:
            r.identity_ready = True
            r.reasons.append("identity_ready_for_provider_research")
        else:
            r.identity_ready = False
            r.reasons.append("identity_present_physical_pending_enrichment")
    elif base_ok and not ident_ok:
        # No strong identifier: probable-only if operator enabled, else resolution queue
        if allow_probable:
            r.probable_only = True
            r.reasons.append("probable_match_research_no_identifier_operator_enabled")
        else:
            r.identifier_resolution_required = True
    else:
        if not ident_ok:
            r.identifier_resolution_required = True
        r.reasons.append("insufficient_source_identity")

    # never both
    if r.identity_ready:
        r.identifier_resolution_required = False
        r.probable_only = False
    return r


def audit_source_identity(store, run_id: Optional[str] = None, *, limit: int = 1_000_000) -> Dict[str, Any]:
    """Audit identifier / physical / pack coverage across local Costco records."""
    rows = store.list_source_products(run_id=run_id, limit=limit)
    total = len(rows)
    eligible = [r for r in rows if r.get("eligible_for_costco_non_kirkland_workflow")]
    upc = sum(1 for r in eligible if normalize_upc(r.get("upc")))
    ean = sum(1 for r in eligible if normalize_upc(r.get("ean")))
    gtin = sum(1 for r in eligible if normalize_upc(r.get("gtin")))
    mpn = sum(1 for r in eligible if _clean(r.get("manufacturer_part_number")))
    any_ident = sum(1 for r in eligible if has_strong_identifier(r))
    weight = sum(1 for r in eligible if _clean(r.get("size_or_weight_raw")) or _clean(r.get("shipping_weight")))
    pack = sum(1 for r in eligible if _pack_known(r, None))

    ready = probable = resolution = 0
    for r in eligible:
        res = assess_identity_readiness(r, None)
        if res.identity_ready:
            ready += 1
        elif res.probable_only:
            probable += 1
        elif res.identifier_resolution_required:
            resolution += 1

    return {
        "generated_at": _now(),
        "run_id": run_id,
        "total_source_records": total,
        "eligible_records": len(eligible),
        "identifier_coverage": {"upc": upc, "ean": ean, "gtin": gtin, "mpn": mpn,
                                "any_strong_identifier": any_ident},
        "weight_coverage": weight,
        "dimensions_coverage": 0,  # dimensions not present in local source
        "pack_coverage": pack,
        "identity_ready_count": ready,
        "probable_match_only_count": probable,
        "identifier_resolution_required_count": resolution,
    }
