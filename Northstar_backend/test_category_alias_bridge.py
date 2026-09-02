"""Offline regression tests for the fee-engine <-> demand-estimator
category-vocabulary alias bridge. No network, no providers."""

import unittest

import demand_estimator
from fee_engine import calculate_referral_fee


class TestDemandAliasBridge(unittest.TestCase):
    def test_fee_vocab_resolves_to_demand_curve(self):
        # product_analysis feeds the fee-resolved category into demand;
        # these must now map onto a real demand curve.
        for fee_term, expected_curve in [
            ("Health & Personal Care", "Health & Household"),
            ("Beauty", "Beauty & Personal Care"),
            ("Consumer Electronics", "Electronics"),
            ("Electronics", "Electronics"),
            ("Home & Kitchen", "Home & Kitchen"),
            ("Toys & Games", "Toys & Games"),
            ("Books", "Books"),
        ]:
            with self.subTest(fee_term=fee_term):
                est = demand_estimator.estimate_demand(
                    bsr=50000, bsr_category=fee_term
                )
                self.assertEqual(est["bsr_category"], expected_curve)
                self.assertIsNotNone(est["estimated_monthly_sales"])
                self.assertNotEqual(est["sales_estimation_method"], "unknown")

    def test_bsr_department_text_resolves_to_demand_curve(self):
        est = demand_estimator.estimate_demand(
            bsr=292264, bsr_category="Health & Household"
        )
        self.assertEqual(est["bsr_category"], "Health & Household")
        self.assertIsNotNone(est["estimated_monthly_sales"])

    def test_unmapped_category_stays_unknown(self):
        est = demand_estimator.estimate_demand(
            bsr=50000, bsr_category="Everything Else"
        )
        self.assertEqual(est["sales_estimation_method"], "unknown")
        self.assertIsNone(est["estimated_monthly_sales"])

    def test_version_bumped(self):
        self.assertEqual(demand_estimator.CALIBRATION_MODEL_VERSION, "1.1")


class TestFeeAliasBridge(unittest.TestCase):
    def test_bsr_department_text_resolves_fee_category(self):
        fee = calculate_referral_fee(25.0, amazon_category="Health & Household")
        self.assertEqual(fee["referral_fee_category"], "Health & Personal Care")
        self.assertEqual(fee["referral_fee_confidence"], "verified_category")

    def test_version_bumped(self):
        from amazon_us_fee_rules_2026 import CATEGORY_RESOLVER_VERSION

        self.assertEqual(CATEGORY_RESOLVER_VERSION, "2026.2")


if __name__ == "__main__":
    unittest.main()
