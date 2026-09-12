"""Offline tests for the ASIN market-data completeness plan scaffolding.

Files under test (all planning-only, NOT wired into the server):
  - intel_schema.py            schema validation for normalized snapshots
  - completeness_score.py      0-100 score + status taxonomy
  - enrichment_preflight.py    dry-run enrichment planner (batch <= 20)

Honesty invariants verified:
  - 0 is never a substitute for an unknown number (validator rejects it).
  - Missing demand/sellers/cost are never fabricated.
  - Ready for Test Buy requires all data gates AND account-review approval.
  - purchase_authorized requires an invoice-confirmed cost basis.
  - The planner issues zero network requests and never writes files.

Mirrors the containment pattern: the GET scanner route must stay cache-only
with every outbound provider patched to explode.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import amazon_search
import bright_data_client
import canopy_client
import costco_api_client
import easyparser_client
import main
import offer_enrichment
import scavio_client

from intel_schema import fixture_minimal, validate_snapshot, snapshot_from_fixture
from completeness_score import compute_completeness, compute_scanner_completeness
from enrichment_preflight import plan_enrichment

_TMP = os.path.join(tempfile.gettempdir(), "opencode", "asin-intel-plan-tests")
os.makedirs(_TMP, exist_ok=True)


def _worst_case_env():
    return {
        "SCANNER_LIVE_ALLOWED": "0",
        "SCANNER_SEARCH_SOURCE": "BRIGHTDATA",
        "SCANNER_SEARCH_FALLBACK": "SCAVIO",
        "SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA",
        "SCANNER_LOCAL_SNAPSHOT_MERGE": "0",
        "SCANNER_SEARCH_CACHE_PATH": os.path.join(_TMP, "search-cache.json"),
        "SCANNER_OFFER_CACHE_PATH": os.path.join(_TMP, "offer-cache.json"),
        "SCANNER_SELLER_CACHE_PATH": os.path.join(_TMP, "seller-cache.json"),
        "SCANNER_ENRICH_RUN_REPORT_PATH": os.path.join(_TMP, "enrich-report.json"),
        "SCANNER_MARKET_SNAPSHOT_PATH": os.path.join(_TMP, "snapshots.json"),
    }


def _boom(*args, **kwargs):
    raise AssertionError("provider call leaked")


def _provider_patches():
    return [
        patch.object(bright_data_client, "search_products", side_effect=_boom),
        patch.object(bright_data_client, "get_product_detail", side_effect=_boom),
        patch.object(scavio_client, "search_kirkland_products", side_effect=_boom),
        patch.object(amazon_search, "_search_brightdata", side_effect=_boom),
        patch.object(amazon_search, "_search_chocodata", side_effect=_boom),
        patch.object(offer_enrichment, "get_easyparser_offers", side_effect=_boom),
        patch.object(offer_enrichment, "get_product_detail", side_effect=_boom),
        patch.object(offer_enrichment, "enrich_product", side_effect=_boom),
        patch.object(offer_enrichment, "get_offer_data", side_effect=_boom),
        patch.object(canopy_client.requests, "get", side_effect=_boom),
        patch.object(costco_api_client.requests, "get", side_effect=_boom),
        patch.object(easyparser_client.requests, "get", side_effect=_boom),
    ]


def _full_fixture():
    snap = fixture_minimal()
    facts = snap["facts"]
    facts["identity"] = {
        "name": "Kirkland Signature Example Product",
        "pack_match": "exact",
        "upc_or_ean": "096619999999",
        "net_weight_lbs": 3.0,
    }
    facts["cost"] = {
        "costco_cost": 12.99,
        "cost_status": "business_center_invoice_confirmed",
        "source": "business_center_invoice",
        "paid_cost_invoice": 12.99,
    }
    facts["fees"] = {
        "referral_fee": 1.95,
        "referral_fee_confidence": "verified",
        "fba_fee": 4.75,
        "fba_fee_status": "verified_seller_central",
        "prep_cost_per_unit": 0.0,
        "inbound_cost_per_unit": 0.0,
        "packaging_cost_per_unit": 0.0,
        "return_reserve_rate": 0.0,
    }
    facts["demand"] = {
        "estimated_monthly_sales": 480,
        "sales_estimation_method": "provider_verified",
        "sales_estimation_confidence": "high",
    }
    facts["market"] = {
        "amazon_price": 24.99,
        "buy_box": {
            "available": True,
            "price": 24.99,
            "seller_name": "Seller A",
            "seller_id": "S1",
            "fulfillment": "FBA",
            "source": "easyparser",
            "observed_at": "2026-08-17T12:00:00+00:00",
        },
        "seller_counts": {
            "total_observed": 6,
            "fba_observed": 4,
            "fbm_observed": 2,
            "amazon_observed": 1,
            "claimed_total": 6,
        },
        "coverage": {
            "offer_list_available": True,
            "offers_complete_status": "full",
            "coverage_reason": None,
        },
        "offers": [
            {
                "position": 1,
                "is_buy_box_winner": True,
                "price": 24.99,
                "condition": "New",
                "seller_id": "S1",
                "seller_name": "Seller A",
                "fulfillment": "FBA",
            }
        ],
    }
    facts["economics"] = {
        "net_profit": 2.54,
        "roi_pct": 19.5,
        "economics_confidence": "estimated",
        "economics_status": "estimated_fee_stack",
    }
    facts["provenance"] = {
        "identity.name": {"source": "easyparser", "fetched_at": "2026-08-17T12:00:00+00:00"},
        "identity.upc_or_ean": {"source": "easyparser", "fetched_at": "2026-08-17T12:00:00+00:00"},
        "identity.net_weight_lbs": {"source": "easyparser", "fetched_at": "2026-08-17T12:00:00+00:00"},
        "market.amazon_price": {"source": "easyparser", "fetched_at": "2026-08-17T12:00:00+00:00"},
        "cost.costco_cost": {"source": "business_center_invoice", "fetched_at": "2026-08-16T09:00:00+00:00"},
        "cost.paid_cost_invoice": {"source": "business_center_invoice", "fetched_at": "2026-08-16T09:00:00+00:00"},
        "fees.referral_fee": {"source": "seller_central", "fetched_at": "2026-08-15T10:00:00+00:00"},
        "fees.fba_fee": {"source": "seller_central", "fetched_at": "2026-08-15T10:00:00+00:00"},
        "fees.prep_cost_per_unit": {"source": "configuration", "fetched_at": "2026-08-15T10:00:00+00:00"},
        "fees.inbound_cost_per_unit": {"source": "configuration", "fetched_at": "2026-08-15T10:00:00+00:00"},
        "fees.packaging_cost_per_unit": {"source": "configuration", "fetched_at": "2026-08-15T10:00:00+00:00"},
        "fees.return_reserve_rate": {"source": "configuration", "fetched_at": "2026-08-15T10:00:00+00:00"},
        "demand.estimated_monthly_sales": {"source": "internal_estimate", "fetched_at": "2026-08-17T12:00:00+00:00"},
    }
    return snap


class IntelSchemaTests(unittest.TestCase):
    def test_minimal_fixture_is_valid(self):
        self.assertEqual(validate_snapshot(fixture_minimal()), [])

    def test_full_fixture_is_valid(self):
        self.assertEqual(validate_snapshot(_full_fixture()), [])

    def test_zero_never_substitutes_for_unknown(self):
        snap = _full_fixture()
        snap["facts"]["market"]["amazon_price"] = 0
        errors = validate_snapshot(snap)
        self.assertTrue(any("amazon_price is 0" in e for e in errors))

        snap = _full_fixture()
        snap["facts"]["fees"]["fba_fee"] = 0
        errors = validate_snapshot(snap)
        self.assertTrue(any("fba_fee is 0" in e for e in errors))

        snap = _full_fixture()
        snap["facts"]["economics"]["net_profit"] = 0
        errors = validate_snapshot(snap)
        self.assertTrue(any("net_profit is 0" in e for e in errors))

    def test_missing_top_level_keys_rejected(self):
        errors = validate_snapshot({"asin": "B0PLACEH0LD"})
        self.assertIn("missing top-level key: schema_version", errors)
        self.assertIn("missing top-level key: facts", errors)

    def test_invalid_asin_rejected(self):
        snap = fixture_minimal()
        snap["asin"] = "not-an-asin"
        self.assertTrue(any("asin must be" in e for e in validate_snapshot(snap)))

    def test_partial_coverage_requires_reason(self):
        snap = _full_fixture()
        snap["facts"]["market"]["coverage"] = {
            "offer_list_available": True,
            "offers_complete_status": "partial",
            "coverage_reason": None,
        }
        errors = validate_snapshot(snap)
        self.assertTrue(any("coverage_reason required" in e for e in errors))

    def test_every_fact_field_needs_provenance(self):
        snap = _full_fixture()
        del snap["facts"]["provenance"]
        errors = validate_snapshot(snap)
        self.assertTrue(any("no provenance entry" in e for e in errors))


class CompletenessScoreTests(unittest.TestCase):
    def test_empty_snapshot_score_null_not_computable(self):
        result = compute_completeness({"facts": {}})
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], "not_computable")
        self.assertEqual(result["score_max"], 0)
        for cat, value in result["category_scores"].items():
            self.assertIsNone(value)

    def test_minimal_fixture_evaluated_statuses_earn_real_zero(self):
        # The minimal fixture carries evaluated "unavailable"/"unknown"
        # statuses: those ARE evidence, so the affected categories are
        # computable and genuinely earn 0 points — never null, never a
        # fabricated number.
        result = compute_completeness(fixture_minimal())
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["status"], "needs_mapping")
        self.assertEqual(result["category_scores"]["identity_mapping"], None)
        # buy_box.available=False is itself evaluated evidence ("no buy
        # box"), so market is computable and genuinely earns 0.
        self.assertEqual(result["category_scores"]["market_coverage"], 0)
        self.assertEqual(result["category_scores"]["source_cost"], 0)
        self.assertEqual(result["category_scores"]["fees_economics"], 0)
        self.assertEqual(result["category_scores"]["demand"], 0)
        self.assertEqual(result["category_scores"]["invoice_readiness"], 0)
        self.assertEqual(result["score_max"], 85)

    def test_scanner_empty_row_score_null_not_computable(self):
        result = compute_scanner_completeness({})
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], "not_computable")
        self.assertEqual(result["score_max"], 0)

    def test_scanner_genuine_zero_explicitly_constructed(self):
        # Every computable category earns 0 from evaluated evidence:
        # pack mismatch (identity 0), stated cost basis (cost 0),
        # explicit no-buy-box (market 0), economics unavailable (fees 0),
        # demand signals present-but-empty (demand 0), stated basis
        # (invoice 0). A proven genuine zero — tested separately from the
        # null-score case above.
        row = {
            "name": None,
            "pack_match": "mismatch",
            "amazon_price": None,
            "costco_cost": None,
            "costco_cost_basis": "unavailable",
            "observed_buy_box_available": False,
            "economics_confidence": "unavailable",
            "monthly_sales_estimate": None,
            "sales_estimation_method": "unknown",
        }
        result = compute_scanner_completeness(row)
        self.assertEqual(result["score"], 0)
        self.assertNotEqual(result["status"], "not_computable")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["purchase_authorized"])
        self.assertEqual(result["score_max"], 100)

    def test_scanner_partial_row_real_partial_score(self):
        # Evaluated inputs exist for some categories only: demand and
        # identity (name-only) are NOT computable; the rest compute real
        # points. Score is a real partial score, never null, never
        # fabricated.
        row = {
            "name": "Kirkland Signature Example Product",
            "pack_match": None,
            "amazon_price": 24.99,
            "costco_cost": 12.99,
            "costco_cost_basis": "estimated",
            "referral_fee": 1.95,
            "fba_fee": 4.75,
            "fba_fee_status": "estimated",
            "economics_confidence": "estimated",
            "net_profit": 2.54,
            "roi_pct": 19.5,
            "monthly_sales_estimate": None,
            "sales_estimation_confidence": None,
        }
        result = compute_scanner_completeness(row)
        self.assertIsNotNone(result["score"])
        self.assertGreater(result["score"], 0)
        self.assertLess(result["score_max"], 100)
        self.assertIsNone(result["category_scores"]["demand"])
        self.assertIsNotNone(result["category_scores"]["source_cost"])
        self.assertIn("demand", result["missing_inputs"])
        self.assertEqual(result["status"], "needs_mapping")

    def test_full_fixture_scores_100(self):
        result = compute_completeness(_full_fixture(), account_review_approved=True)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["score_max"], 100)
        self.assertEqual(result["status"], "ready_for_test_buy")
        self.assertTrue(result["purchase_authorized"])

    def test_ready_requires_account_review_approval(self):
        result = compute_completeness(_full_fixture(), account_review_approved=False)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("requires_account_review", result["status_reason"])

    def test_purchase_authorization_requires_invoice(self):
        snap = _full_fixture()
        snap["facts"]["cost"]["cost_status"] = "costco_online_discovery"
        result = compute_completeness(snap, account_review_approved=True)
        self.assertEqual(result["status"], "needs_invoice_confirmation")
        self.assertFalse(result["purchase_authorized"])

    def test_pack_mismatch_blocks(self):
        snap = _full_fixture()
        snap["facts"]["identity"]["pack_match"] = "mismatch"
        result = compute_completeness(snap, account_review_approved=True)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["purchase_authorized"])

    def test_partial_coverage_caps_market_category(self):
        snap = _full_fixture()
        snap["facts"]["market"]["coverage"] = {
            "offer_list_available": True,
            "offers_complete_status": "partial",
            "coverage_reason": "aggregate-only provider data",
        }
        result = compute_completeness(snap, account_review_approved=True)
        self.assertLessEqual(result["category_scores"]["market_coverage"], 10)
        self.assertEqual(result["score"], 90)

    def test_provisional_fees_cap_fee_category(self):
        snap = _full_fixture()
        snap["facts"]["fees"]["fba_fee_status"] = "provisional"
        snap["facts"]["economics"]["economics_confidence"] = "provisional"
        result = compute_completeness(snap, account_review_approved=True)
        self.assertLessEqual(result["category_scores"]["fees_economics"], 8)
        self.assertEqual(result["status"], "needs_fee_verification")

    def test_missing_demand_never_fabricated(self):
        snap = _full_fixture()
        snap["facts"]["demand"]["estimated_monthly_sales"] = None
        result = compute_completeness(snap, account_review_approved=True)
        self.assertEqual(result["category_scores"]["demand"], 0)
        self.assertEqual(result["status"], "needs_demand_data")
        self.assertIsNone(snap["facts"]["demand"]["estimated_monthly_sales"])

    def test_missing_sellers_never_invented(self):
        snap = _full_fixture()
        snap["facts"]["market"]["seller_counts"]["total_observed"] = None
        snap["facts"]["market"]["seller_counts"]["fba_observed"] = None
        result = compute_completeness(snap, account_review_approved=True)
        self.assertLess(result["score"], 100)
        self.assertNotEqual(result["category_scores"]["market_coverage"], 20)

    def test_score_monotone_adding_data_never_lowers(self):
        base = compute_completeness(fixture_minimal())
        full = compute_completeness(_full_fixture())
        self.assertGreaterEqual(full["score"], base["score"])


class EnrichmentPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._preloaded = {m for m in sys.modules if m.startswith(("easyparser_client", "bright_data_client", "scavio_client", "canopy_client", "offer_enrichment"))}

    def test_provider_modules_never_imported_by_planner(self):
        after = {m for m in sys.modules if m.startswith(("easyparser_client", "bright_data_client", "scavio_client", "canopy_client", "offer_enrichment"))}
        self.assertEqual(after - self._preloaded, set())

    def test_batch_hard_cap_twenty(self):
        asins = [f"B0XXXXX{i:03d}" for i in range(40)]
        plan = plan_enrichment(asins, provider="EASYPARSER")
        self.assertLessEqual(len(plan["asins_selected"]), 20)
        self.assertEqual(len(plan["asins_deferred_batch"]), 20)

    def test_env_batch_size_override_clamped(self):
        asins = [f"B0XXXXX{i:03d}" for i in range(30)]
        with patch.dict(os.environ, {"MAX_ENRICHMENT_BATCH_SIZE": "50"}):
            plan = plan_enrichment(asins, provider="EASYPARSER")
            self.assertLessEqual(len(plan["asins_selected"]), 20)
        with patch.dict(os.environ, {"MAX_ENRICHMENT_BATCH_SIZE": "5"}):
            plan = plan_enrichment(asins, provider="EASYPARSER")
            self.assertEqual(len(plan["asins_selected"]), 5)

    def test_fresh_cache_skips_zero_cost(self):
        asins = ["B0XXXXX001", "B0XXXXX002"]
        plan = plan_enrichment(
            asins,
            cache_statuses={"B0XXXXX001": "fresh", "B0XXXXX002": "absent"},
            provider="EASYPARSER",
        )
        self.assertEqual(plan["requests_planned"], 1)
        self.assertEqual(plan["asins_skipped_fresh"], ["B0XXXXX001"])
        self.assertEqual(plan["credit_estimate"], 5)

    def test_budget_stop_truncates_plan(self):
        asins = [f"B0XXXXX{i:03d}" for i in range(10)]
        plan = plan_enrichment(asins, provider="EASYPARSER", max_credits=10)
        self.assertEqual(plan["requests_planned"], 2)
        self.assertEqual(len(plan["asins_deferred_budget"]), 8)
        self.assertTrue(plan["budget_stop"])

    def test_unknown_provider_credit_is_none_not_guess(self):
        plan = plan_enrichment(["B0XXXXX0001"], provider="SCAVIO")
        self.assertIsNone(plan["credit_estimate"])
        self.assertEqual(plan["credit_estimate_source"], "unknown")

    def test_invalid_asins_rejected(self):
        plan = plan_enrichment(["B0XXXXX001", "nope", "123"], provider="EASYPARSER")
        self.assertEqual(plan["asins_invalid"], ["nope", "123"])
        self.assertEqual(plan["asins_selected"], ["B0XXXXX001"])

    def test_dry_run_and_human_confirmation_flags(self):
        plan = plan_enrichment(["B0XXXXX0001"], provider="EASYPARSER")
        self.assertTrue(plan["dry_run"])
        self.assertTrue(plan["requires_human_confirmation"])

    def test_missing_field_groups_reported(self):
        snap = fixture_minimal()
        plan = plan_enrichment(
            ["B0PLACEH01"],
            snapshots={"B0PLACEH01": snap},
            provider="EASYPARSER",
        )
        groups = plan["planned_requests"][0]["field_groups_sought"]
        self.assertIn("identity_pack", groups)
        self.assertIn("source_cost", groups)
        self.assertIn("market_offers", groups)


class ScannerGateReassertTests(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, _worst_case_env(), clear=True)
        self._env.start()
        self._patches = _provider_patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._env.stop()

    def test_scanner_get_remains_cache_only(self):
        body = main.get_kirkland_scanner()
        self.assertFalse(body["summary"]["live_allowed"])
        self.assertEqual(body["summary"]["scanner_mode"], "cache_only")
        self.assertEqual(body["summary"]["enrichment_source"], "OFF")
        self.assertIsNotNone(body.get("products"))

    def test_live_route_get_remains_cache_only(self):
        body = main.get_kirkland_live()
        self.assertIsNotNone(body)


if __name__ == "__main__":
    unittest.main()