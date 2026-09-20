"""B7 tests — Golden Goose entitlement mapping (references the plan catalog)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder import gg_entitlements as ge  # noqa: E402


def test_mapping_references_only_catalog_plan_ids():
    catalog = ge.load_catalog()
    mapping = ge.load_gg_entitlements()
    plan_ids = set(ge.catalog_plan_ids(catalog))
    assert set(mapping["plans"]).issubset(plan_ids)
    # canonical catalog plan ids are all present
    assert {"foundation", "scout", "mover", "autothink"} <= set(mapping["plans"])


def test_mapping_does_not_duplicate_catalog_data():
    # validator raises if name/price/tier/gates leak into the mapping
    ge.validate_gg_entitlements()  # real files conform


def test_unknown_plan_id_fails_closed():
    with pytest.raises(KeyError):
        ge.gg_entitlements_for_plan("enterprise_plus")


def test_resolution_shape_and_foundation_none():
    ent = ge.gg_entitlements_for_plan("foundation")
    assert ent == {"plan": "foundation", "categories": [], "exports": []}


def test_entitlements_progress_monotonically():
    scout = set(ge.gg_entitlements_for_plan("scout")["categories"])
    mover = set(ge.gg_entitlements_for_plan("mover")["categories"])
    autothink = set(ge.gg_entitlements_for_plan("autothink")["categories"])
    assert scout < mover < autothink
    # autothink unlocks every canonical category
    mapping = ge.load_gg_entitlements()
    assert autothink == set(mapping["canonical_categories"])


def test_export_entitlements_progress():
    scout = set(ge.gg_entitlements_for_plan("scout")["exports"])
    mover = set(ge.gg_entitlements_for_plan("mover")["exports"])
    autothink = set(ge.gg_entitlements_for_plan("autothink")["exports"])
    assert scout < mover <= autothink
    assert "export_manifest_json" in autothink


def test_categories_and_exports_are_canonical():
    mapping = ge.load_gg_entitlements()
    cats = set(mapping["canonical_categories"])
    exps = set(mapping["export_types"])
    for pid in mapping["plans"]:
        ent = ge.gg_entitlements_for_plan(pid)
        assert set(ent["categories"]) <= cats
        assert set(ent["exports"]) <= exps


def test_plan_entitles_helpers():
    assert ge.plan_entitles_category("autothink", "pet") is True
    assert ge.plan_entitles_category("foundation", "pet") is False
    assert ge.plan_entitles_export("autothink", "opportunities_csv") is True
    assert ge.plan_entitles_export("scout", "opportunities_csv") is False


def test_validator_rejects_duplicated_catalog_fields():
    from agents.golden_goose_finder.gg_entitlements import EntitlementConfigError
    catalog = ge.load_catalog()
    bad = ge.load_gg_entitlements()
    bad["plans"]["scout"]["price"] = 29  # duplicate catalog data -> must fail
    with pytest.raises(EntitlementConfigError):
        ge.validate_gg_entitlements(catalog, bad)


def test_validator_rejects_unknown_category():
    from agents.golden_goose_finder.gg_entitlements import EntitlementConfigError
    catalog = ge.load_catalog()
    bad = ge.load_gg_entitlements()
    bad["plans"]["scout"]["categories"] = ["not_a_category"]
    with pytest.raises(EntitlementConfigError):
        ge.validate_gg_entitlements(catalog, bad)