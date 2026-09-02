"""Offline tests for the BSR/category demand model (demand_estimator).

Pure module tests: signal priority, log-space interpolation, confidence
tiers and ranges, and the honesty rule that Unknown is never 0 and never
estimated from price/title/sellers/cost.
"""

import unittest

import demand_estimator as de


class SignalPriorityTests(unittest.TestCase):
    def test_listing_signal_beats_provider_and_model(self):
        d = de.estimate_demand(
            listing_bought_past_month=900,
            provider_monthly_sales_estimate=1200,
            bsr=500,
            bsr_category="Home & Kitchen",
        )
        self.assertEqual(d["estimated_monthly_sales"], 900)
        self.assertEqual(d["sales_estimation_method"], "listing_bought_past_month")
        self.assertEqual(d["sales_estimation_source"], "listing_published_signal")
        self.assertEqual(d["sales_estimation_confidence"], "higher")
        self.assertEqual(d["monthly_sales_estimated"], True)

    def test_provider_beats_model(self):
        d = de.estimate_demand(
            provider_monthly_sales_estimate=1200,
            bsr=500,
            bsr_category="Home & Kitchen",
        )
        self.assertEqual(d["estimated_monthly_sales"], 1200)
        self.assertEqual(d["sales_estimation_method"], "provider_monthly_sales_estimate")
        self.assertEqual(d["sales_estimation_source"], "provider_estimate")
        self.assertEqual(d["sales_estimation_confidence"], "medium")

    def test_model_used_when_no_listing_or_provider(self):
        d = de.estimate_demand(bsr=500, bsr_category="Home & Kitchen")
        self.assertEqual(d["sales_estimation_method"], "bsr_category_model")
        self.assertEqual(d["sales_estimation_source"], "bsr_category_model")
        self.assertEqual(d["monthly_sales_estimated"], True)
        self.assertEqual(d["bsr"], 500)
        self.assertEqual(d["bsr_category"], "Home & Kitchen")

    def test_unknown_when_no_basis(self):
        d = de.estimate_demand()
        self.assertIsNone(d["estimated_monthly_sales"])
        self.assertIsNone(d["sales_estimate_low"])
        self.assertIsNone(d["sales_estimate_high"])
        self.assertEqual(d["sales_estimation_method"], "unknown")
        self.assertEqual(d["sales_estimation_source"], "unknown")
        self.assertEqual(d["sales_estimation_confidence"], "unknown")
        self.assertFalse(d["monthly_sales_estimated"])
        self.assertIsNone(d["calibration_model_name"])

    def test_never_estimates_from_price_or_sellers(self):
        # A price, title, or seller count alone never produces an estimate.
        d = de.estimate_demand()
        self.assertIsNone(d["estimated_monthly_sales"])
        d2 = de.estimate_demand(bsr=None, bsr_category=None)
        self.assertIsNone(d2["estimated_monthly_sales"])


class InterpolationTests(unittest.TestCase):
    def test_anchor_values_are_exact_at_band_starts(self):
        curve = de.CATEGORY_CURVES["Home & Kitchen"]
        for bsr, sales in curve:
            self.assertAlmostEqual(
                de.model_estimate(bsr, "Home & Kitchen"), float(sales), places=4
            )

    def test_interpolation_is_smooth_and_between_anchors(self):
        # 500 is between the 101->8000 and 1001->2500 anchors.
        est = de.model_estimate(500, "Home & Kitchen")
        self.assertGreater(est, 2500)
        self.assertLess(est, 8000)
        # 5000 is between 1001->2500 and 5001->600 anchors.
        est2 = de.model_estimate(5000, "Home & Kitchen")
        self.assertGreater(est2, 600)
        self.assertLess(est2, 2500)

    def test_monotonic_decrease(self):
        previous = None
        for bsr in (1, 50, 100, 101, 500, 1000, 1001, 5000, 5001, 25000, 25001, 100000, 100001, 5000000):
            est = de.model_estimate(bsr, "Electronics")
            self.assertIsNotNone(est)
            if previous is not None:
                self.assertLessEqual(est, previous)
            previous = est

    def test_top_band_and_floor_clamp(self):
        self.assertAlmostEqual(de.model_estimate(1, "Books"), 3500.0, places=4)
        self.assertAlmostEqual(de.model_estimate(10 ** 8, "Books"), 5.0, places=4)
        self.assertAlmostEqual(de.model_estimate(100001, "Books"), 5.0, places=4)

    def test_unsupported_category_is_unknown(self):
        self.assertIsNone(de.model_estimate(500, "Grocery & Gourmet Food"))
        d = de.estimate_demand(bsr=500, bsr_category="Grocery & Gourmet Food")
        self.assertIsNone(d["estimated_monthly_sales"])
        self.assertEqual(d["sales_estimation_confidence"], "unknown")

    def test_missing_bsr_is_unknown(self):
        self.assertIsNone(de.model_estimate(None, "Books"))
        d = de.estimate_demand(bsr=None, bsr_category="Books")
        self.assertIsNone(d["estimated_monthly_sales"])

    def test_zero_or_negative_inputs_are_ignored(self):
        self.assertIsNone(de.model_estimate(0, "Books"))
        self.assertIsNone(de.model_estimate(-5, "Books"))
        d = de.estimate_demand(provider_monthly_sales_estimate=0)
        self.assertIsNone(d["estimated_monthly_sales"])


class ConfidenceRangeTests(unittest.TestCase):
    def test_bsr_medium_range(self):
        d = de.estimate_demand(bsr=3000, bsr_category="Health & Household")
        self.assertEqual(d["sales_estimation_confidence"], "medium")
        est = d["estimated_monthly_sales"]
        self.assertLessEqual(d["sales_estimate_low"], est)
        self.assertGreaterEqual(d["sales_estimate_high"], est)
        self.assertGreaterEqual(d["sales_estimate_low"], int(est * 0.7) - 1)
        self.assertLessEqual(d["sales_estimate_high"], int(est * 1.3) + 1)

    def test_bsr_50000_boundary_is_medium(self):
        d = de.estimate_demand(bsr=50000, bsr_category="Home & Kitchen")
        self.assertEqual(d["sales_estimation_confidence"], "medium")

    def test_bsr_low_range(self):
        d = de.estimate_demand(bsr=70000, bsr_category="Books")
        self.assertEqual(d["sales_estimation_confidence"], "low")
        est = d["estimated_monthly_sales"]
        self.assertGreaterEqual(d["sales_estimate_low"], int(est * 0.5) - 1)
        self.assertLessEqual(d["sales_estimate_high"], int(est * 1.5) + 1)

    def test_bsr_very_low_range(self):
        d = de.estimate_demand(bsr=500000, bsr_category="Toys & Games")
        self.assertEqual(d["sales_estimation_confidence"], "very_low")
        est = d["estimated_monthly_sales"]
        self.assertGreaterEqual(d["sales_estimate_low"], int(est * 0.3) - 1)
        self.assertLessEqual(d["sales_estimate_high"], int(est * 1.7) + 1)

    def test_listing_range_is_tight(self):
        d = de.estimate_demand(listing_bought_past_month=1000)
        self.assertEqual(d["sales_estimation_confidence"], "higher")
        self.assertGreaterEqual(d["sales_estimate_low"], 800)
        self.assertLessEqual(d["sales_estimate_high"], 1200)

    def test_provider_range_is_medium(self):
        d = de.estimate_demand(provider_monthly_sales_estimate=1000)
        self.assertEqual(d["sales_estimation_confidence"], "medium")
        self.assertGreaterEqual(d["sales_estimate_low"], 600)
        self.assertLessEqual(d["sales_estimate_high"], 1400)

    def test_no_range_when_unknown(self):
        d = de.estimate_demand()
        self.assertIsNone(d["sales_estimate_low"])
        self.assertIsNone(d["sales_estimate_high"])


class ModelMetaTests(unittest.TestCase):
    def test_supported_categories(self):
        self.assertEqual(
            set(de.SUPPORTED_CATEGORIES),
            {
                "Home & Kitchen",
                "Beauty & Personal Care",
                "Health & Household",
                "Toys & Games",
                "Electronics",
                "Books",
            },
        )

    def test_calibration_meta_present_only_with_estimate(self):
        d = de.estimate_demand(bsr=500, bsr_category="Books")
        self.assertEqual(d["calibration_model_name"], de.CALIBRATION_MODEL_NAME)
        self.assertEqual(d["calibration_model_version"], de.CALIBRATION_MODEL_VERSION)
        d2 = de.estimate_demand()
        self.assertIsNone(d2["calibration_model_name"])

    def test_bsr_observed_at_passthrough(self):
        d = de.estimate_demand(bsr=500, bsr_category="Books", bsr_observed_at="2026-08-17T06:59:33+00:00")
        self.assertEqual(d["bsr_observed_at"], "2026-08-17T06:59:33+00:00")
        d2 = de.estimate_demand(bsr=500, bsr_category="Books")
        self.assertIsNone(d2["bsr_observed_at"])


if __name__ == "__main__":
    unittest.main()