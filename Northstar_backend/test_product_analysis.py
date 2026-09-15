"""Mocked unit tests for the product_analysis pipeline under the
item_name,costco_cost contract (weight no longer required).

No external APIs are touched: Scavio, Bright Data, Costco, Canopy and
Easyparser are all mocked here.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import os
import unittest
from unittest.mock import patch

import offer_enrichment
import product_analysis
from pricing import screen_by_profit_tier


def setUpModule():
    """Live-path tests: explicitly opt into SCANNER_LIVE_ALLOWED (the
    default-off gate). tearDownModule restores it for later modules."""
    os.environ["SCANNER_LIVE_ALLOWED"] = "1"


def tearDownModule():
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)


def fake_candidate(asin, name, amazon_price=48.87):
    return {
        "name": name,
        "product_url": f"https://www.amazon.com/dp/{asin}",
        "asin": asin,
        "amazon_price": amazon_price,
    }


def fake_offer(amazon_price=48.87, monthly_sales=None, monthly_sales_estimated=True):
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


def fake_costco(costco_cost=15.99, weight_lbs=None, match_quality="exact", match_reason=None, costco_cost_basis=None, source=None):
    row = {
        "costco_cost": costco_cost,
        "costco_cost_basis": costco_cost_basis or ("estimated" if match_quality in ("exact", "high_confidence") else "candidate_match"),
        "match_quality": match_quality,
        "match_reason": match_reason,
    }
    if source is not None:
        row["source"] = source
    if weight_lbs is not None:
        row["weight_lbs"] = weight_lbs
    return row


def fake_profile():
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
        "projected_net_profit": None,
        "projected_roi_pct": None,
        "financial_status": "need_cost_data",
        "financial_data_gaps": ["costco_cost"],
    }


def fake_economics(net=20.0, roi=90.0, confidence="estimated", status="estimated_fee_stack"):
    """Deterministic fee-engine economics dict for patching."""
    return {
        "amazon_category": None,
        "costco_cogs": 15.99,
        "costco_cost_basis": "estimated",
        "referral_fee": 7.33,
        "referral_fee_rate": 0.15,
        "referral_fee_category": "Everything Else",
        "referral_fee_confidence": "default_category",
        "referral_fee_rule": "REF-2026.1-Everything Else",
        "referral_fee_tier": "15% of sale price",
        "referral_fee_note": "default category applied",
        "fba_base_fee": 7.92,
        "fba_fuel_logistics_surcharge": 0.28,
        "fba_size_tier": "standard",
        "fba_fee_status": "available",
        "fba_fee_confidence": "table_estimate",
        "fba_fee_rule": "FBA-2026.1",
        "fba_fee_note": "table estimate",
        "fba_weight_basis_lbs": 3.5,
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


class AnalyzeWithoutFeeTests(unittest.TestCase):
    def run_scan(self, candidates, costco_rows=None, min_roi=None, min_margin=None):
        # Pin a non-OFF enrichment mode per call so search_kirkland_products
        # is actually used: another module imported earlier in the same run
        # (e.g. test_manual_import) may have left SCANNER_OFFER_ENRICHMENT=OFF
        # at import time, which would route _candidates_for_mode() to the
        # cache instead and silently empty every result.
        with patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False):
            patches = [
                patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
                patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer()),
                patch.object(product_analysis, "get_costco_price", side_effect=costco_rows),
                patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
                patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0 if min_roi is None else min_roi),
                patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0 if min_margin is None else min_margin),
            ]
            for p in patches:
                p.start()
            try:
                return product_analysis.analyze_kirkland_products()
            finally:
                for p in reversed(patches):
                    p.stop()

    def test_candidate_kept_without_fba_fee(self):
        result = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Item", 48.87)],
            costco_rows=[fake_costco()],
        )
        self.assertEqual(len(result["all_results"]), 1)
        p = result["all_results"][0]
        self.assertIsNone(p["fba_fee"])
        # Provisional economics: price + COGS with the FBA fee excluded,
        # never treated as final and never displayed without the badge.
        self.assertEqual(p["economics_confidence"], "provisional")
        self.assertEqual(p["economics_status"], "needs_fee_verification")
        self.assertIsNotNone(p["net_profit"])
        self.assertIsNotNone(p["roi_pct"])
        self.assertEqual(p["verdict"], "Needs Fee Verification")
        self.assertIsNone(p["profit_tier"])
        self.assertEqual(p["costco_cost"], 15.99)
        self.assertEqual(p["amazon_price"], 48.87)

    def test_missing_offer_and_candidate_price_stays_none(self):
        """No price from the offer AND no price from the candidate: the row
        is kept (research view) with amazon_price None — never a TypeError
        on `None > 0` and never a fabricated $0.00."""
        with patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False):
            patches = [
                patch.object(product_analysis, "search_kirkland_products", return_value=[fake_candidate("B000000008", "No Price Item", None)]),
                patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer(amazon_price=None)),
                patch.object(product_analysis, "get_costco_price", side_effect=[fake_costco()]),
                patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
                patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
                patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
            ]
            for p in patches:
                p.start()
            try:
                result = product_analysis.analyze_kirkland_products()
            finally:
                for p in reversed(patches):
                    p.stop()

        self.assertEqual(len(result["all_results"]), 1)
        r = result["all_results"][0]
        self.assertIsNone(r["amazon_price"], "missing price stays None, never 0")
        self.assertIsNone(r["net_profit"])
        self.assertIsNone(r["roi_pct"])
        self.assertEqual(r["economics_status"], "missing_amazon_price")

    def test_offer_price_zero_falls_back_to_candidate_price(self):
        """Documented fallback: a non-positive offer price (offline
        placeholder sentinel 0) falls back to the candidate's own price."""
        with patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False):
            patches = [
                patch.object(product_analysis, "search_kirkland_products", return_value=[fake_candidate("B000000008", "Kirkland Item", 48.87)]),
                patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer(amazon_price=0)),
                patch.object(product_analysis, "get_costco_price", side_effect=[fake_costco()]),
                patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
                patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
                patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
            ]
            for p in patches:
                p.start()
            try:
                result = product_analysis.analyze_kirkland_products()
            finally:
                for p in reversed(patches):
                    p.stop()

        self.assertEqual(len(result["all_results"]), 1)
        self.assertEqual(result["all_results"][0]["amazon_price"], 48.87)

    def test_candidate_match_row_keeps_provisional_economics_no_tier(self):
        """A candidate-only COGS match surfaces as a research candidate with
        its computed price + COGS economics visible as **provisional**
        (mapping_verification_required, no tier, no verdict, never
        purchase-authorized): the numbers are directional research
        estimates to triage, not final — never nulled, never hidden."""
        result = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Item", 48.87)],
            costco_rows=[fake_costco(match_quality="candidate", match_reason="Pack/count cannot be confirmed.")],
        )
        self.assertEqual(len(result["all_results"]), 1)
        p = result["all_results"][0]
        self.assertEqual(p["pack_match"], "candidate")
        self.assertEqual(p["costco_cost_basis"], "candidate_match")
        self.assertEqual(p["economics_confidence"], "provisional")
        self.assertEqual(p["economics_status"], "mapping_verification_required")
        self.assertIn("candidate match only", p["economics_note"])
        self.assertIn("Pack/count cannot be confirmed", p["economics_note"])
        # Computed economics stay visible for triage — provisional, never nulled.
        self.assertIsNotNone(p["net_profit"])
        self.assertIsNotNone(p["roi_pct"])
        self.assertIsNone(p["profit_tier"])
        self.assertIsNone(p["verdict"])
        self.assertIs(p["cost_is_purchase_authorized"], False)

    def test_mismatch_row_is_blocked_with_reason(self):
        """The three misleading shortlist rows (flavor/weight/pack swaps)
        must classify as mismatch: cost present for research with computed
        economics surfaced as provisional (mapping_verification_required),
        no tier, no verdict."""
        result = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Adult Formula Chicken, Rice and Vegetable Dog Food 40 lb", 88.99)],
            costco_rows=[fake_costco(match_quality="mismatch", match_reason="Net weight differs (40 vs 25 lb); Formula/flavor differs (chicken vs lamb).")],
        )
        p = result["all_results"][0]
        self.assertEqual(p["pack_match"], "mismatch")
        self.assertEqual(p["costco_cost_basis"], "candidate_match")
        self.assertEqual(p["economics_confidence"], "provisional")
        self.assertEqual(p["economics_status"], "mapping_verification_required")
        self.assertIsNotNone(p["net_profit"])
        self.assertIsNotNone(p["roi_pct"])
        self.assertIsNone(p["profit_tier"])
        self.assertIsNone(p["verdict"])

    def test_exact_match_row_keeps_estimated_economics(self):
        """Only an exact fingerprint match keeps estimated economics,
        tiers, and Pass eligibility."""
        result = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Signature Dental Chews 72 ct", 48.87)],
            costco_rows=[fake_costco(match_quality="exact")],
        )
        p = result["all_results"][0]
        self.assertEqual(p["pack_match"], "exact")
        self.assertEqual(p["costco_cost_basis"], "estimated")
        self.assertEqual(p["economics_confidence"], "provisional")
        self.assertIsNotNone(p["net_profit"])
        self.assertEqual(p["verdict"], "Needs Fee Verification")

    def test_invoice_confirmed_row_keeps_economics(self):
        """An invoice-confirmed COGS (real paid price, exact fingerprint)
        passes the Pack/Variant gate like an exact match and carries the
        invoice basis through the economics."""
        result = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Signature Dental Chews 72 ct", 48.87)],
            costco_rows=[fake_costco(
                match_quality="invoice_confirmed",
                costco_cost=27.5,
                costco_cost_basis="invoice_confirmed",
                match_reason="Invoice INV-200 (2026-08-01) confirms the exact item (fingerprint match).",
            )],
        )
        p = result["all_results"][0]
        self.assertEqual(p["pack_match"], "invoice_confirmed")
        self.assertEqual(p["costco_cost"], 27.5)
        self.assertEqual(p["costco_cost_basis"], "invoice_confirmed")
        self.assertEqual(p["economics_confidence"], "provisional")
        self.assertIsNotNone(p["net_profit"])
        self.assertEqual(p["verdict"], "Needs Fee Verification")

    def test_listing_fba_fee_takes_priority_over_weight_estimate(self):
        offer = fake_offer()
        offer["fba_fee"] = 9.25
        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        patches = [
            # Pin a non-OFF mode per call: another module imported earlier in
            # the same run may have left SCANNER_OFFER_ENRICHMENT=OFF, which
            # would route _candidates_for_mode() to the cache instead.
            patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False),
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(offer_enrichment, "get_scanner_offer", return_value=offer),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco(weight_lbs=3.5)),
            patch.object(
                product_analysis,
                "calculate_unit_economics",
                return_value=fake_economics(net=10.0, roi=62.5),
            ),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
            patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
            patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
        ]
        for p in patches:
            p.start()
        try:
            result = product_analysis.analyze_kirkland_products()
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(result["all_results"][0]["fba_fee"], 9.25)
        self.assertEqual(result["all_results"][0]["net_profit"], 10.0)

    def test_listing_fee_zero_or_invalid_is_ignored(self):
        offer = fake_offer()
        offer["fba_fee"] = 0
        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(offer_enrichment, "get_scanner_offer", return_value=offer),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
            patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
            patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
        ]
        for p in patches:
            p.start()
        try:
            result = product_analysis.analyze_kirkland_products()
        finally:
            for p in reversed(patches):
                p.stop()
        p = result["all_results"][0]
        self.assertIsNone(p["fba_fee"])
        self.assertEqual(p["economics_confidence"], "provisional")
        self.assertEqual(p["verdict"], "Needs Fee Verification")

    def test_legacy_weight_estimate_still_applies_without_listing_fee(self):
        result = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Item", 48.87)],
            costco_rows=[fake_costco(weight_lbs=3.5)],
        )
        p = result["all_results"][0]
        self.assertEqual(p["fba_fee"], 8.20)
        self.assertEqual(p["economics_confidence"], "estimated")
        self.assertEqual(p["economics_status"], "estimated_fee_stack")
        self.assertIsNotNone(p["net_profit"])
        self.assertNotEqual(p["verdict"], "Needs Fee Verification")

    def test_category_metadata_from_offer_passed_to_fee_engine(self):
        """The parsed category / browse node must reach the fee engine —
        not the old hardcoded None — or Default 15% is all we ever get."""
        offer = fake_offer()
        offer["amazon_category"] = "Pet Supplies"
        offer["browse_node_id"] = 2619533011
        offer["category_source_hint"] = "breadcrumb"
        captured = {}

        def probe(product, costco):
            captured.update(product)
            return fake_economics()

        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        patches = [
            patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False),
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(offer_enrichment, "get_scanner_offer", return_value=offer),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
            patch.object(product_analysis, "calculate_unit_economics", side_effect=probe),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
            patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
            patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
        ]
        for p in patches:
            p.start()
        try:
            product_analysis.analyze_kirkland_products()
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(captured["amazon_category"], "Pet Supplies")
        self.assertEqual(captured["browse_node"], 2619533011)
        self.assertEqual(captured["category_source_hint"], "breadcrumb")

    def test_offer_without_category_metadata_passes_nulls(self):
        """No category metadata on the offer -> the fee engine receives
        None (not a fabricated value) and keeps the Default 15% path."""
        captured = {}

        def probe(product, costco):
            captured.update(product)
            return fake_economics()

        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer()),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
            patch.object(product_analysis, "calculate_unit_economics", side_effect=probe),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
        ]
        for p in patches:
            p.start()
        try:
            product_analysis.analyze_kirkland_products()
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertIsNone(captured["amazon_category"])
        self.assertIsNone(captured["browse_node"])
        self.assertIsNone(captured["category_source_hint"])

    def test_economics_called_even_without_fee_but_never_fabricates_fba(self):
        """Economics runs for every candidate (provisional tier), but the
        FBA fee must stay None — never invented — when there is no
        listing fee and no weight."""

        def economics_probe(product, costco):
            self.assertIsNone(product.get("listing_fba_fee"))
            return fake_economics(
                net=12.0,
                roi=75.0,
                confidence="provisional",
                status="needs_fee_verification",
            )

        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer()),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
            patch.object(product_analysis, "calculate_unit_economics", side_effect=economics_probe),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
        ]
        for p in patches:
            p.start()
        try:
            result = product_analysis.analyze_kirkland_products()
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(len(result["all_results"]), 1)
        self.assertIsNone(result["all_results"][0]["fba_fee"])

    def test_candidate_kept_without_costco_match(self):
        result = self.run_scan(
            [fake_candidate("B000000001", "No Catalog Match", 48.87)],
            costco_rows=[None],
        )
        self.assertEqual(len(result["all_results"]), 1)
        p = result["all_results"][0]
        self.assertIsNone(p["costco_cost"])
        self.assertIsNone(p["fba_fee"])
        self.assertIsNone(p["net_profit"])
        self.assertIsNone(p["roi_pct"])
        self.assertEqual(p["pack_match"], "unknown")
        self.assertEqual(p["economics_status"], "missing_costco_cogs")
        # Honest economics: a row with no Costco cost keeps its
        # missing_costco_cogs status and gets no verdict — it is never
        # labeled mapping_verification_required and never Needs Fee
        # Verification (that label requires a cost to verify against).
        self.assertIsNone(p["verdict"])

    def test_high_confidence_row_keeps_estimated_economics(self):
        """A high-confidence match (strong normalized title identity, no
        known fingerprint conflict) exposes the research cost and existing
        ROI/profit calculations but is never a purchase authorization."""
        result = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Signature Dental Chews", 48.87)],
            costco_rows=[fake_costco(
                match_quality="high_confidence",
                match_reason="Strong normalized title identity (90%); Amazon carries no weight/pack/UPC evidence and none conflicts.",
                source="csv",
            )],
        )
        p = result["all_results"][0]
        self.assertEqual(p["pack_match"], "high_confidence")
        self.assertEqual(p["costco_cost_basis"], "estimated")
        self.assertEqual(p["cost_source"], "csv")
        self.assertEqual(p["cost_match_reason"], "Strong normalized title identity (90%); Amazon carries no weight/pack/UPC evidence and none conflicts.")
        self.assertIs(p["cost_is_purchase_authorized"], False)
        self.assertEqual(p["economics_confidence"], "provisional")
        self.assertIsNotNone(p["net_profit"])
        self.assertIsNotNone(p["roi_pct"])
        self.assertEqual(p["verdict"], "Needs Fee Verification")

    def test_invoice_confirmed_row_authorizes_purchase_only(self):
        """Only invoice-confirmed rows carry cost_is_purchase_authorized;
        exact and high_confidence rows are research costs."""
        result = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Signature Dental Chews 72 ct", 48.87)],
            costco_rows=[fake_costco(
                match_quality="invoice_confirmed",
                costco_cost=27.5,
                costco_cost_basis="invoice_confirmed",
                match_reason="Invoice INV-200 (2026-08-01) confirms the exact item (fingerprint match).",
                source="business_center_invoice",
            )],
        )
        p = result["all_results"][0]
        self.assertIs(p["cost_is_purchase_authorized"], True)
        self.assertEqual(p["cost_source"], "business_center_invoice")

        result_exact = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Signature Dental Chews 72 ct", 48.87)],
            costco_rows=[fake_costco(match_quality="exact", source="csv")],
        )
        self.assertIs(result_exact["all_results"][0]["cost_is_purchase_authorized"], False)
        self.assertEqual(result_exact["all_results"][0]["cost_source"], "csv")

    def test_url_only_candidate_never_enriches(self):
        """A search hit without an ASIN (listing URL only) must not call a
        billed provider, stays in the research view, and keeps the listing
        URL so the UI can still link to it."""
        url_only = fake_candidate("B000000001", "Url Only Kirkland Item", 48.87)
        url_only["asin"] = None
        with patch.object(product_analysis, "search_kirkland_products", return_value=[url_only]), \
             patch.object(offer_enrichment, "_enrichment_mode", return_value="BRIGHTDATA"), \
             patch.object(offer_enrichment, "get_scanner_offer") as enrich_mock, \
             patch.object(offer_enrichment, "_offline_offer", return_value={
                 "amazon_price": 0, "lowest_price": None, "highest_price": None,
                 "total_sellers": None, "fba_sellers": None, "fba_sellers_estimated": False,
                 "monthly_sales_estimate": None, "monthly_sales_estimated": False, "fba_fee": None,
             }) as offline_mock, \
             patch.object(product_analysis, "get_costco_price",
                          return_value=fake_costco(costco_cost=15.99, match_quality="candidate")):
            result = product_analysis.analyze_kirkland_products()
        enrich_mock.assert_not_called()
        offline_mock.assert_called_once_with("https://www.amazon.com/dp/B000000001")
        self.assertEqual(len(result["all_results"]), 1)
        p = result["all_results"][0]
        self.assertIsNone(p["asin"])
        self.assertEqual(p["product_url"], "https://www.amazon.com/dp/B000000001")
        self.assertEqual(p["pack_match"], "candidate")
        self.assertEqual(p["economics_status"], "mapping_verification_required")

    def test_candidates_deduped_by_asin(self):
        dupes = [
            fake_candidate("B000000001", "Kirkland Item", 48.87),
            fake_candidate("B000000001", "Kirkland Item Duplicate", 48.87),
            fake_candidate("B000000002", "Second Item", 40.00),
        ]
        result = self.run_scan(dupes, costco_rows=[fake_costco(), fake_costco(), fake_costco()])
        asins = [p["asin"] for p in result["all_results"]]
        self.assertEqual(asins, ["B000000001", "B000000002"])

    def test_candidates_without_identifier_dropped(self):
        ghost = {"name": "No Identifier"}
        result = self.run_scan([ghost, fake_candidate("B000000001", "Kirkland Item", 48.87)],
                               costco_rows=[fake_costco(), fake_costco()])
        self.assertEqual([p["asin"] for p in result["all_results"]], ["B000000001"])

    def test_roi_threshold_not_applied_when_roi_unverified(self):
        """Provisional/unavailable rows are never dropped by a threshold
        they cannot truthfully satisfy."""
        result = self.run_scan(
            [fake_candidate("B000000001", "Kirkland Item", 48.87)],
            costco_rows=[fake_costco()],
            min_roi=90.0,
            min_margin=50.0,
        )
        self.assertEqual(len(result["all_results"]), 1)
        p = result["all_results"][0]
        self.assertEqual(p["economics_confidence"], "provisional")
        self.assertIsNotNone(p["roi_pct"])

    def test_negative_roi_estimated_row_kept_and_flagged(self):
        """Estimated rows below the ROI minimum are never silently dropped:
        they stay visible for operator triage with roi_below_minimum=True."""
        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer()),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
            patch.object(
                product_analysis,
                "calculate_unit_economics",
                return_value=fake_economics(
                    net=-5.0, roi=-25.0,
                    confidence="estimated", status="estimated_fee_stack",
                ),
            ),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
            patch.object(product_analysis, "MIN_ROI_PERCENT", 0.0),
            patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", 0.0),
        ]
        for p in patches:
            p.start()
        try:
            result = product_analysis.analyze_kirkland_products()
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(len(result["all_results"]), 1)
        p = result["all_results"][0]
        self.assertEqual(p["economics_confidence"], "estimated")
        self.assertEqual(p["net_profit"], -5.0)
        self.assertEqual(p["roi_pct"], -25.0)
        self.assertIs(p.get("roi_below_minimum"), True)

    def test_no_roi_threshold_by_default_never_flags(self):
        """With no configured MIN_ROI/MIN_MARGIN (None = the unset default),
        negative-ROI estimated rows stay visible and are NOT flagged:
        there is no minimum or maximum ROI unless the operator sets one."""
        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        patches = [
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer()),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
            patch.object(
                product_analysis,
                "calculate_unit_economics",
                return_value=fake_economics(
                    net=-5.0, roi=-25.0,
                    confidence="estimated", status="estimated_fee_stack",
                ),
            ),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
            patch.object(product_analysis, "MIN_ROI_PERCENT", None),
            patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", None),
        ]
        for p in patches:
            p.start()
        try:
            result = product_analysis.analyze_kirkland_products()
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(len(result["all_results"]), 1)
        p = result["all_results"][0]
        self.assertEqual(p["economics_confidence"], "estimated")
        self.assertEqual(p["roi_pct"], -25.0)
        self.assertNotIn("roi_below_minimum", p)

    def test_sort_handles_mixed_null_and_numeric_profits(self):
        candidates = [
            fake_candidate("B000000001", "With Fee", 60.0),
            fake_candidate("B000000002", "Without Fee", 50.0),
        ]
        costco_rows = [fake_costco(costco_cost=15.99, weight_lbs=3.5), fake_costco()]

        patches = [
            patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False),
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(
                offer_enrichment,
                "get_scanner_offer",
                side_effect=lambda i: fake_offer(amazon_price=(60.0 if "1" in i else 50.0)),
            ),
            patch.object(product_analysis, "get_costco_price", side_effect=costco_rows),
            patch.object(
                product_analysis,
                "calculate_unit_economics",
                return_value=fake_economics(net=20.0, roi=90.0),
            ),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
        ]
        for p in patches:
            p.start()
        try:
            result = product_analysis.analyze_kirkland_products()
        finally:
            for p in reversed(patches):
                p.stop()
        names = [r["name"] for r in result["all_results"]]
        self.assertEqual(len(names), 2)
        self.assertEqual(names[0], "With Fee")


class ChocodataGatingAndFallbackTests(unittest.TestCase):
    def test_chocodata_mode_skips_enrichment_without_costco_match(self):
        candidate = fake_candidate("B000000001", "Kirkland Item", 48.87)
        candidate["monthly_sales_estimate"] = 5000.0
        candidate["monthly_sales_estimated"] = True
        candidates = [candidate]
        with patch.object(product_analysis, "search_kirkland_products", return_value=candidates), \
             patch.object(offer_enrichment, "_enrichment_mode", return_value="CHOCODATA"), \
             patch.object(offer_enrichment, "get_scanner_offer") as enrich_mock, \
             patch.object(offer_enrichment, "_offline_offer", return_value={
                 "amazon_price": 0, "lowest_price": None, "highest_price": None,
                 "total_sellers": None, "fba_sellers": None, "fba_sellers_estimated": False,
                 "lowest_price_seller_type": "unknown", "highest_price_seller_type": "unknown",
                 "monthly_sales_estimate": None, "monthly_sales_estimated": False, "fba_fee": None,
             }) as offline_mock, \
             patch.object(product_analysis, "get_costco_price", return_value=None):
            product_analysis.analyze_kirkland_products()
        enrich_mock.assert_not_called()
        offline_mock.assert_called_once_with("https://www.amazon.com/dp/B000000001")

    def test_chocodata_mode_enriches_when_costco_match_exists(self):
        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        with patch.object(product_analysis, "search_kirkland_products", return_value=candidates), \
             patch.object(offer_enrichment, "_enrichment_mode", return_value="CHOCODATA"), \
             patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer()) as enrich_mock, \
             patch.object(product_analysis, "get_costco_price", return_value=fake_costco()):
            product_analysis.analyze_kirkland_products()
        enrich_mock.assert_called_once_with("https://www.amazon.com/dp/B000000001")

    def test_candidate_monthly_sales_used_when_offer_has_none(self):
        candidate = fake_candidate("B000000001", "Kirkland Item", 48.87)
        candidate["monthly_sales_estimate"] = 5000.0
        candidate["monthly_sales_estimated"] = True
        offer = fake_offer(monthly_sales=None)
        with patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False), \
             patch.object(product_analysis, "search_kirkland_products", return_value=[candidate]), \
             patch.object(offer_enrichment, "get_scanner_offer", return_value=offer), \
             patch.object(product_analysis, "get_costco_price", return_value=fake_costco()):
            result = product_analysis.analyze_kirkland_products()
        product = result["all_results"][0]
        self.assertEqual(product["monthly_sales_estimate"], 5000.0)
        self.assertIs(product["monthly_sales_estimated"], True)


class EnrichmentCreditGatingTests(unittest.TestCase):
    """Per-ASIN enrichment credits are only spent where the row can score:
    a Costco cost exists AND the Pack/Variant match passes the
    purchase-analysis gate (exact, invoice-confirmed, or
    high-confidence). Candidate/mismatch/unknown rows are research view
    only and must never call a billed provider."""

    def _run(self, costco_row):
        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        with patch.object(product_analysis, "search_kirkland_products", return_value=candidates), \
             patch.object(offer_enrichment, "_enrichment_mode", return_value="BRIGHTDATA"), \
             patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer()) as enrich_mock, \
             patch.object(offer_enrichment, "_offline_offer", return_value={
                 "amazon_price": 0, "lowest_price": None, "highest_price": None,
                 "total_sellers": None, "fba_sellers": None, "fba_sellers_estimated": False,
                 "monthly_sales_estimate": None, "monthly_sales_estimated": False, "fba_fee": None,
             }) as offline_mock, \
             patch.object(product_analysis, "get_costco_price", return_value=costco_row):
            product_analysis.analyze_kirkland_products()
        return enrich_mock, offline_mock

    def test_candidate_match_never_enriches(self):
        enrich_mock, offline_mock = self._run(
            fake_costco(costco_cost=15.99, match_quality="candidate")
        )
        enrich_mock.assert_not_called()
        offline_mock.assert_called_once_with("https://www.amazon.com/dp/B000000001")

    def test_mismatch_match_never_enriches(self):
        enrich_mock, offline_mock = self._run(
            fake_costco(costco_cost=31.67, match_quality="mismatch")
        )
        enrich_mock.assert_not_called()
        offline_mock.assert_called_once()

    def test_unknown_match_never_enriches(self):
        enrich_mock, offline_mock = self._run(
            fake_costco(costco_cost=20.0, match_quality="unknown")
        )
        enrich_mock.assert_not_called()
        offline_mock.assert_called_once()

    def test_invoice_confirmed_enriches(self):
        enrich_mock, offline_mock = self._run(
            fake_costco(costco_cost=29.99, match_quality="invoice_confirmed", match_reason="Invoice INV-77 confirms the exact item (fingerprint match)")
        )
        offline_mock.assert_not_called()
        enrich_mock.assert_called_once_with("https://www.amazon.com/dp/B000000001")

    def test_high_confidence_enriches(self):
        """High-confidence rows pass the scoreable gate: a Costco cost
        exists AND the Pack/Variant match is high-confidence, so the
        billed enrichment is justified (the row can compute net/ROI)."""
        enrich_mock, offline_mock = self._run(
            fake_costco(
                costco_cost=15.99,
                match_quality="high_confidence",
                match_reason="Strong normalized title identity (92%); Costco carries no weight/pack/UPC evidence and none conflicts.",
            )
        )
        offline_mock.assert_not_called()
        enrich_mock.assert_called_once_with("https://www.amazon.com/dp/B000000001")

    def test_exact_match_still_enriches(self):
        enrich_mock, offline_mock = self._run(fake_costco())
        offline_mock.assert_not_called()
        enrich_mock.assert_called_once_with("https://www.amazon.com/dp/B000000001")

    def test_no_costco_cost_never_enriches(self):
        enrich_mock, offline_mock = self._run(None)
        enrich_mock.assert_not_called()
        offline_mock.assert_called_once_with("https://www.amazon.com/dp/B000000001")

    def test_off_mode_never_calls_live_provider(self):
        candidates = [fake_candidate("B000000001", "Kirkland Item", 48.87)]
        with patch.object(product_analysis, "search_kirkland_products", return_value=candidates), \
             patch.object(offer_enrichment, "_enrichment_mode", return_value="OFF"), \
             patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer()) as enrich_mock, \
             patch.object(offer_enrichment, "_offline_offer", return_value={
                 "amazon_price": 0, "lowest_price": None, "highest_price": None,
                 "total_sellers": None, "fba_sellers": None, "fba_sellers_estimated": False,
                 "monthly_sales_estimate": None, "monthly_sales_estimated": False, "fba_fee": None,
             }) as offline_mock, \
             patch.object(product_analysis, "get_costco_price", return_value=fake_costco()):
            product_analysis.analyze_kirkland_products()
        enrich_mock.assert_not_called()
        offline_mock.assert_called_once()


class ScreenByProfitTierGuardTests(unittest.TestCase):
    def test_none_profits_do_not_crash(self):
        tier, matches = screen_by_profit_tier(
            [{"net_profit": None}, {"net_profit": 12.0}, {"net_profit": "8"}, {"net_profit": 5}],
        )
        self.assertEqual(tier, 11)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["net_profit"], 12.0)

    def test_no_matches_returns_none(self):
        tier, matches = screen_by_profit_tier([{"net_profit": None}, {"net_profit": 2.0}])
        self.assertIsNone(tier)
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
