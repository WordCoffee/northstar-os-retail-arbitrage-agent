"""Bright Data Costco identity-enrichment adapter (approval-gated, offline by default).

Reuses the Northstar live-gate / env-flag / approval discipline. This module
NEVER makes a live Bright Data call during implementation, tests, imports, or
ordinary CLI use. Live mode fails closed unless EVERY gate is satisfied.

Modes:
  disabled            (default)
  fixture             (local fixture data only)
  dry_run_manifest    (build a proposed sample manifest; zero calls)
  approved_live_run   (gated; requires all approvals)
  imported_snapshot   (import an operator-provided normalized snapshot)
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from env_flags import env_flag

from .enrichment import (
    ENRICHMENT_CONTRACT_FIELDS,
    has_strong_identifier,
    normalize_upc,
    identifier_kind,
    assess_identity_readiness,
    _clean,
)

PROVIDER = "brightdata"
GATE_ENRICHMENT = "NORTHSTAR_ENRICHMENT_APPROVED"
GATE_BRIGHTDATA = "NORTHSTAR_BRIGHT_DATA_ENABLED"

CAPTURE_STATUSES = (
    "captured", "field_not_returned", "field_not_supported", "parse_error",
    "stale", "identifier_conflict", "insufficient_source_identity",
    "provider_unavailable", "provider_not_configured",
)

# Fields requested from the provider (marketing-claimed, must be validated).
REQUESTED_FIELDS = (
    "costco_item_number", "brand", "manufacturer", "title", "description",
    "category_path", "upc", "ean", "gtin", "mpn", "manufacturer_model",
    "net_weight", "shipping_weight", "package_length", "package_width",
    "package_height", "outer_pack_count", "inner_unit_count", "unit_count",
    "unit_measure",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_mode() -> str:
    """Resolve the adapter mode from env (default disabled)."""
    if env_flag(GATE_BRIGHTDATA) and env_flag(GATE_ENRICHMENT):
        return "approved_live_run"
    return "disabled"


# ---------------------------------------------------------------------------
# Dry-run sample manifest
# ---------------------------------------------------------------------------

def select_sample(store, run_id: Optional[str] = None, *, max_items: int = 25) -> List[Dict[str, Any]]:
    """Select up to max_items eligible records for a schema-validation sample."""
    rows = store.list_source_products(run_id=run_id, limit=1_000_000)
    picks = []
    for r in rows:
        if not r.get("eligible_for_costco_non_kirkland_workflow"):
            continue
        if not (r.get("brand_normalized") or r.get("brand_raw")):
            continue
        if r.get("costco_price") is None:
            continue
        if not (r.get("costco_item_number") or r.get("source_record_id")):
            continue
        picks.append(r)
    # prefer records lacking identifiers (these are the ones needing enrichment)
    picks.sort(key=lambda r: (has_strong_identifier(r), r.get("costco_price") or 0))
    return picks[:max_items]


def plan_enrichment_manifest(store, run_id: Optional[str] = None, *, max_items: int = 25,
                             dry_run: bool = True) -> Dict[str, Any]:
    """Build a proposed sample manifest. ZERO network calls."""
    sample = select_sample(store, run_id, max_items=max_items)
    items = []
    for r in sample:
        split_review = bool((r.get("normalized_unit_count") or 0) > 1)
        items.append({
            "source_product_id": r.get("id"),
            "costco_item_number": r.get("costco_item_number") or r.get("source_record_id"),
            "brand": r.get("brand_raw"),
            "title": r.get("title_raw"),
            "pack": r.get("costco_pack_raw"),
            "costco_price": r.get("costco_price"),
            "existing_identifiers": {
                "upc": r.get("upc"), "ean": r.get("ean"), "gtin": r.get("gtin"),
                "mpn": r.get("manufacturer_part_number"),
            },
            "missing_identity_fields": [
                f for f in ("upc_ean_gtin_or_mpn", "weight", "dimensions")
                if (f == "upc_ean_gtin_or_mpn" and not has_strong_identifier(r))
                or (f == "weight" and not (_clean(r.get("size_or_weight_raw")) or _clean(r.get("shipping_weight"))))
                or (f == "dimensions" and True)  # local source has no dimensions
            ],
            "split_review": split_review,
            "auto_identity_approval_eligible": not split_review,
        })
    return {
        "provider": PROVIDER,
        "mode": "dry_run_manifest",
        "dry_run": dry_run,
        "created_at": _now(),
        "sample_size": len(items),
        "requested_fields": list(REQUESTED_FIELDS),
        "existing_local_identifier_coverage": {
            "with_upc": sum(1 for i in items if normalize_upc(i["existing_identifiers"]["upc"])),
            "with_mpn": sum(1 for i in items if i["existing_identifiers"]["mpn"]),
        },
        "known_brightdata_field_availability": "unknown — must be validated on the approved live sample",
        "approved_provider_configuration_status": (
            "configured" if (os.getenv("BRIGHTDATA_UNLOCKER_API_KEY") or os.getenv("BRIGHTDATA_API_KEY")) else "unavailable"
        ),
        "network_calls_made": 0,
        "items": items,
    }


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_schema(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Coverage report for a provider sample/snapshot. No network."""
    total = len(records)
    def cov(field):
        return sum(1 for r in records if _clean(r.get(field)))
    report = {
        "records": total,
        "coverage": {},
        "identifier_coverage": {},
        "physical_coverage": {},
    }
    for f in REQUESTED_FIELDS:
        report["coverage"][f] = cov(f)
    for f in ("upc", "ean", "gtin", "mpn"):
        report["identifier_coverage"][f] = cov(f)
    report["identifier_coverage"]["any_strong_identifier"] = sum(
        1 for r in records if has_strong_identifier(r))
    for f in ("net_weight", "shipping_weight", "package_length", "package_width", "package_height"):
        report["physical_coverage"][f] = cov(f)
    report["mappable_to_item_number"] = sum(
        1 for r in records if _clean(r.get("costco_item_number")))
    return report


# ---------------------------------------------------------------------------
# Run (fail-closed)
# ---------------------------------------------------------------------------

def run_enrichment(manifest: Dict[str, Any], *, approved: bool = False, max_items: Optional[int] = None,
                   spend_cap: Optional[float] = None, source_id: Optional[str] = None,
                   manifest_id: Optional[str] = None) -> Dict[str, Any]:
    """Fail-closed live runner. No call is made unless every gate is satisfied."""
    gates = {
        "approved_flag": bool(approved),
        "env_enrichment_approved": env_flag(GATE_ENRICHMENT),
        "env_brightdata_enabled": env_flag(GATE_BRIGHTDATA),
        "max_items_set": isinstance(max_items, int) and max_items > 0,
        "spend_cap_set": spend_cap is not None and spend_cap >= 0,
        "manifest_id_set": bool(manifest_id),
        "source_id_set": bool(source_id),
    }
    missing = [k for k, v in gates.items() if not v]
    if missing:
        return {
            "provider": PROVIDER,
            "result_status": "requires_explicit_approval",
            "missing_gates": missing,
            "network_calls_made": 0,
            "no_live_calls": True,
            "how_to_approve": (
                "Pass --approved with NORTHSTAR_ENRICHMENT_APPROVED=1 and "
                "NORTHSTAR_BRIGHT_DATA_ENABLED=1, --max-items N, --spend-cap X, "
                "an approved manifest id and a source/scraper id."
            ),
        }
    # All gates satisfied — but this build intentionally performs NO live call.
    return {
        "provider": PROVIDER,
        "result_status": "not_executed_offline_build",
        "detail": "All gates satisfied but this offline build does not perform live provider calls.",
        "network_calls_made": 0,
    }


# ---------------------------------------------------------------------------
# Import a normalized snapshot (idempotent)
# ---------------------------------------------------------------------------

def map_provider_record(raw: Dict[str, Any], *, provider_name: str = PROVIDER,
                        snapshot_sha256: Optional[str] = None,
                        provider_snapshot_id: Optional[str] = None) -> Dict[str, Any]:
    """Map a provider/enrichment record into the canonical enrichment contract."""
    upc = normalize_upc(raw.get("upc") or raw.get("upc_gtin_ean") or raw.get("UPC_GTIN_EAN"))
    ean = normalize_upc(raw.get("ean"))
    gtin = normalize_upc(raw.get("gtin"))
    mpn = _clean(raw.get("mpn") or raw.get("manufacturer_part_number"))
    kind = "upc" if upc else "ean" if ean else "gtin" if gtin else "mpn" if mpn else None
    value = upc or ean or gtin or mpn
    capture = {}
    rec = {
        "costco_item_number": _clean(raw.get("costco_item_number") or raw.get("returned_costco_item_id") or raw.get("requested_item_id")),
        "source_record_id": _clean(raw.get("source_record_id")),
        "provider_name": provider_name,
        "provider_snapshot_id": provider_snapshot_id,
        "snapshot_sha256": snapshot_sha256,
        "brand": _clean(raw.get("brand")),
        "manufacturer": _clean(raw.get("manufacturer")),
        "title": _clean(raw.get("title") or raw.get("exact_title")),
        "description": _clean(raw.get("description")),
        "category_path": _clean(raw.get("category_path") or raw.get("category")),
        "upc": upc, "ean": ean, "gtin": gtin, "mpn": mpn,
        "manufacturer_model": _clean(raw.get("manufacturer_model") or raw.get("model")),
        "identifier_type": kind, "identifier_value": value,
        "identifier_source": provider_name if value else None,
        "identifier_capture_status": "captured" if value else "field_not_returned",
        "net_weight": _clean(raw.get("net_weight")),
        "shipping_weight": _clean(raw.get("shipping_weight") or raw.get("weight") or raw.get("size_or_weight")),
        "package_length": _clean(raw.get("package_length")),
        "package_width": _clean(raw.get("package_width")),
        "package_height": _clean(raw.get("package_height")),
        "outer_pack_count": _clean(raw.get("outer_pack_count") or raw.get("quantity_or_pack")),
        "inner_unit_count": _clean(raw.get("inner_unit_count")),
        "unit_count": _clean(raw.get("unit_count")),
        "unit_measure": _clean(raw.get("unit_measure") or raw.get("size_or_weight")),
        "split_pack_status": _clean(raw.get("split_pack_status")) or "unknown",
        "captured_at": _clean(raw.get("captured_at")) or _now(),
        "ingested_at": _now(),
        "freshness_status": _clean(raw.get("freshness_status")) or "unknown",
    }
    for f in REQUESTED_FIELDS:
        capture[f] = "captured" if rec.get(f) is not None else "field_not_returned"
    rec["field_capture_status"] = capture
    return rec


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Offline readiness / cost PREFLIGHT (zero network calls)
# ---------------------------------------------------------------------------

# Env var NAMES only — values are never read, printed, or used here.
SOURCE_ID_ENVS = (
    "NORTHSTAR_BRIGHTDATA_SOURCE_ID",
    "BRIGHTDATA_COSTCO_SOURCE_ID",
    "BRIGHTDATA_UNLOCKER_ZONE",
)
CREDENTIAL_ENVS = (
    "BRIGHTDATA_UNLOCKER_API_KEY",
    "BRIGHTDATA_API_KEY",
)

FIELD_PURPOSE_MAP = {
    "identifier_resolution": ["upc", "ean", "gtin", "mpn", "brand"],
    "weight_size_validation": ["net_weight", "shipping_weight", "package_length", "package_width", "package_height"],
    "pack_validation": ["outer_pack_count", "inner_unit_count", "unit_count", "unit_measure"],
    "exact_provider_match": ["brand", "upc", "ean", "gtin", "mpn", "title"],
    "economics": ["costco_price", "shipping_weight", "unit_count"],
}

OPTIONAL_FIELDS = ("description", "category_path", "manufacturer", "manufacturer_model",
                   "availability", "image_reference", "specification_reference",
                   "observed_at", "source_url")

REQUESTED_FIELDS_FULL = (
    "costco_item_number", "brand", "title", "description", "category_path",
    "costco_price", "availability", "upc", "ean", "gtin", "mpn",
    "manufacturer_model", "outer_pack_count", "inner_pack_count", "unit_count",
    "unit_measure", "net_weight", "shipping_weight", "package_length",
    "package_width", "package_height", "specification_reference",
    "image_reference", "observed_at", "source_url",
)

CANONICAL_EXPECTED_MAPPING = {
    "costco_item_number": "costco_identity_enrichment.costco_item_number",
    "brand": "costco_identity_enrichment.brand",
    "title": "costco_identity_enrichment.title",
    "description": "costco_identity_enrichment.description",
    "category_path": "costco_identity_enrichment.category_path",
    "upc": "costco_identity_enrichment.upc",
    "ean": "costco_identity_enrichment.ean",
    "gtin": "costco_identity_enrichment.gtin",
    "mpn": "costco_identity_enrichment.mpn",
    "manufacturer_model": "costco_identity_enrichment.manufacturer_model",
    "outer_pack_count": "costco_identity_enrichment.outer_pack_count",
    "inner_unit_count": "costco_identity_enrichment.inner_unit_count",
    "unit_count": "costco_identity_enrichment.unit_count",
    "unit_measure": "costco_identity_enrichment.unit_measure",
    "net_weight": "costco_identity_enrichment.net_weight",
    "shipping_weight": "costco_identity_enrichment.shipping_weight",
    "package_length": "costco_identity_enrichment.package_length",
    "package_width": "costco_identity_enrichment.package_width",
    "package_height": "costco_identity_enrichment.package_height",
}


def _find_local_brightdata_fixtures() -> List[str]:
    """Look for any existing Bright Data / Costco enrichment fixture/history."""
    found = []
    roots = [os.path.join("data", "costco-discovery-runs")]
    try:
        for root in roots:
            if os.path.isdir(root):
                for dirpath, _dirs, files in os.walk(root):
                    for f in files:
                        if "bright" in f.lower() or "normalized" in dirpath.lower():
                            found.append(os.path.join(dirpath, f))
    except OSError:
        pass
    return found[:20]


def preflight(manifest: Optional[Dict[str, Any]] = None, *, manifest_path: Optional[str] = None,
              env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Offline Bright Data readiness/cost preflight. ZERO network calls.

    Never reads or prints credential values; only env var NAMES and set/unset.
    """
    env = env if env is not None else os.environ
    if manifest is None and manifest_path:
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
        except (OSError, ValueError):
            manifest = None
    manifest = manifest or {}

    source_id_set = {name: bool(env.get(name)) for name in SOURCE_ID_ENVS}
    cred_set = {name: bool(env.get(name)) for name in CREDENTIAL_ENVS}
    configured_source = any(source_id_set.values())

    gates = {
        "approved_flag": False,  # a flag is only set by the live runner
        "env_enrichment_approved": env_flag(GATE_ENRICHMENT, default=False),
        "env_brightdata_enabled": env_flag(GATE_BRIGHTDATA, default=False),
        "source_id_configured": configured_source,
        "max_items_set": bool(manifest.get("sample_size")),
        "spend_cap_set": False,
        "manifest_id_present": bool(manifest_path or manifest.get("manifest_id")),
    }
    unsatisfied = [k for k, v in gates.items() if not v]

    items = manifest.get("items", [])
    sample_ids = [i.get("costco_item_number") for i in items]

    if not configured_source:
        provider_status = "provider_not_configured"
    else:
        provider_status = "configured_source_id_present_unverified"

    return {
        "provider": PROVIDER,
        "result_status": provider_status,
        "enabled": env_flag(GATE_BRIGHTDATA, default=False),
        "source_id_configured": configured_source,
        "source_id_env_names_checked": list(SOURCE_ID_ENVS),
        "source_id_env_set": source_id_set,
        "credential_env_names_checked": list(CREDENTIAL_ENVS),
        "credential_env_set": cred_set,
        "credentials_printed": False,
        "approval_gates": gates,
        "unsatisfied_gates": unsatisfied,
        "sample_size": manifest.get("sample_size", 0),
        "sample_candidate_ids": sample_ids,
        "requested_fields": list(REQUESTED_FIELDS_FULL),
        "canonical_expected_mapping": dict(CANONICAL_EXPECTED_MAPPING),
        "mandatory_fields_by_purpose": dict(FIELD_PURPOSE_MAP),
        "optional_fields": list(OPTIONAL_FIELDS),
        "unknown_untested_fields": list(REQUESTED_FIELDS_FULL),
        "local_fixtures_found": _find_local_brightdata_fixtures(),
        "local_fixtures_note": "Historical fixtures are NOT current live evidence.",
        "known_cost": "cost unknown; operator must confirm in Bright Data account",
        "spend_cap": None,
        "network_calls_made": 0,
    }


def render_preflight_markdown(rep: Dict[str, Any]) -> str:
    lines = [
        "# Bright Data Costco Enrichment — Preflight Report",
        "",
        f"- Result: **{rep['result_status']}**",
        f"- Enabled: {rep['enabled']}",
        f"- Source/scraper id configured: {rep['source_id_configured']}",
        f"- Known cost: {rep['known_cost']}",
        f"- Network calls made: {rep['network_calls_made']}",
        "",
        "## Unsatisfied approval gates",
    ]
    lines += [f"- {g}" for g in rep["unsatisfied_gates"]] or ["- (none)"]
    lines += [
        "",
        f"## Sample ({rep['sample_size']} items)",
        ", ".join(str(x) for x in rep["sample_candidate_ids"]) or "(none)",
        "",
        "## Mandatory fields by purpose",
    ]
    for purpose, fields in rep["mandatory_fields_by_purpose"].items():
        lines.append(f"- **{purpose}**: {', '.join(fields)}")
    lines += [
        "",
        "## Unknown / untested fields",
        ", ".join(rep["unknown_untested_fields"]),
        "",
        "## Canonical field mappings (expected)",
    ]
    for k, v in rep["canonical_expected_mapping"].items():
        lines.append(f"- {k} -> {v}")
    lines += [
        "",
        f"## Local fixtures found: {len(rep['local_fixtures_found'])} (historical; not live evidence)",
    ]
    return "\n".join(lines)


def import_snapshot(path: str, store, *, provider_name: str = PROVIDER,
                    dry_run: bool = False) -> Dict[str, Any]:
    """Import a normalized enrichment snapshot (idempotent by file hash)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    records = data.get("records", data if isinstance(data, list) else [])
    sha = sha256_file(path)
    if store.has_enrichment_snapshot(sha):
        return {"provider": provider_name, "result_status": "duplicate", "records": len(records),
                "snapshot_sha256": sha, "network_calls_made": 0}
    imported = 0
    for raw in records:
        rec = map_provider_record(raw, provider_name=provider_name, snapshot_sha256=sha,
                                  provider_snapshot_id=data.get("provider_snapshot_id"))
        if not dry_run:
            store.upsert_enrichment_record(rec)
        imported += 1
    return {"provider": provider_name, "result_status": "imported", "records": imported,
            "snapshot_sha256": sha, "dry_run": dry_run, "network_calls_made": 0}
