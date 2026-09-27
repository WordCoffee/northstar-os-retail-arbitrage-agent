"""Costco Non-Kirkland inventory audit (offline, non-destructive).

Computes exact strict/provisional eligibility counts from the locally stored
Costco source products in the canonical database. No network, no source mutation.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .store import PipelineStore

_LB_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(lb|lbs|pound|pounds)\b", re.IGNORECASE)
_OZ_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(oz|ounce|ounces)\b", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_weight_lb(size_text: Optional[str]) -> Optional[float]:
    """Parse weight in pounds from a size/weight string. None if unknown.

    oz is converted to lb. Never guesses.
    """
    if not size_text:
        return None
    s = str(size_text)
    m = _LB_RE.search(s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    m = _OZ_RE.search(s)
    if m:
        try:
            return round(float(m.group(1)) / 16.0, 4)
        except ValueError:
            return None
    return None


def _has_identifier(row: Dict[str, Any]) -> bool:
    return any(row.get(k) for k in ("upc", "ean", "gtin", "manufacturer_part_number"))


def _has_pack(row: Dict[str, Any]) -> bool:
    return row.get("normalized_unit_count") is not None or bool(row.get("costco_pack_raw"))


def audit(store: Optional[PipelineStore] = None, *, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Compute the full Costco inventory audit."""
    store = store or PipelineStore()
    rows = store.list_source_products(run_id=run_id, limit=1_000_000)

    total = len(rows)
    # Dedupe rule: (upc if present) else (costco_item_number) else (title_normalized).
    seen = set()
    unique = 0
    for r in rows:
        key = r.get("upc") or r.get("costco_item_number") or r.get("title_normalized") or r.get("id")
        if key not in seen:
            seen.add(key)
            unique += 1

    kirkland = sum(1 for r in rows if r.get("exclusion_reason") == "kirkland_signature_out_of_scope")
    disallowed = sum(1 for r in rows if r.get("exclusion_reason") == "disallowed_product_class")
    remaining = sum(1 for r in rows if not r.get("exclusion_reason"))
    eligible_rows = [r for r in rows if r.get("eligible_for_costco_non_kirkland_workflow")]

    known_brand = sum(1 for r in eligible_rows if r.get("brand_normalized"))
    usable_cost = sum(1 for r in eligible_rows if r.get("costco_price") is not None)
    with_identifier = sum(1 for r in eligible_rows if _has_identifier(r))
    clear_pack = sum(1 for r in eligible_rows if _has_pack(r))

    confirmed_le3 = confirmed_gt3 = unknown_weight = 0
    for r in eligible_rows:
        w = parse_weight_lb(r.get("size_or_weight_raw"))
        if w is None:
            unknown_weight += 1
        elif w <= 3.0:
            confirmed_le3 += 1
        else:
            confirmed_gt3 += 1

    confirmed_size = sum(1 for r in eligible_rows if r.get("size_or_weight_raw"))
    unknown_size = len(eligible_rows) - confirmed_size

    split_review = sum(1 for r in eligible_rows
                       if (r.get("normalized_unit_count") or 0) and (r.get("normalized_unit_count") or 0) > 1)

    missing_brand = sum(1 for r in eligible_rows if not r.get("brand_normalized"))
    missing_price = sum(1 for r in eligible_rows if r.get("costco_price") is None)
    missing_identity_pack = sum(1 for r in eligible_rows if not _has_pack(r))

    # Strict: passes every currently verifiable Costco-side requirement.
    strict = [
        r for r in eligible_rows
        if r.get("brand_normalized")
        and r.get("costco_price") is not None
        and _has_pack(r)
        and not r.get("manual_review_required")
        and parse_weight_lb(r.get("size_or_weight_raw")) is not None
        and parse_weight_lb(r.get("size_or_weight_raw")) <= 3.0
    ]
    # Provisional: promising but blocked by a missing/unknown required source field.
    provisional = [
        r for r in eligible_rows
        if r.get("brand_normalized")
        and r.get("costco_price") is not None
        and _has_pack(r)
        and r not in strict
    ]

    # Provider-linked / requiring research.
    try:
        snapshots = store.list_market_snapshots(limit=1_000_000)
        linked_asins = {s.get("asin") for s in snapshots if s.get("asin")}
    except Exception:
        linked_asins = set()
    provider_linked = sum(1 for r in eligible_rows if r.get("upc") in linked_asins)

    return {
        "generated_at": _now(),
        "run_id": run_id,
        "total_source_records": total,
        "unique_records": unique,
        "kirkland_excluded": kirkland,
        "disallowed_excluded": disallowed,
        "remaining_non_kirkland_non_disallowed": remaining,
        "known_brand_records": known_brand,
        "usable_cost_records": usable_cost,
        "upc_ean_gtin_mpn_records": with_identifier,
        "clear_pack_unit_records": clear_pack,
        "confirmed_le_3lb": confirmed_le3,
        "confirmed_gt_3lb": confirmed_gt3,
        "unknown_weight": unknown_weight,
        "confirmed_acceptable_size": confirmed_size,
        "unknown_size_dimensions": unknown_size,
        "multipack_split_review_records": split_review,
        "strict_costco_side_eligible": len(strict),
        "provisional_eligible": len(provisional),
        "missing_brand_review": missing_brand,
        "missing_source_price_review": missing_price,
        "missing_identity_pack_review": missing_identity_pack,
        "records_already_provider_linked": provider_linked,
        "records_requiring_provider_research": len(eligible_rows) - provider_linked,
    }


def render_audit_markdown(a: Dict[str, Any]) -> str:
    lines = [
        "# AutothinK ChromeControl — Costco Inventory Audit",
        "",
        f"- Generated: {a.get('generated_at')}",
        f"- Total local Costco records: {a.get('total_source_records')}",
        f"- Unique records (dedupe: upc|item_number|title): {a.get('unique_records')}",
        f"- Kirkland excluded: {a.get('kirkland_excluded')}",
        f"- Other disallowed excluded: {a.get('disallowed_excluded')}",
        f"- Remaining (non-Kirkland / non-disallowed): {a.get('remaining_non_kirkland_non_disallowed')}",
        "",
        "## Source-side completeness",
        f"- Known brand: {a.get('known_brand_records')}",
        f"- Usable source cost: {a.get('usable_cost_records')}",
        f"- UPC/EAN/GTIN/MPN present: {a.get('upc_ean_gtin_mpn_records')}",
        f"- Clear pack/unit: {a.get('clear_pack_unit_records')}",
        f"- Confirmed <= 3 lb: {a.get('confirmed_le_3lb')}",
        f"- Confirmed > 3 lb: {a.get('confirmed_gt_3lb')}",
        f"- Unknown weight: {a.get('unknown_weight')}",
        f"- Confirmed size present: {a.get('confirmed_acceptable_size')}",
        f"- Unknown size/dimensions: {a.get('unknown_size_dimensions')}",
        f"- Multipack split-review candidates: {a.get('multipack_split_review_records')}",
        "",
        "## Eligibility",
        f"- **Strict Costco-side eligible: {a.get('strict_costco_side_eligible')}**",
        f"- **Provisional eligible (pending source data): {a.get('provisional_eligible')}**",
        f"- Missing brand review: {a.get('missing_brand_review')}",
        f"- Missing source price review: {a.get('missing_source_price_review')}",
        f"- Missing identity/pack review: {a.get('missing_identity_pack_review')}",
        f"- Already provider-linked: {a.get('records_already_provider_linked')}",
        f"- Requiring provider research: {a.get('records_requiring_provider_research')}",
        "",
        "_Not purchase authorized. Offline audit only; no live provider calls._",
    ]
    return "\n".join(lines)
