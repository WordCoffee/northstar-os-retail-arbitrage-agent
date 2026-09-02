"""Mocked unit tests for the GET /api/kirkland/live response contract.

Never calls Scavio, Bright Data, Costco, Canopy, Easyparser, or any
external API. All pipeline inputs are mocked; the financial profile is
real for the need_cost_data case (B) and mocked for the other cases.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import os
import unittest
from unittest.mock import patch

import offer_enrichment
import product_analysis


def setUpModule():
    """Live-path tests: explicitly opt into SCANNER_LIVE_ALLOWED (the
    default-off gate). tearDownModule restores it for later modules."""
    os.environ["SCANNER_LIVE_ALLOWED"] = "1"


def tearDownModule():
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)


def fake_candidate(asin="B0CS6Z9SRX", name="Kirkland Signature K-Cups (120ct)", amazon_price=48.87):
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


def fake_costco(costco_cost=15.99, weight_lbs=3.5, match_quality="exact"):
    return {"costco_cost": costco_cost, "weight_lbs": weight_lbs, "match_quality": match_quality}


def fake_profile(status, profit, roi, gaps=()):
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


def fake_economics(net, roi):
    """Deterministic fee-engine economics dict for patching."""
    return {
        "amazon_category": None,
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
        "fba_fee_status": "available",
        "fba_fee_confidence": "table_estimate",
        "fba_fee_rule": "FBA-2026.1",
        "fba_fee_note": "test economics",
        "fba_weight_basis_lbs": 3.5,
        "inbound_cost_per_unit": 0.35,
        "prep_cost_per_unit": 0.25,
        "packaging_cost_per_unit": 0.0,
        "return_reserve_rate": 0.02,
        "net_profit": net,
        "roi_pct": roi,
        "economics_confidence": "estimated",
        "economics_status": "estimated_fee_stack",
        "economics_note": "test economics",
    }


def default_patches():
    """Mocks the three required pipeline inputs plus deterministic helpers.

    The profit screen thresholds are forced permissive so records are
    never dropped by unrelated environment values.
    """
    return [
        # Pin a non-OFF mode per call: another module imported later in the
        # same run (e.g. test_manual_import) may leave SCANNER_OFFER_ENRICHMENT
        # =OFF, which would route _candidates_for_mode() to the cache instead
        # of the mocked live search every test in this module depends on.
        patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False),
        patch.object(product_analysis, "search_kirkland_products", return_value=[fake_candidate()]),
        patch.object(offer_enrichment, "get_scanner_offer", return_value=fake_offer()),
        patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
        patch.object(
            product_analysis,
            "calculate_unit_economics",
            return_value=fake_economics(net=16.71, roi=104.5),
        ),
        patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
        patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
    ]


class TestLiveResponseContract(unittest.TestCase):
    def _run(self):
        return product_analysis.analyze_kirkland_products()["all_results"]

    def test_a_scored_complete_inputs_verdict_none_when_velocity_unavailable(self):
        patches = default_patches() + [
            patch.object(
                product_analysis,
                "estimate_financial_profile",
                return_value=fake_profile("scored", 12.5, 76.5),
            )
        ]
        with patches[0]:
            for p in patches[1:]:
                p.start()
            try:
                results = self._run()
            finally:
                for p in reversed(patches[1:]):
                    p.stop()

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["financial_status"], "scored")
        self.assertEqual(r["financial_decision_status"], "scored")
        self.assertIsInstance(r["projected_net_profit"], (int, float))
        self.assertGreater(r["projected_net_profit"], 0)
        self.assertIsInstance(r["projected_roi_pct"], (int, float))
        self.assertIsNone(r["verdict"])

    def test_b_missing_cost_data(self):
        """Real estimate_financial_profile: no explicit costs -> need_cost_data."""
        patches = default_patches()
        with patches[0]:
            for p in patches[1:]:
                p.start()
            try:
                results = self._run()
            finally:
                for p in reversed(patches[1:]):
                    p.stop()

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["financial_status"], "need_cost_data")
        self.assertEqual(r["financial_decision_status"], "need_cost_data")
        self.assertIsNone(r["projected_net_profit"])
        self.assertIsNone(r["projected_roi_pct"])
        self.assertIsNone(r["verdict"])

    def test_c_missing_fee_data(self):
        patches = default_patches() + [
            patch.object(
                product_analysis,
                "estimate_financial_profile",
                return_value=fake_profile("need_fee_data", None, None),
            )
        ]
        with patches[0]:
            for p in patches[1:]:
                p.start()
            try:
                results = self._run()
            finally:
                for p in reversed(patches[1:]):
                    p.stop()

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["financial_status"], "need_fee_data")
        self.assertEqual(r["financial_decision_status"], "need_fee_data")
        self.assertIsNone(r["projected_net_profit"])
        self.assertIsNone(r["projected_roi_pct"])
        self.assertIsNone(r["verdict"])

    def test_d_unprofitable_complete_inputs_verdict_none_without_velocity(self):
        patches = default_patches() + [
            patch.object(
                product_analysis,
                "calculate_unit_economics",
                return_value=fake_economics(net=-5.0, roi=-31.3),
            ),
            patch.object(
                product_analysis,
                "estimate_financial_profile",
                return_value=fake_profile("unprofitable", -3.0, -18.4),
            ),
        ]
        with patches[0]:
            for p in patches[1:]:
                p.start()
            try:
                results = self._run()
            finally:
                for p in reversed(patches[1:]):
                    p.stop()

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["financial_status"], "unprofitable")
        self.assertEqual(r["financial_decision_status"], "unprofitable")
        self.assertIsInstance(r["projected_net_profit"], (int, float))
        self.assertLessEqual(r["projected_net_profit"], 0)
        self.assertIsNone(r["verdict"])

    def test_e_verified_velocity_reuses_existing_catalog_rule(self):
        """With verified monthly sales, the existing Pass/Hold/Reject rule
        applies exactly; unverified velocity still yields verdict None."""
        candidates = [
            fake_candidate(asin="B000000001", name="Pass Item", amazon_price=48.87),
            fake_candidate(asin="B000000002", name="Hold Item", amazon_price=40.00),
            fake_candidate(asin="B000000003", name="Reject Item", amazon_price=30.00),
            fake_candidate(asin="B000000004", name="Unverified Item", amazon_price=48.87),
        ]
        offers = {
            "B000000001": fake_offer(amazon_price=48.87, monthly_sales=2500, monthly_sales_estimated=False),
            "B000000002": fake_offer(amazon_price=40.00, monthly_sales=1000, monthly_sales_estimated=False),
            "B000000003": fake_offer(amazon_price=30.00, monthly_sales=3000, monthly_sales_estimated=False),
            "B000000004": fake_offer(amazon_price=48.87, monthly_sales=2500, monthly_sales_estimated=True),
        }
        profits_by_price = {
            48.87: (20.0, 125.1),
            40.00: (12.0, 75.1),
            30.00: (-5.0, -31.3),
        }

        def offer_side(identifier):
            asin = identifier.rsplit("/", 1)[-1]
            return offers[asin]

        def economics_side(product, costco):
            price = product.get("amazon_price")
            net, roi = profits_by_price[price]
            return fake_economics(net=net, roi=roi)

        patches = [
            patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False),
            patch.object(product_analysis, "search_kirkland_products", return_value=candidates),
            patch.object(offer_enrichment, "get_scanner_offer", side_effect=offer_side),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
            patch.object(product_analysis, "calculate_unit_economics", side_effect=economics_side),
            patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
            patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
            patch.object(
                product_analysis,
                "estimate_financial_profile",
                return_value=fake_profile("scored", 12.5, 76.5),
            ),
        ]

        with patches[0]:
            for p in patches[1:]:
                p.start()
            try:
                results = self._run()
            finally:
                for p in reversed(patches[1:]):
                    p.stop()

        verdicts = {r["asin"]: r["verdict"] for r in results}
        self.assertEqual(verdicts["B000000001"], "Pass")
        self.assertEqual(verdicts["B000000002"], "Hold")
        self.assertEqual(verdicts["B000000003"], "Reject")
        self.assertIsNone(verdicts["B000000004"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
