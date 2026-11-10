"""Tests for Costco identity enrichment + Bright Data adapter (fixture-only, zero network)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import test_network_guard  # noqa: F401

from costco_non_kirkland.enrichment import (
    assess_identity_readiness,
    audit_source_identity,
    has_strong_identifier,
    normalize_upc,
    identifier_kind,
)
from costco_non_kirkland.brightdata_costco_enrichment import (
    plan_enrichment_manifest,
    validate_schema,
    run_enrichment,
    import_snapshot,
    map_provider_record,
    current_mode,
)
from costco_non_kirkland.requirements_profile import build_requirements_profile
from .fixtures import source_fixture


def _isolated_store():
    import data_layer
    tmp = Path(tempfile.mkdtemp(prefix="cnk-enr-"))
    data_layer._SQLITE_PATH = tmp / "northstar.db"
    data_layer._db_instance = None
    from costco_non_kirkland.store import PipelineStore
    return PipelineStore()


class TriStateRuleTests(unittest.TestCase):
    def test_item_number_not_treated_as_upc(self):
        r = source_fixture(id="a", upc=None, manufacturer_part_number=None)
        self.assertFalse(has_strong_identifier(r))
        self.assertIsNone(identifier_kind(r))
        # item number present but is NOT an identifier
        self.assertTrue(r.get("costco_item_number"))
        self.assertFalse(has_strong_identifier({**r, "costco_item_number": "2700048"}))

    def test_unknown_upc_stays_unknown(self):
        self.assertIsNone(normalize_upc(None))
        self.assertIsNone(normalize_upc(""))
        self.assertIsNone(normalize_upc("N/A"))
        self.assertEqual(normalize_upc("799488123456"), "799488123456")

    def test_unknown_weight_not_le_3lb(self):
        r = source_fixture(id="b", size_or_weight_raw=None, upc="799488123456")
        res = assess_identity_readiness(r, None)
        self.assertFalse(res.identity_ready)
        self.assertIn("weight", res.missing_physical_fields)

    def test_unknown_dimensions_not_standard_size(self):
        r = source_fixture(id="c", size_or_weight_raw="1 lb", upc="799488123456")
        res = assess_identity_readiness(r, None)
        self.assertIn("dimensions", res.missing_physical_fields)

    def test_unknown_split_not_approved(self):
        r = source_fixture(id="d")
        res = assess_identity_readiness(r, None)
        self.assertEqual(res.split_pack_status, "unknown")


class ReadinessTests(unittest.TestCase):
    def test_identifier_present_physical_pending(self):
        r = source_fixture(id="e", upc="799488123456", size_or_weight_raw="1 lb")
        res = assess_identity_readiness(r, None)
        self.assertTrue(res.identifier_kind == "upc")
        self.assertFalse(res.identity_ready)
        self.assertFalse(res.identifier_resolution_required)
        self.assertIn("identity_present_physical_pending_enrichment", res.reasons)

    def test_identity_ready_with_full_enrichment(self):
        r = source_fixture(id="f", upc="799488123456", size_or_weight_raw="1 lb")
        enrichment = {"shipping_weight": "1 lb", "package_length": "10", "package_width": "8", "package_height": "4"}
        res = assess_identity_readiness(r, enrichment)
        self.assertTrue(res.identity_ready)
        self.assertFalse(res.identifier_resolution_required)

    def test_mpn_brand_creates_identifier(self):
        r = source_fixture(id="g", upc=None, manufacturer_part_number="DP-100")
        self.assertTrue(has_strong_identifier(r))
        self.assertEqual(identifier_kind(r), "mpn")

    def test_no_identifier_routes_to_resolution(self):
        r = source_fixture(id="h", upc=None, manufacturer_part_number=None)
        res = assess_identity_readiness(r, None)
        self.assertTrue(res.identifier_resolution_required)
        self.assertFalse(res.identity_ready)

    def test_probable_only_when_enabled(self):
        r = source_fixture(id="i", upc=None, manufacturer_part_number=None)
        res = assess_identity_readiness(r, None, allow_probable=True)
        self.assertTrue(res.probable_only)
        self.assertFalse(res.identity_ready)


class AuditTests(unittest.TestCase):
    def test_audit_counts(self):
        store = _isolated_store()
        store.upsert_source_product(source_fixture(id="x1", upc="799488123456", size_or_weight_raw="1 lb"), run_id="run_e")
        store.upsert_source_product(source_fixture(id="x2", upc=None, manufacturer_part_number=None), run_id="run_e")
        a = audit_source_identity(store, run_id="run_e")
        self.assertEqual(a["eligible_records"], 2)
        self.assertGreaterEqual(a["identifier_coverage"]["upc"], 1)
        self.assertGreaterEqual(a["identifier_resolution_required_count"], 1)


class BrightDataAdapterTests(unittest.TestCase):
    def test_disabled_mode_zero_calls(self):
        for k in ("NORTHSTAR_BRIGHT_DATA_ENABLED", "NORTHSTAR_ENRICHMENT_APPROVED"):
            os.environ.pop(k, None)
        self.assertEqual(current_mode(), "disabled")

    def test_dry_run_manifest_zero_calls(self):
        store = _isolated_store()
        store.upsert_source_product(source_fixture(id="y1"), run_id="run_f")
        m = plan_enrichment_manifest(store, run_id="run_f", max_items=25, dry_run=True)
        self.assertEqual(m["network_calls_made"], 0)
        self.assertLessEqual(m["sample_size"], 25)

    def test_live_fails_closed_without_gates(self):
        out = run_enrichment({}, approved=False)
        self.assertEqual(out["result_status"], "requires_explicit_approval")
        self.assertEqual(out["network_calls_made"], 0)
        self.assertTrue(out["missing_gates"])

    def test_validate_schema(self):
        recs = [map_provider_record({"costco_item_number": "1", "brand": "X", "upc": "799488123456"}),
                map_provider_record({"costco_item_number": "2"})]
        rep = validate_schema(recs)
        self.assertEqual(rep["records"], 2)
        self.assertEqual(rep["identifier_coverage"]["upc"], 1)

    def test_import_snapshot_idempotent(self):
        store = _isolated_store()
        tmp = Path(tempfile.mkdtemp(prefix="cnk-snap-"))
        p = tmp / "snap.json"
        p.write_text(json.dumps({"records": [{"costco_item_number": "1", "brand": "X", "upc": "799488123456"}]}), encoding="utf-8")
        r1 = import_snapshot(str(p), store)
        self.assertEqual(r1["result_status"], "imported")
        r2 = import_snapshot(str(p), store)
        self.assertEqual(r2["result_status"], "duplicate")

    def test_provenance_persists(self):
        store = _isolated_store()
        rec = map_provider_record({"costco_item_number": "9", "brand": "X", "upc": "799488123456"},
                                  snapshot_sha256="deadbeef")
        store.upsert_enrichment_record(rec)
        got = store.get_enrichment_record("9")
        self.assertEqual(got["snapshot_sha256"], "deadbeef")
        self.assertEqual(got["identifier_capture_status"], "captured")

    def test_missing_identifier_status(self):
        rec = map_provider_record({"costco_item_number": "10"})
        self.assertEqual(rec["identifier_capture_status"], "field_not_returned")
        self.assertIsNone(rec["identifier_type"])

    def test_no_browser_automation_in_adapter(self):
        src = Path(__file__).resolve().parents[1] / "brightdata_costco_enrichment.py"
        text = src.read_text(encoding="utf-8")
        self.assertNotIn("playwright", text.lower())
        self.assertNotIn("amazon.com", text.lower())

    def test_requirements_profile_builds(self):
        prof = build_requirements_profile()
        self.assertEqual(prof["defaults"]["bright_data_enabled"], False)
        self.assertIn("identifier_required_for_exact_match", prof["rules"])


if __name__ == "__main__":
    unittest.main()
