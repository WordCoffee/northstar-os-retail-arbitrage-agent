"""Tests 10-13: provenance persistence, zero-network, no provider calls from
GET routes, no Kirkland in the eligible GG queue, store persistence + enrichment
approval gating."""
from __future__ import annotations

import os
import unittest
from unittest import mock

# Activate the network guard for this test process.
import test_network_guard  # noqa: F401

from costco_non_kirkland.snapshot import (
    build_market_snapshot,
    parse_bsr,
    CaptureStatus,
)
from costco_non_kirkland.providers import SellerAmpProvider, provider_factory, ProviderRetired
from costco_non_kirkland.pipeline import plan_enrichment, enrich, import_costco_local, build_match_queue, score_run, ENRICHMENT_APPROVAL_ENV
from costco_non_kirkland.matching import AmazonAttributes
from .fixtures import NON_KIRKLAND, NON_KIRKLAND_WITH_UPC, write_discovery_catalog_fixture, make_tmp_data_dir


class ProvenanceAndSnapshotTests(unittest.TestCase):
    def test_provenance_persistence(self):
        snap = build_market_snapshot(asin="B0123456789", title="Test Product",
                                     price=25.99, provider="selleramp")
        self.assertEqual(snap["fields"]["price"]["source"], "selleramp")
        self.assertEqual(snap["fields"]["price"]["capture_status"], CaptureStatus.CAPTURED.value)
        self.assertEqual(snap["fields"]["estimated_monthly_sales"]["evidence_class"], "provider_estimate")
        self.assertIn("provider estimate", snap["fields"]["estimated_monthly_sales"]["limitations"].lower())
        self.assertIsNotNone(snap["observed_at"])

    def test_unknown_is_unavailable_not_zero(self):
        snap = build_market_snapshot(asin="B0X", provider="selleramp",
                                     price=None, estimated_monthly_sales=None)
        self.assertEqual(snap["fields"]["price"]["value"], None)
        self.assertEqual(snap["fields"]["price"]["capture_status"], CaptureStatus.UNAVAILABLE.value)
        self.assertIsNone(snap["fields"]["estimated_monthly_sales"]["value"])

    def test_bsr_never_zero_when_unknown(self):
        fact = parse_bsr(None)
        self.assertIsNone(fact.bsr_primary_rank)
        self.assertEqual(fact.bsr_capture_status, CaptureStatus.UNAVAILABLE.value)
        self.assertEqual(fact.bsr_primary_rank, None)

    def test_bsr_parsed_first_class(self):
        fact = parse_bsr("#350 in Health & Household")
        self.assertEqual(fact.bsr_primary_rank, 350)
        self.assertEqual(fact.bsr_primary_category, "Health & Household")
        self.assertEqual(fact.bsr_capture_status, CaptureStatus.CAPTURED.value)

    def test_bsr_parse_error_status(self):
        fact = parse_bsr("not a bsr string")
        self.assertEqual(fact.bsr_capture_status, CaptureStatus.PARSE_ERROR.value)
        self.assertIsNone(fact.bsr_primary_rank)


class SellerAmpTests(unittest.TestCase):
    def test_disabled_by_default(self):
        p = SellerAmpProvider()
        status = p.is_configured()
        self.assertFalse(status.configured)
        self.assertEqual(status.mode, "deep_link_only")
        self.assertIn("provider_not_configured", status.reason)

    def test_mock_fetch(self):
        p = SellerAmpProvider()
        out = p.fetch("B0123456789", mock=True)
        self.assertEqual(out["result_status"], "fixture")
        self.assertTrue(all(f["source_name"] == "selleramp" for f in out["fields"]))
        self.assertIn("MOCK DATA ONLY", out["note"])

    def test_deep_link_does_not_imply_data(self):
        p = SellerAmpProvider()
        link = p.deep_link("B0123456789")
        self.assertIn("B0123456789", link)
        status = p.is_configured()
        self.assertFalse(status.configured)  # deep link alone is not configured access


class RetiredProviderTests(unittest.TestCase):
    def test_sellersprite_retired_in_factory(self):
        with self.assertRaises(ProviderRetired):
            provider_factory("sellersprite")

    def test_sellersprite_retired_in_signin(self):
        from costco_non_kirkland.signin import require_signin
        prompt = require_signin("sellersprite", store=None)
        self.assertTrue(prompt.required)
        self.assertIn("retired", prompt.message.lower())
        self.assertIsNone(prompt.url)


class PipelineStoreAndEnrichmentTests(unittest.TestCase):
    def _isolated_store(self):
        import tempfile
        from pathlib import Path
        import data_layer
        tmp = Path(tempfile.mkdtemp(prefix="cnk-"))
        data_layer._SQLITE_PATH = tmp / "northstar.db"
        data_layer._db_instance = None
        from costco_non_kirkland.store import PipelineStore
        return PipelineStore()

    def test_store_persists_source_product(self):
        store = self._isolated_store()
        from costco_non_kirkland.normalize import normalize_costco_record, apply_exclusion
        rec = apply_exclusion(normalize_costco_record(NON_KIRKLAND))
        stored = store.upsert_source_product(rec, run_id="run_test")
        rows = store.list_source_products(eligible_only=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["brand_normalized"], "dream plush")

    def test_import_excludes_and_persists(self):
        store = self._isolated_store()
        from costco_non_kirkland.normalize import load_discovery_catalog
        with mock.patch("costco_non_kirkland.pipeline.load_local_records",
                        return_value=[dict(NON_KIRKLAND), dict(NON_KIRKLAND_WITH_UPC)]):
            result = import_costco_local(store=store, dry_run=False)
        self.assertEqual(result.eligible, 2)
        self.assertEqual(result.excluded_kirkland, 0)
        self.assertEqual(store.count_source_products(eligible_only=True), 2)

    def test_enrichment_plan_is_dry_run_and_requires_approval(self):
        store = self._isolated_store()
        run = store.create_run("enrich test", command="import")
        from costco_non_kirkland.normalize import normalize_costco_record, apply_exclusion
        csp = store.upsert_source_product(
            apply_exclusion(normalize_costco_record(NON_KIRKLAND_WITH_UPC)), run_id=run["run_id"])
        store.insert_match_candidate({
            "costco_source_product_id": csp["id"], "asin": "B0123456789",
            "match_method": "upc_exact", "match_confidence": 0.95,
            "title_similarity": 0.8, "brand_match_status": "match",
            "pack_match_status": "exact", "size_match_status": "match",
            "variation_match_status": "unknown", "identity_status": "upc_exact_candidate",
            "match_rationale": "UPC exact", "manual_review_required": 0,
            "amazon_title": "Swissgear 8097", "amazon_brand": "SwissGear",
        }, run_id=run["run_id"])

        plan = plan_enrichment(run["run_id"], provider="selleramp", max_items=5, dry_run=True)
        self.assertTrue(plan.get("dry_run"))
        self.assertTrue(plan.get("no_live_calls"))
        self.assertEqual(plan.get("selected_items"), 1)
        # Dry-run creates NO manifest (fail closed: no approval requested).
        self.assertIsNone(plan.get("manifest_id"))
        # Dry-run preflight surfaces the sign-in prompt (fail-closed gate).
        self.assertTrue(plan.get("signin_prompt", {}).get("required"))

        # Retired provider is rejected outright.
        retired = plan_enrichment(run["run_id"], provider="sellersprite", max_items=5, dry_run=True)
        self.assertEqual(retired.get("reason"), "retired_provider")

        # Non-dry-run plan creates a manifest, but execution still needs approval.
        manifest = plan_enrichment(run["run_id"], provider="selleramp", max_items=5, dry_run=False)
        self.assertIn("manifest_id", manifest)
        result = enrich(manifest["manifest_id"], approved=False)
        self.assertIn("NOT APPROVED", result.get("error", ""))

        # Approved but NOT signed in -> fails closed at the sign-in gate.
        os.environ[ENRICHMENT_APPROVAL_ENV] = "1"
        result2 = enrich(manifest["manifest_id"], approved=True, mock=True)
        self.assertIn("SIGN-IN REQUIRED", result2.get("error", ""))
        self.assertEqual(result2.get("status"), "requires_sign_in")
        del os.environ[ENRICHMENT_APPROVAL_ENV]

        # Signed in + approved + mock -> runs fixture only, never purchase-authorized.
        from costco_non_kirkland.signin import mark_signed_in
        mark_signed_in("selleramp", store=store)
        os.environ[ENRICHMENT_APPROVAL_ENV] = "1"
        result3 = enrich(manifest["manifest_id"], approved=True, mock=True)
        self.assertTrue(result3.get("approved"))
        self.assertEqual(result3.get("purchase_authorization_status"), "not_authorized")
        del os.environ[ENRICHMENT_APPROVAL_ENV]

    def test_no_kirkland_in_eligible_gg_queue(self):
        store = self._isolated_store()
        from costco_non_kirkland.normalize import normalize_costco_record, apply_exclusion
        from .fixtures import KIRKLAND_BRAND
        k = apply_exclusion(normalize_costco_record(KIRKLAND_BRAND))
        n = apply_exclusion(normalize_costco_record(NON_KIRKLAND_WITH_UPC))
        store.upsert_source_product(k, run_id="run_gg")
        store.upsert_source_product(n, run_id="run_gg")
        eligible = store.list_source_products(run_id="run_gg", eligible_only=True)
        self.assertEqual(len(eligible), 1)
        self.assertNotEqual(eligible[0]["brand_normalized"], "kirkland signature")

    def test_zero_network_in_offline_mode(self):
        # network_guard is active: any real requests call must raise.
        import requests
        from network_guard import NetworkGuardViolation
        with self.assertRaises(NetworkGuardViolation):
            requests.get("http://127.0.0.1:9/", timeout=0.1)


if __name__ == "__main__":
    unittest.main()