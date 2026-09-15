"""Mocked unit tests for the GET /api/kirkland/scanner response contract.

Never calls Scavio, Bright Data, Costco, Canopy, Easyparser, or any
external API. All pipeline inputs are mocked via product_analysis.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import os
import unittest
from unittest.mock import patch

import amazon_search
import costco_client
import costco_api_client
import main
import offer_enrichment
import product_analysis


def setUpModule():
    """Live-path tests: explicitly opt into SCANNER_LIVE_ALLOWED (the
    default-off gate). tearDownModule restores it for later modules."""
    os.environ["SCANNER_LIVE_ALLOWED"] = "1"


def tearDownModule():
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)

# These route tests exercise the enabled (live-search + get_scanner_offer)
# path, so pin the mode explicitly: the production default for an unset
# SCANNER_OFFER_ENRICHMENT is now cache-only (OFF). Cache-only behavior
# is covered by test_scanner_cache_only.py. setdefault, never clobber:
# every consumer here pins the mode per call anyway (see _get), so an
# unconditional write would only re-order the full suite.
os.environ.setdefault("SCANNER_OFFER_ENRICHMENT", "BRIGHTDATA")

ALLOWED = set(main.SCANNER_ALLOWED_KEYS)
FORBIDDEN = {
    "prep_cost",
    "inbound_shipping_cost",
    "landed_cost",
    "projected_net_profit",
    "projected_roi_pct",
    "financial_data_gaps",
    "financial_status",
    "financial_decision_status",
    "amazon_fees_total",
    "amazon_payout_before_inventory_costs",
    "cogs",
    "fba_sellers_estimated",
    "fba_seller_preference",
    "lowest_price_seller_type",
    "highest_price_seller_type",
}


def fake_candidate(asin, name, amazon_price=48.87):
    return {
        "name": name,
        "product_url": f"https://www.amazon.com/dp/{asin}",
        "asin": asin,
        "amazon_price": amazon_price,
    }


def fake_offer(amazon_price, monthly_sales=None, monthly_sales_estimated=True):
    return {
        "amazon_price": amazon_price,
        "lowest_price": 45.0,
        "highest_price": 60.0,
        "total_sellers": 5,
        "fba_sellers": 2,
        "fba_sellers_estimated": True,
        "lowest_price_seller_type": "FBA",
        "highest_price_seller_type": "FBM",
        "monthly_sales_estimate": monthly_sales,
        "monthly_sales_estimated": monthly_sales_estimated,
    }


def fake_costco(costco_cost=15.99, weight_lbs=None, match_quality="exact"):
    row = {"costco_cost": costco_cost, "match_quality": match_quality}
    if weight_lbs is not None:
        row["weight_lbs"] = weight_lbs
    return row


def fake_profile(status="need_cost_data", profit=None, roi=None, gaps=()):
    return {
        "amazon_sale_price": None,
        "referral_fee": None,
        "fba_fulfillment_fee": None,
        "amazon_fees_total": None,
        "amazon_payout_before_inventory_costs": None,
        "cogs": None,
        "prep_cost": None,
        "inbound_shipping_cost": None,
        "landed_cost": None,
        "projected_net_profit": profit,
        "projected_roi_pct": roi,
        "financial_status": status,
        "financial_data_gaps": list(gaps),
    }


FAKE_DISCOVERY = {
    "run_report_exists": True,
    "archive_record_count": 24,
    "threshold_days": 8,
    "location": {"delivery_zip": "75201", "business_center": "Dallas Business Center"},
    "freshness": "fresh",
    "last_run_at": "2026-08-16T03:00:00+00:00",
    "last_fetched_at": "2026-08-16T03:00:00+00:00",
    "status": "ok",
    "stop_reason": None,
    "last_fetched_count": 24,
}


def fake_economics(net=None, roi=None, confidence="provisional", status="needs_fee_verification"):
    """Deterministic fee-engine economics dict for patching."""
    return {
        "amazon_category": "Grocery & Gourmet Food",
        "browse_node_id": 16310101,
        "category_resolution_source": "breadcrumb",
        "category_resolution_confidence": "inferred",
        "category_resolution_note": "Resolved from Amazon page breadcrumbs; confirm the exact category in Seller Central.",
        "pack_match": "exact",
        "costco_cogs": 15.99,
        "costco_cost_basis": "estimated",
        "referral_fee": None,
        "referral_fee_rate": None,
        "referral_fee_category": None,
        "referral_fee_confidence": "default_category",
        "referral_fee_rule": "REF-2026.1-Everything Else",
        "referral_fee_tier": None,
        "referral_fee_note": "default category applied",
        "fba_base_fee": None,
        "fba_fuel_logistics_surcharge": None,
        "fba_size_tier": None,
        "fba_fee_status": "weight_unavailable",
        "fba_fee_confidence": "unavailable",
        "fba_fee_rule": "FBA-2026.1",
        "fba_fee_note": "test economics",
        "fba_weight_basis_lbs": None,
        "inbound_cost_per_unit": 0.35,
        "prep_cost_per_unit": 0.25,
        "packaging_cost_per_unit": 0.0,
        "return_reserve_rate": 0.02,
        "net_profit": net,
        "roi_pct": roi,
        "economics_confidence": confidence,
        "economics_status": status,
        "economics_note": "test economics",
    }


def ok_patches(candidates, offers_by_asin, profits_by_price, sales_by_asin):
    """Permissive scan thresholds so nothing is dropped by env values.
    Profits map by amazon_price -> (net, roi) for estimated rows; rows
    without an entry fall back to provisional economics."""
    def economics_for(product, costco):
        price = product.get("amazon_price")
        if price in profits_by_price:
            net, roi = profits_by_price[price]
            return fake_economics(net=net, roi=roi, confidence="estimated", status="estimated_fee_stack")
        return fake_economics(net=10.0, roi=80.0)

    return [
        patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
        patch.object(
            offer_enrichment,
            "get_scanner_offer",
            side_effect=lambda identifier: offers_by_asin[identifier.rsplit("/", 1)[-1]],
        ),
        patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
        patch.object(product_analysis, "calculate_unit_economics", side_effect=economics_for),
        patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
        patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
        patch.object(
            product_analysis,
            "estimate_financial_profile",
            return_value=fake_profile(),
        ),
        patch.object(costco_client, "catalog_state", return_value="ready"),
        patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY),
    ]


class TestScannerEndpoint(unittest.TestCase):
    def _get(self, patches):
        # Pin the enrichment mode per call: the module-level default (line
        # 23) can be overwritten by other test modules imported later in the
        # same run (e.g. test_manual_import forces OFF at import time), which
        # would silently switch these endpoint tests into cache-only mode and
        # bypass their search_kirkland_products patch. Restored after.
        with patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False):
            with patches[0]:
                for p in patches[1:]:
                    p.start()
                try:
                    return main.get_kirkland_scanner()
                finally:
                    for p in reversed(patches[1:]):
                        p.stop()

    def test_health_works(self):
        result = main.health()
        self.assertEqual(result["status"], "ok")

    def test_response_shape_and_allowlisted_keys_only(self):
        candidates = [fake_candidate("B000000001", "Alpha", 48.87)]
        patches = ok_patches(
            candidates,
            {"B000000001": fake_offer(48.87, monthly_sales=1500)},
            {48.87: (20.0, 125.1)},
            {"B000000001": 1500},
        )
        body = self._get(patches)

        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["summary"]["candidates_returned"], 1)
        self.assertEqual(body["summary"]["costco_catalog"], "ready")
        self.assertIsNotNone(body["generated_at"])
        self.assertTrue(body["generated_at"].endswith("+00:00") or body["generated_at"].endswith("Z") or "Z" in body["generated_at"] or "+00:00" in body["generated_at"])

        product = body["products"][0]
        self.assertEqual(set(product.keys()), ALLOWED)
        self.assertFalse(FORBIDDEN.intersection(product.keys()))
        self.assertIn("offer_data_provider", product)
        self.assertIn("enrichment_status", product)
        self.assertIn("enriched_at", product)
        # Category-resolution metadata survives the allowlist intact.
        self.assertEqual(product["browse_node_id"], 16310101)
        self.assertEqual(product["category_resolution_source"], "breadcrumb")
        self.assertEqual(product["category_resolution_confidence"], "inferred")
        self.assertIn("Seller Central", product["category_resolution_note"])
        # Pack/Variant Match field survives the allowlist.
        self.assertEqual(product["pack_match"], "exact")

    def test_enrichment_provenance_passes_through(self):
        candidates = [fake_candidate("B000000001", "Alpha", 48.87)]
        offer = fake_offer(48.87, monthly_sales=1500)
        offer["offer_data_provider"] = "easyparser"
        offer["enrichment_status"] = "complete"
        offer["enriched_at"] = "2026-08-13T10:00:00+00:00"
        patches = ok_patches(
            candidates,
            {"B000000001": offer},
            {48.87: (20.0, 125.1)},
            {"B000000001": 1500},
        )
        body = self._get(patches)
        product = body["products"][0]
        self.assertEqual(product["offer_data_provider"], "easyparser")
        self.assertEqual(product["enrichment_status"], "complete")
        self.assertEqual(product["enriched_at"], "2026-08-13T10:00:00+00:00")

    def test_cost_match_provenance_passes_through(self):
        """cost_match_reason / cost_source / cost_is_purchase_authorized
        survive the allowlist intact (additive, backward-compatible)."""
        candidates = [fake_candidate("B000000001", "Alpha", 48.87)]

        def costco_for(name, **kwargs):
            return {
                "costco_cost": 15.99,
                "costco_cost_basis": "estimated",
                "match_quality": "high_confidence",
                "match_reason": "Strong normalized title identity (90%); Costco carries no weight/pack/UPC evidence and none conflicts.",
                "source": "csv",
            }

        def economics_for(product, costco):
            econ = fake_economics(net=20.0, roi=125.1, confidence="estimated", status="estimated_fee_stack")
            econ.pop("pack_match", None)
            return econ

        patches = ok_patches(
            candidates,
            {"B000000001": fake_offer(48.87, monthly_sales=1500)},
            {48.87: (20.0, 125.1)},
            {"B000000001": 1500},
        )
        patches.append(patch.object(product_analysis, "get_costco_price", side_effect=costco_for))
        patches.append(patch.object(product_analysis, "calculate_unit_economics", side_effect=economics_for))
        body = self._get(patches)
        product = body["products"][0]
        self.assertEqual(product["pack_match"], "high_confidence")
        self.assertEqual(product["cost_match_reason"], "Strong normalized title identity (90%); Costco carries no weight/pack/UPC evidence and none conflicts.")
        self.assertEqual(product["cost_source"], "csv")
        self.assertIs(product["cost_is_purchase_authorized"], False)

    def test_internal_fields_never_appear(self):
        """Legacy internal profile fields must never appear as response
        keys (checked recursively; substring matching would false-positive
        on the new public fee-engine fields like costco_cogs)."""
        candidates = [fake_candidate("B000000001", "Alpha", 48.87)]
        patches = ok_patches(
            candidates,
            {"B000000001": fake_offer(48.87, monthly_sales=1500)},
            {48.87: (20.0, 125.1)},
            {"B000000001": 1500},
        )
        body = self._get(patches)

        def walk_keys(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    yield k
                    yield from walk_keys(v)
            elif isinstance(node, list):
                for item in node:
                    yield from walk_keys(item)

        keys = set(walk_keys(body))
        self.assertFalse(FORBIDDEN.intersection(keys))

    def test_empty_data_returns_no_candidates(self):
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=[]),
            patch.object(costco_client, "catalog_state", return_value="ready"),
            patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY),
        ]
        body = self._get(patches)
        self.assertEqual(body["status"], "no_candidates")
        self.assertEqual(body["summary"]["candidates_returned"], 0)
        self.assertEqual(body["summary"]["costco_catalog"], "ready")
        self.assertEqual(body["products"], [])

    def test_upstream_unavailable_when_search_failed(self):
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=[]),
            patch.object(amazon_search, "load_cached_candidates", return_value=[]),
            patch.object(costco_client, "catalog_state", return_value="empty"),
            patch.object(main.amazon_search, "LAST_SEARCH_ERROR", "HTTP 500"),
            patch.object(main.amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"),
            patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY),
        ]
        body = self._get(patches)
        self.assertEqual(body["status"], "upstream_unavailable")
        self.assertEqual(body["summary"]["candidates_returned"], 0)
        self.assertEqual(body["summary"]["costco_catalog"], "empty")
        self.assertEqual(body["summary"]["search_source"], "BRIGHTDATA")
        self.assertEqual(body["products"], [])
        hint = body["summary"]["upstream_hint"]
        self.assertIsNotNone(hint)
        self.assertIn("Bright Data search failed", hint)
        self.assertIn("SCANNER_SEARCH_SOURCE=CHOCODATA or SCAVIO", hint)

    def test_scavio_402_surfaces_credit_hint(self):
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=[]),
            patch.object(amazon_search, "load_cached_candidates", return_value=[]),
            patch.object(costco_client, "catalog_state", return_value="empty"),
            patch.object(
                main.amazon_search,
                "LAST_SEARCH_ERROR",
                'HTTP 402 {"error":"Insufficient credits","credit_balance":0}',
            ),
            patch.object(main.amazon_search, "SCANNER_SEARCH_SOURCE", "SCAVIO"),
            patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY),
        ]
        body = self._get(patches)
        self.assertEqual(body["status"], "upstream_unavailable")
        hint = body["summary"]["upstream_hint"]
        self.assertIsNotNone(hint)
        self.assertIn("Scavio is out of credits", hint)
        self.assertIn("dashboard.scavio.dev/billing", hint)

    def test_chocodata_insufficient_credits_hint(self):
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=[]),
            patch.object(amazon_search, "load_cached_candidates", return_value=[]),
            patch.object(costco_client, "catalog_state", return_value="empty"),
            patch.object(
                main.amazon_search,
                "LAST_SEARCH_ERROR",
                "HTTP 402 (insufficient credits)",
            ),
            patch.object(main.amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"),
            patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY),
        ]
        body = self._get(patches)
        self.assertEqual(body["status"], "upstream_unavailable")
        self.assertEqual(body["summary"]["search_source"], "CHOCODATA")
        hint = body["summary"]["upstream_hint"]
        self.assertIsNotNone(hint)
        self.assertIn("Chocodata is out of credits", hint)
        self.assertIn("app.chocodata.com", hint)

    def test_target_unreachable_surfaces_transient_hint(self):
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=[]),
            patch.object(amazon_search, "load_cached_candidates", return_value=[]),
            patch.object(costco_client, "catalog_state", return_value="empty"),
            patch.object(
                main.amazon_search,
                "LAST_SEARCH_ERROR",
                "HTTP 502 target_unreachable Amazon blocked every retry.",
            ),
            patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY),
        ]
        body = self._get(patches)
        self.assertEqual(body["status"], "upstream_unavailable")
        hint = body["summary"]["upstream_hint"]
        self.assertIsNotNone(hint)
        self.assertIn("temporarily blocking searches", hint)
        self.assertIn("not charged", hint)

    def test_costco_discovery_freshness_in_summary(self):
        candidates = [fake_candidate("B000000001", "Alpha", 48.87)]
        patches = ok_patches(
            candidates,
            {"B000000001": fake_offer(48.87, monthly_sales=1500)},
            {48.87: (20.0, 125.1)},
            {"B000000001": 1500},
        )
        body = self._get(patches)
        discovery = body["summary"]["costco_discovery"]
        self.assertEqual(discovery["freshness"], "fresh")
        self.assertEqual(discovery["status"], "ok")
        self.assertEqual(discovery["location"]["delivery_zip"], "75201")
        self.assertEqual(discovery["last_fetched_count"], 24)

    def test_sorting_order(self):
        candidates = [
            fake_candidate("B000000001", "High Profit Low ROI", 60.0),
            fake_candidate("B000000002", "Mid Profit High ROI", 50.0),
            fake_candidate("B000000003", "Low Profit", 30.0),
            fake_candidate("B000000004", "Unknown Sales", 40.0),
        ]
        offers = {
            "B000000001": fake_offer(60.0, monthly_sales=3000, monthly_sales_estimated=True),
            "B000000002": fake_offer(50.0, monthly_sales=1000, monthly_sales_estimated=False),
            "B000000003": fake_offer(30.0, monthly_sales=500, monthly_sales_estimated=True),
            "B000000004": fake_offer(40.0, monthly_sales=None, monthly_sales_estimated=True),
        }
        profits = {
            60.0: (25.0, 90.0),
            50.0: (18.0, 150.0),
            30.0: (5.0, 40.0),
            40.0: (12.0, 80.0),
        }
        patches = ok_patches(candidates, offers, profits, {})
        patches.append(patch.object(product_analysis, "get_costco_price", return_value=fake_costco(weight_lbs=3.5)))
        body = self._get(patches)

        names = [p["name"] for p in body["products"]]
        # net_profit desc first: 25, 18, 12, 5
        self.assertEqual(names, [
            "High Profit Low ROI",
            "Mid Profit High ROI",
            "Unknown Sales",
            "Low Profit",
        ])

    def test_sorting_order_without_fee_uses_sales_desc(self):
        """Without a verified fee the rows are provisional (grouped after
        estimated) and ordered by provisional profit then sales desc,
        never crashing."""
        candidates = [
            fake_candidate("B000000001", "High Velocity", 60.0),
            fake_candidate("B000000002", "Mid Velocity", 50.0),
            fake_candidate("B000000003", "Unknown Velocity", 30.0),
        ]
        offers = {
            "B000000001": fake_offer(60.0, monthly_sales=3000, monthly_sales_estimated=True),
            "B000000002": fake_offer(50.0, monthly_sales=500, monthly_sales_estimated=True),
            "B000000003": fake_offer(30.0, monthly_sales=None, monthly_sales_estimated=True),
        }
        patches = ok_patches(candidates, offers, {}, {})
        body = self._get(patches)

        names = [p["name"] for p in body["products"]]
        self.assertEqual(names, ["High Velocity", "Mid Velocity", "Unknown Velocity"])
        self.assertTrue(all(p["economics_status"] == "needs_fee_verification" for p in body["products"]))
        self.assertTrue(all(p["verdict"] == "Needs Fee Verification" for p in body["products"]))

    def test_economics_groups_order_estimated_provisional_unavailable(self):
        """Scout spec sort: Estimated first, Provisional second,
        Unavailable last; net profit desc within each group."""
        candidates = [
            fake_candidate("B000000001", "Estimated Low Profit", 60.0),
            fake_candidate("B000000002", "Estimated High Profit", 60.0),
            fake_candidate("B000000003", "Provisional High Profit", 50.0),
            fake_candidate("B000000004", "Unavailable", 30.0),
        ]
        offers = {
            "B000000001": fake_offer(60.0, monthly_sales=1000, monthly_sales_estimated=True),
            "B000000002": fake_offer(60.0, monthly_sales=1000, monthly_sales_estimated=True),
            "B000000003": fake_offer(50.0, monthly_sales=3000, monthly_sales_estimated=True),
            "B000000004": fake_offer(30.0, monthly_sales=5000, monthly_sales_estimated=True),
        }

        def economics_for(product, costco):
            price = product.get("amazon_price")
            if price == 60.0:
                net = 20.0 if product.get("asin") == "B000000002" else 12.0
                return fake_economics(net=net, roi=90.0, confidence="estimated", status="estimated_fee_stack")
            if price == 50.0:
                return fake_economics(net=18.0, roi=95.0)
            return fake_economics(net=None, roi=None, confidence="unavailable", status="missing_costco_cogs")

        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(
                offer_enrichment,
                "get_scanner_offer",
                side_effect=lambda identifier: offers[identifier.rsplit("/", 1)[-1]],
            ),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
            patch.object(product_analysis, "calculate_unit_economics", side_effect=economics_for),
            patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
            patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
            patch.object(costco_client, "catalog_state", return_value="ready"),
            patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY),
        ]
        body = self._get(patches)

        names = [p["name"] for p in body["products"]]
        groups = [p["economics_confidence"] for p in body["products"]]
        self.assertEqual(names, [
            "Estimated High Profit",      # estimated, net 20 first
            "Estimated Low Profit",       # estimated, net 12 second
            "Provisional High Profit",    # provisional group
            "Unavailable",                # unavailable group last
        ])
        self.assertEqual(groups, ["estimated", "estimated", "provisional", "unavailable"])

    def test_ranking_competition_then_demand_when_profit_ties(self):
        """Spec ranking: net profit desc, ROI desc, seller count asc,
        FBA seller count asc, then demand desc."""
        candidates = [
            fake_candidate("B000000001", "Crowded High FBA", 60.0),
            fake_candidate("B000000002", "Crowded Low FBA", 60.0),
            fake_candidate("B000000003", "Open Field", 60.0),
            fake_candidate("B000000004", "Open Field Low Demand", 60.0),
        ]
        offers = {
            "B000000001": fake_offer(60.0, monthly_sales=900, monthly_sales_estimated=True),
            "B000000002": fake_offer(60.0, monthly_sales=900, monthly_sales_estimated=True),
            "B000000003": fake_offer(60.0, monthly_sales=900, monthly_sales_estimated=True),
            "B000000004": fake_offer(60.0, monthly_sales=100, monthly_sales_estimated=True),
        }
        offers["B000000001"]["total_sellers"] = 9
        offers["B000000001"]["fba_sellers"] = 8
        offers["B000000002"]["total_sellers"] = 9
        offers["B000000002"]["fba_sellers"] = 1
        offers["B000000003"]["total_sellers"] = 2
        offers["B000000003"]["fba_sellers"] = 1
        offers["B000000004"]["total_sellers"] = 2
        offers["B000000004"]["fba_sellers"] = 1
        patches = ok_patches(candidates, offers, {60.0: (20.0, 90.0)}, {})
        patches.append(patch.object(product_analysis, "get_costco_price", return_value=fake_costco(weight_lbs=3.5)))
        body = self._get(patches)

        names = [p["name"] for p in body["products"]]
        self.assertEqual(names, ["Open Field", "Open Field Low Demand", "Crowded Low FBA", "Crowded High FBA"])

    def test_needs_fee_verification_verdict_when_no_fee(self):
        """Without a fee the candidate stays visible, ranked after qualified
        products, carrying the Needs Fee Verification verdict."""
        candidates = [
            fake_candidate("B000000001", "Has Fee", 60.0),
            fake_candidate("B000000002", "No Fee", 50.0),
        ]
        offers = {
            "B000000001": fake_offer(60.0, monthly_sales=3000, monthly_sales_estimated=True),
            "B000000002": fake_offer(50.0, monthly_sales=2500, monthly_sales_estimated=True),
        }
        patches = ok_patches(candidates, offers, {60.0: (20.0, 90.0)}, {})
        patches.append(patch.object(product_analysis, "get_costco_price", side_effect=[
            fake_costco(weight_lbs=3.5),
            fake_costco(),
        ]))
        body = self._get(patches)

        by_asin = {p["asin"]: p for p in body["products"]}
        self.assertIsNone(by_asin["B000000001"]["verdict"])
        self.assertEqual(by_asin["B000000002"]["verdict"], "Needs Fee Verification")
        self.assertIsNone(by_asin["B000000002"]["fba_fee"])
        # Provisional rows carry provisional numbers, never treated as final
        self.assertEqual(by_asin["B000000002"]["economics_status"], "needs_fee_verification")
        self.assertIsNotNone(by_asin["B000000002"]["net_profit"])
        # estimated (fee-present) product ranks first, provisional second
        self.assertEqual(body["products"][0]["asin"], "B000000001")
        self.assertEqual(body["products"][1]["asin"], "B000000002")

    def test_monthly_sales_estimated_flags_pass_through(self):
        candidates = [
            fake_candidate("B000000001", "Estimated Item", 48.87),
            fake_candidate("B000000002", "Not Estimated Item", 48.87),
        ]
        offers = {
            "B000000001": fake_offer(48.87, monthly_sales=2500, monthly_sales_estimated=True),
            "B000000002": fake_offer(48.87, monthly_sales=2500, monthly_sales_estimated=False),
        }
        patches = ok_patches(candidates, offers, {48.87: (20.0, 125.1)}, {})
        body = self._get(patches)

        flags = {p["asin"]: p["monthly_sales_estimated"] for p in body["products"]}
        self.assertIs(flags["B000000001"], True)
        self.assertIs(flags["B000000002"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
