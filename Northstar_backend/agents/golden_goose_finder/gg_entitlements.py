"""Golden Goose entitlement mapping (B7) — plan id -> GG categories/exports.

References `shared/subscription-plans.json` (plans/prices/gates — the single
source of truth) and `shared/gg-entitlements.json` (GG-specific categories and
exports keyed by plan id). This module NEVER duplicates catalog data: it only
resolves and validates.

Pure and offline: reads two local JSON files; no network, no provider calls.

Invariant (matching the catalog + constitution): a plan ENTITLES a category or
export; it never flips a live gate. Live execution still requires a fresh,
named operator approval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

# repo root = .../Northstar_backend/agents/golden_goose_finder/ -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = _REPO_ROOT / "shared" / "subscription-plans.json"
GG_ENTITLEMENTS_PATH = _REPO_ROOT / "shared" / "gg-entitlements.json"


class EntitlementConfigError(ValueError):
    """Raised when the GG entitlement mapping drifts from the catalog."""


def _read_json(path: Path, label: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise EntitlementConfigError("cannot read %s at %s: %s" % (label, path, exc)) from exc


def load_catalog(path: Path | None = None) -> dict:
    return _read_json(path or CATALOG_PATH, "subscription catalog")


def load_gg_entitlements(path: Path | None = None) -> dict:
    return _read_json(path or GG_ENTITLEMENTS_PATH, "gg entitlement mapping")


def catalog_plan_ids(catalog: dict | None = None) -> List[str]:
    catalog = catalog or load_catalog()
    return [p.get("id") for p in catalog.get("plans", []) if p.get("id")]


def validate_gg_entitlements(catalog: dict | None = None, mapping: dict | None = None) -> None:
    """Fail closed if the mapping references an unknown plan/category/export,
    or attempts to duplicate catalog data (names/prices/gates).

    Raises EntitlementConfigError on any breach.
    """
    catalog = catalog or load_catalog()
    mapping = mapping or load_gg_entitlements()

    plan_ids = set(catalog_plan_ids(catalog))
    mapping_plans = mapping.get("plans", {})
    if not isinstance(mapping_plans, dict) or not mapping_plans:
        raise EntitlementConfigError("gg-entitlements.json holds no plans map")

    unknown = [pid for pid in mapping_plans if pid not in plan_ids]
    if unknown:
        raise EntitlementConfigError(
            "gg-entitlements references unknown plan id(s): %s (known: %s)"
            % (unknown, sorted(plan_ids))
        )

    # No catalog duplication: the mapping may not carry name/price/gates.
    forbidden_keys = {"name", "price", "price_usd_month", "gates", "entitled_gates", "tier"}
    for pid, entry in mapping_plans.items():
        bad = forbidden_keys & set(entry)
        if bad:
            raise EntitlementConfigError(
                "gg-entitlements.%s duplicates catalog data: %s (reference the catalog instead)"
                % (pid, sorted(bad))
            )

    canonical_cats = set(mapping.get("canonical_categories", []))
    export_types = set(mapping.get("export_types", []))
    if not canonical_cats or not export_types:
        raise EntitlementConfigError("gg-entitlements must declare canonical_categories and export_types")

    for pid, entry in mapping_plans.items():
        bad_cats = [c for c in entry.get("categories", []) if c not in canonical_cats]
        bad_exps = [e for e in entry.get("exports", []) if e not in export_types]
        if bad_cats:
            raise EntitlementConfigError("gg-entitlements.%s unknown category(ies): %s" % (pid, bad_cats))
        if bad_exps:
            raise EntitlementConfigError("gg-entitlements.%s unknown export(s): %s" % (pid, bad_exps))


def gg_entitlements_for_plan(plan_id: str, *, catalog: dict | None = None,
                             mapping: dict | None = None) -> Dict[str, List[str]]:
    """Resolve a plan's GG categories + exports. Unknown plan ids fail closed."""
    catalog = catalog or load_catalog()
    mapping = mapping or load_gg_entitlements()
    validate_gg_entitlements(catalog, mapping)
    if plan_id not in catalog_plan_ids(catalog):
        raise KeyError("unknown plan id: %r" % (plan_id,))
    entry = mapping["plans"].get(plan_id, {})
    return {
        "plan": plan_id,
        "categories": list(entry.get("categories", [])),
        "exports": list(entry.get("exports", [])),
    }


def plan_entitles_category(plan_id: str, category: str) -> bool:
    return category in gg_entitlements_for_plan(plan_id)["categories"]


def plan_entitles_export(plan_id: str, export_type: str) -> bool:
    return export_type in gg_entitlements_for_plan(plan_id)["exports"]