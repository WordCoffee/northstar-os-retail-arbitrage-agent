"""Costco local record normalization -> canonical `costco_source_product`.

PURE / OFFLINE. Adapters over the real local source shapes found in the repo:
  * `data/costco-items.csv`              (item_name, costco_cost)
  * `data/costco-discovery-catalog.json` (rich: brand, pack, price, url, item_id)
  * `data/costco-product-detail.json`    (detail: upc_or_ean, pack_count, ...)

Canonical output fields are the union required by the pipeline contract.
No network access. Never classifies offline data as live.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .enums import EvidenceClass, FreshnessStatus, classify_freshness
from .kirkland_exclusion import evaluate_exclusion

_CURRENCY_DEFAULT = "USD"

# Normalized unit kinds we can derive from pack/size text.
_UNIT_KINDS = {
    "ct", "count", "pack", "roll", "rolls", "sheet", "sheets", "bag", "bags",
    "bar", "bars", "can", "cans", "bottle", "bottles", "ea", "piece", "pieces",
    "tablet", "tablets", "capsule", "capsules", "tab", "tabs", "pill", "pills",
    "oz", "fl oz", "floz", "lb", "lbs", "kg", "g", "mg", "ml", "l", "gal",
    "sq ft", "sqft",
}

_PACK_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ct|count|packs?|pk|rolls?|sheets?|bags?|bars?|cans?|bottles?|pieces?|ea|tablets?|tabs?|capsules?|pills?)", re.IGNORECASE)
_COUNT_SUFFIX_RE = re.compile(r"(\d+)\s*(?:-|\s)?(?:count|ct|pk)\b", re.IGNORECASE)
_MULTIPACK_RE = re.compile(r"(\d+)\s*-?\s*pack\b", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _t(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def normalize_brand(brand: Optional[Any]) -> Optional[str]:
    """Normalize a brand string to a stable lowercase identifier.

    Removes legal suffixes, "Inc.", "LLC", "The", whitespace, punctuation.
    """
    if brand is None:
        return None
    s = _t(brand).lower()
    for suffix in (", inc", " inc", ", llc", " llc", " corporation", " co.", " company", " inc.", ", inc.", " trademarks"):
        s = s.replace(suffix, "")
    s = re.sub(r"['\u2019]", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = " ".join(s.split())
    if not s or s in ("the", "generic", "unknown", "n/a", "na", "-"):
        return None
    return s


def normalize_title(title: Optional[Any]) -> Optional[str]:
    if title is None:
        return None
    s = _t(title).lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def _normalized_unit_count_and_kind(pack_raw: Optional[Any], size_raw: Optional[Any]) -> tuple:
    """Return (normalized_unit_count, normalized_unit_kind) best-effort.

    Never guesses: returns (None, None) when the pack text is not parseable.
    """
    pack_text = _t(pack_raw)
    if not pack_text:
        return (None, None)

    m = _PACK_RE.search(pack_text)
    if m:
        count = float(m.group(1))
        kind = m.group(2).lower().rstrip("s")
        if kind == "count":
            kind = "ct"
        if kind == "pk":
            kind = "pack"
        return (count, kind)

    m = _COUNT_SUFFIX_RE.search(pack_text)
    if m:
        return (float(m.group(1)), "ct")

    m = _MULTIPACK_RE.search(pack_text)
    if m:
        return (float(m.group(1)), "pack")

    return (None, None)


def _costco_item_number(record: Dict[str, Any]) -> Optional[str]:
    for k in ("costco_item_id", "costco_item_number", "item_id", "costco_sku", "sku"):
        if record.get(k):
            return _t(record[k])
    return None


def _source_url(record: Dict[str, Any]) -> Optional[str]:
    for k in ("source_url", "product_url", "url_derived_source", "url"):
        if record.get(k):
            return _t(record[k])
    return None


def _upc_ean_gtin(record: Dict[str, Any]) -> tuple:
    upc = record.get("upc") or record.get("upc_or_ean") or None
    ean = record.get("ean") or None
    gtin = record.get("gtin") or None
    return (_t(upc) or None, _t(ean) or None, _t(gtin) or None)


def _price(record: Dict[str, Any]) -> Optional[float]:
    for k in ("costco_price", "regular_price", "current_price", "listed_price", "costco_cost", "price"):
        v = record.get(k)
        if v is None or v == "":
            continue
        if isinstance(v, (int, float)):
            return float(v)
        s = _t(v).replace("$", "").replace(",", "").strip()
        try:
            return float(s)
        except ValueError:
            continue
    return None


def _availability(record: Dict[str, Any]) -> Optional[str]:
    for k in ("availability", "availability_status", "in_stock", "stock"):
        if record.get(k):
            return _t(record[k])
    return None


def _observed_at(record: Dict[str, Any]) -> Optional[str]:
    for k in ("observed_at", "fetched_at", "captured_at", "requested_at", "imported_at"):
        if record.get(k):
            return _t(record[k])
    return None


def _source_name_for(file_path: str) -> str:
    if "costco-items.csv" in file_path:
        return "costco_items_csv"
    if "costco-discovery-catalog.json" in file_path:
        return "costco_discovery_catalog"
    if "costco-product-detail.json" in file_path:
        return "costco_product_detail"
    if "costco-api-catalog.json" in file_path:
        return "costco_api_catalog"
    if "costco-amazon-mapping.json" in file_path:
        return "costco_amazon_mapping"
    return "costco_local_source"


def normalize_costco_record(raw: Dict[str, Any], *,
                            source_file: Optional[str] = None,
                            source_record_id: Optional[str] = None,
                            evidence_class: str = EvidenceClass.CACHED_SOURCE_SNAPSHOT.value,
                            now: object = None) -> Dict[str, Any]:
    """Normalize one raw local Costco record into the canonical shape.

    Returns a dict with ALL canonical fields populated (None where unknown).
    The returned record is NOT yet exclusion-marked; call `apply_exclusion`
    (from pipeline) or `evaluate_exclusion` to set the exclusion fields.
    """
    raw = raw or {}
    title_raw = _t(raw.get("title_raw") or raw.get("item_name") or raw.get("name") or raw.get("product_name") or raw.get("exact_title") or "")
    brand_raw = _t(raw.get("brand_raw") or raw.get("brand") or "")
    upc, ean, gtin = _upc_ean_gtin(raw)
    pack_raw = _t(raw.get("costco_pack_raw") or raw.get("pack_size") or raw.get("quantity_or_pack") or raw.get("pack_count") or "")
    size_raw = _t(raw.get("size_or_weight_raw") or raw.get("size_or_weight") or raw.get("net_weight") or raw.get("unit_of_measure") or "")
    unit_count, unit_kind = _normalized_unit_count_and_kind(pack_raw, size_raw)
    observed_at = _observed_at(raw) or _now()
    costco_item_number = _costco_item_number(raw)
    source_url = _source_url(raw)
    source_name = raw.get("source_name") or _source_name_for(source_file or "")

    record = {
        "id": raw.get("id") or None,
        "source_name": source_name,
        "source_record_id": source_record_id or costco_item_number or None,
        "source_file_or_dataset": source_file,
        "source_url": source_url,
        "costco_item_number": costco_item_number,
        "title_raw": title_raw or None,
        "title_normalized": normalize_title(title_raw),
        "brand_raw": brand_raw or None,
        "brand_normalized": normalize_brand(brand_raw),
        "upc": upc,
        "ean": ean,
        "gtin": gtin,
        "manufacturer_part_number": _t(raw.get("manufacturer_part_number") or raw.get("model_number") or raw.get("mpn") or None) or None,
        "costco_price": _price(raw),
        "currency": raw.get("currency") or _CURRENCY_DEFAULT,
        "costco_pack_raw": pack_raw or None,
        "normalized_unit_count": unit_count,
        "normalized_unit_kind": unit_kind,
        "size_or_weight_raw": size_raw or None,
        "availability_status": _availability(raw) or None,
        "warehouse_or_location": _t(raw.get("warehouse_or_location") or raw.get("warehouse_or_zip") or None) or None,
        "observed_at": observed_at,
        "imported_at": _now(),
        "freshness_status": classify_freshness(observed_at, now=now),
        "evidence_class": evidence_class,
        "identity_status": raw.get("identity_status") or "unresolved",
        # Exclusion fields set by apply_exclusion()
        "exclusion_reason": None,
        "manual_review_required": bool(raw.get("manual_review_required")),
        "eligible_for_costco_non_kirkland_workflow": True,
    }
    return record


def apply_exclusion(record: Dict[str, Any]) -> Dict[str, Any]:
    """Mark (never delete) a normalized record with its Kirkland exclusion verdict."""
    res = evaluate_exclusion(record)
    return res.to_record(record)


def load_discovery_catalog(path: str) -> list:
    """Load raw records from the append-only discovery catalog JSON."""
    import json
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    records = data.get("records", data if isinstance(data, list) else [])
    return list(records)


def load_csv_records(path: str) -> list:
    """Load raw rows from a Costco CSV (item_name, costco_cost)."""
    import csv
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row:
                rows.append(dict(row))
    return rows


def load_json_records(path: str) -> list:
    """Load raw records from a plain JSON list of objects."""
    import json
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return list(data["records"])
    return []