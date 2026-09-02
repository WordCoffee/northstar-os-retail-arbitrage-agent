import test_network_guard  # noqa: F401  (blocks real network calls)
import unittest

import finance as f
import pricing


def full_inputs():
    """All explicit inputs for the catalog's K-Cups ASIN (B0CS6Z9SRX)."""
    return {
        "amazon_price": 48.87,
        "weight_lbs": 3.5,
        "costco_cost": 15.99,
        "prep_cost": 0.0,
        "inbound_shipping_cost": 0.35,
        "referral_rate": 0.15,
    }


class TestExplicitInputContract(unittest.TestCase):
    def test_default_call_has_no_scored_result(self):
        r = pricing.estimate_financial_profile(amazon_price=48.87, weight_lbs=3.5, costco_cost=15.99)
        self.assertEqual(r["financial_status"], f.STATUS_NEED_COST_DATA)
        self.assertIsNone(r["projected_net_profit"])
        self.assertIsNone(r["projected_roi_pct"])
        self.assertIsNone(r["prep_cost"])
        self.assertIsNone(r["inbound_shipping_cost"])
        self.assertIsNone(r["referral_fee"])
        self.assertTrue(any("prep_cost is missing" in g for g in r["financial_data_gaps"]))
        self.assertTrue(any("inbound_shipping_cost is missing" in g for g in r["financial_data_gaps"]))
        self.assertTrue(any("referral_fee is missing" in g for g in r["financial_data_gaps"]))

    def test_omitted_prep_means_need_cost_data_not_scored(self):
        r = pricing.estimate_financial_profile(
            amazon_price=48.87, weight_lbs=3.5, costco_cost=15.99,
            prep_cost=None, inbound_shipping_cost=0.35, referral_rate=0.15,
        )
        self.assertEqual(r["financial_status"], f.STATUS_NEED_COST_DATA)
        self.assertIsNone(r["projected_net_profit"])
        self.assertIsNone(r["projected_roi_pct"])
        self.assertIsNone(r["prep_cost"])
        self.assertTrue(any("prep_cost is missing" in g for g in r["financial_data_gaps"]))

    def test_omitted_inbound_means_need_cost_data_not_scored(self):
        r = pricing.estimate_financial_profile(
            amazon_price=48.87, weight_lbs=3.5, costco_cost=15.99,
            prep_cost=0.0, inbound_shipping_cost=None, referral_rate=0.15,
        )
        self.assertEqual(r["financial_status"], f.STATUS_NEED_COST_DATA)
        self.assertIsNone(r["projected_net_profit"])
        self.assertIsNone(r["projected_roi_pct"])
        self.assertIsNone(r["inbound_shipping_cost"])
        self.assertTrue(any("inbound_shipping_cost is missing" in g for g in r["financial_data_gaps"]))

    def test_omitted_referral_means_need_fee_data_not_scored(self):
        r = pricing.estimate_financial_profile(
            amazon_price=48.87, weight_lbs=3.5, costco_cost=15.99,
            prep_cost=0.0, inbound_shipping_cost=0.35,
        )
        self.assertEqual(r["financial_status"], f.STATUS_NEED_FEE_DATA)
        self.assertIsNone(r["projected_net_profit"])
        self.assertIsNone(r["projected_roi_pct"])
        self.assertIsNone(r["referral_fee"])
        self.assertTrue(any("referral_fee is missing" in g for g in r["financial_data_gaps"]))

    def test_explicit_zero_prep_is_valid_and_documented(self):
        r = pricing.estimate_financial_profile(**full_inputs())
        self.assertEqual(r["financial_status"], f.STATUS_SCORED)
        self.assertEqual(r["prep_cost"], 0.0)
        self.assertAlmostEqual(r["projected_net_profit"], 17.00, places=2)
        self.assertAlmostEqual(r["projected_roi_pct"], 104.04, places=1)
        self.assertIn(
            "Prep cost uses a user-entered planning assumption: $0.00/unit.",
            r["financial_data_gaps"],
        )

    def test_explicit_inbound_035_is_valid_and_documented(self):
        r = pricing.estimate_financial_profile(**full_inputs())
        self.assertEqual(r["financial_status"], f.STATUS_SCORED)
        self.assertEqual(r["inbound_shipping_cost"], 0.35)
        self.assertAlmostEqual(r["landed_cost"], 16.34, places=2)
        self.assertIn(
            "Inbound cost uses a user-entered planning assumption: $0.35/unit.",
            r["financial_data_gaps"],
        )

    def test_explicit_referral_rate_015_is_valid_and_documented(self):
        r = pricing.estimate_financial_profile(**full_inputs())
        self.assertEqual(r["financial_status"], f.STATUS_SCORED)
        self.assertAlmostEqual(r["referral_fee"], 7.33, places=2)
        self.assertAlmostEqual(r["amazon_fees_total"], 15.53, places=2)
        self.assertIn(
            "Referral fee uses a user-entered planning assumption: 15.00%.",
            r["financial_data_gaps"],
        )

    def test_explicit_referral_fee_is_valid_and_documented(self):
        r = pricing.estimate_financial_profile(
            amazon_price=48.87, weight_lbs=3.5, costco_cost=15.99,
            prep_cost=0.0, inbound_shipping_cost=0.35, referral_fee=7.3305,
        )
        self.assertEqual(r["financial_status"], f.STATUS_SCORED)
        self.assertEqual(r["referral_fee"], 7.3305)
        self.assertIn(
            "Referral fee uses a user-entered planning assumption: $7.33.",
            r["financial_data_gaps"],
        )
        self.assertFalse(any("15.00%" in g for g in r["financial_data_gaps"]))

    def test_no_missing_field_is_converted_to_zero(self):
        r = pricing.estimate_financial_profile(amazon_price=48.87, weight_lbs=3.5, costco_cost=15.99)
        self.assertIsNone(r["prep_cost"])
        self.assertIsNone(r["inbound_shipping_cost"])
        self.assertIsNone(r["referral_fee"])
        self.assertIsNone(r["projected_net_profit"])
        self.assertIsNone(r["projected_roi_pct"])
        self.assertEqual(r["financial_status"], f.STATUS_NEED_COST_DATA)

    def test_zero_amazon_price_is_never_scored(self):
        r = pricing.estimate_financial_profile(**{**full_inputs(), "amazon_price": 0})
        self.assertIsNone(r["projected_net_profit"])
        self.assertNotEqual(r["financial_status"], f.STATUS_SCORED)

    def test_negative_explicit_prep_is_invalid_without_assumption_gap(self):
        r = pricing.estimate_financial_profile(**{**full_inputs(), "prep_cost": -0.5})
        self.assertEqual(r["financial_status"], f.STATUS_INVALID_FINANCIAL_DATA)
        self.assertIsNone(r["projected_net_profit"])
        self.assertTrue(any("prep_cost is negative" in g for g in r["financial_data_gaps"]))
        self.assertFalse(
            any(g.startswith("Prep cost uses a user-entered planning assumption") for g in r["financial_data_gaps"])
        )

    def test_all_explicit_assumption_gaps_present_together(self):
        r = pricing.estimate_financial_profile(**full_inputs())
        self.assertEqual(
            [
                g for g in r["financial_data_gaps"]
                if "user-entered planning assumption" in g
            ],
            [
                "Prep cost uses a user-entered planning assumption: $0.00/unit.",
                "Inbound cost uses a user-entered planning assumption: $0.35/unit.",
                "Referral fee uses a user-entered planning assumption: 15.00%.",
            ],
        )


class TestLegacyComputeProfitPreserved(unittest.TestCase):
    def test_compute_profit_unchanged(self):
        net, roi = pricing.compute_profit(amazon_price=48.87, costco_cost=15.99)
        self.assertAlmostEqual(net, 25.1995, places=2)
        self.assertAlmostEqual(roi, 157.60, places=1)


class TestSortContractNonScoredLast(unittest.TestCase):
    def test_need_cost_data_rows_sort_last(self):
        scored = pricing.estimate_financial_profile(**full_inputs())
        scored["title"] = "K-Cups"
        scored["asin"] = "B0CS6Z9SRX"
        incomplete = pricing.estimate_financial_profile(amazon_price=48.87, weight_lbs=3.5, costco_cost=15.99)
        incomplete["title"] = "K-Cups"
        incomplete["asin"] = "B0CS6Z9SRX"
        ordered = f.sort_by_projected_net_profit([incomplete, scored])
        self.assertEqual(ordered, [scored, incomplete])
        self.assertIsNone(incomplete["projected_net_profit"])
        self.assertEqual(incomplete["financial_status"], f.STATUS_NEED_COST_DATA)


if __name__ == "__main__":
    unittest.main(verbosity=2)