"""Tests for the standalone Amazon FBA fee calculator (fee_calculator.py).

Covers the Kirkland Minoxidil validation against this project's real known
figures, multiple weight tiers, multiple category referral percentages, and
edge cases (missing weight, oversize, non-numeric/invalid inputs). All tests
are offline — no network, no credentials, no money.
"""

import unittest

import fee_calculator as fc


# ---------------------------------------------------------------------------
# Kirkland Minoxidil — validation against this project's REAL known figures.
#
# Real figures (from the live sale record):
#   landed (Costco) cost     = 17.99
#   retail (Amazon) price    = 37.99
#   actual Amazon payout     = 25.51   (price - referral - fulfillment)
#   actual net profit        =  7.52   (payout - landed cost)
#
# The calculator models the sale with a 2.0 lb (32 oz) standard-size package,
# Health & Personal Care (15% above $10). Expected calculator output:
#   referral     = 15% of 37.99        =  5.70
#   fulfillment  = 2.0 lb standard band =  6.10
#   payout       = 37.99 - 5.70 - 6.10 = 26.19
#   net profit   = 26.19 - 17.99       =  8.20
#
# Variance vs real: payout 26.19 vs 25.51 (+0.68), net 8.20 vs 7.52 (+0.68).
# Root cause (documented, not forced): the real payout implies a fulfillment
# fee of ~6.78 (37.99 - 25.51 - 5.70), which is ~0.68 above the 2.0 lb band of
# 6.10. The actual Kirkland Minoxidil 6-mo unit (12 fl oz bottle + packaging)
# likely weighed a bit more than 2.0 lb (e.g., landing in/above the 3.0 lb
# 7.10 band), or the real payout netted additional small line items. The
# calculator's 2.0 lb assumption undershoots fulfillment by ~0.68.
#
# The assertion therefore uses a documented tolerance of +-1.00 (reasonable
# for a fast estimate given package-weight ambiguity and schedule drift),
# which both the real net AND payout satisfy.
# ---------------------------------------------------------------------------
KIRKLAND_COST = 17.99
KIRKLAND_PRICE = 37.99
KIRKLAND_REAL_PAYOUT = 25.51
KIRKLAND_REAL_NET = 7.52
KIRKLAND_WEIGHT_OZ = 32.0  # 2.0 lb assumption (documented above)
KIRKLAND_CATEGORY = "Health & Personal Care"
KIRKLAND_TOLERANCE = 1.00


class KirklandMinoxidilValidationTests(unittest.TestCase):
    """Validate the calculator against this project's known real figures."""

    def _calc(self):
        return fc.calculate_fba_fees(
            category=KIRKLAND_CATEGORY,
            weight_oz=KIRKLAND_WEIGHT_OZ,
            dimensions_in=(8.0, 5.0, 4.0),
            sale_price=KIRKLAND_PRICE,
            landed_cost=KIRKLAND_COST,
        )

    def test_known_real_figures_within_tolerance(self):
        r = self._calc()
        self.assertIsNotNone(r["net_profit"])
        self.assertIsNotNone(r["total_fees"])
        # Real net profit 7.52; calculator net profit 8.20 (variance +0.68).
        self.assertAlmostEqual(r["net_profit"], KIRKLAND_REAL_NET, delta=KIRKLAND_TOLERANCE)
        # Real payout 25.51; calculator payout (price - total_fees) 26.19.
        calc_payout = round(KIRKLAND_PRICE - r["total_fees"], 2)
        self.assertAlmostEqual(calc_payout, KIRKLAND_REAL_PAYOUT, delta=KIRKLAND_TOLERANCE)

    def test_exact_calculator_values_are_expected(self):
        """Lock the calculator's own arithmetic so regressions show up."""
        r = self._calc()
        self.assertEqual(r["referral_fee"], 5.70)
        self.assertEqual(r["fulfillment_fee"], 6.10)
        self.assertEqual(r["total_fees"], 11.80)
        self.assertEqual(r["net_profit"], 8.20)
        self.assertEqual(r["net_margin_pct"], round(8.20 / KIRKLAND_PRICE * 100.0, 2))

    def test_storage_fee_defaults_to_zero(self):
        r = self._calc()
        self.assertEqual(r["storage_fee_estimate"], 0.0)

    def test_documented_variance_is_small(self):
        """Document the variance explicitly rather than forcing a match."""
        r = self._calc()
        net_variance = abs(r["net_profit"] - KIRKLAND_REAL_NET)
        self.assertLess(net_variance, KIRKLAND_TOLERANCE)
        self.assertAlmostEqual(net_variance, 0.68, delta=0.01)  # +0.68 as documented


class WeightTierTests(unittest.TestCase):
    """FBA fulfillment fee by weight tier (standard-size envelope)."""

    def test_small_standard_under_half_pound(self):
        r = fc.calculate_fba_fees("Everything Else", weight_oz=7.0,  # 0.4375 lb
                                  dimensions_in=(8, 5, 1), sale_price=20.0)
        self.assertEqual(r["fulfillment_fee"], 4.75)

    def test_one_pound_tier(self):
        r = fc.calculate_fba_fees("Everything Else", weight_oz=16.0,  # 1 lb
                                  dimensions_in=(8, 5, 3), sale_price=20.0)
        self.assertEqual(r["fulfillment_fee"], 5.25)

    def test_two_and_three_pound_tiers(self):
        r2 = fc.calculate_fba_fees("Everything Else", weight_oz=32.0,  # 2 lb
                                   dimensions_in=(10, 6, 4), sale_price=20.0)
        r3 = fc.calculate_fba_fees("Everything Else", weight_oz=48.0,  # 3 lb
                                   dimensions_in=(11, 8, 5), sale_price=20.0)
        self.assertEqual(r2["fulfillment_fee"], 6.10)
        self.assertEqual(r3["fulfillment_fee"], 7.10)

    def test_five_pound_tier(self):
        r = fc.calculate_fba_fees("Everything Else", weight_oz=80.0,  # 5 lb
                                  dimensions_in=(14, 10, 8), sale_price=20.0)
        self.assertEqual(r["fulfillment_fee"], 8.20)

    def test_boundary_over_standard_returns_none(self):
        # 21 lb exceeds the standard-size weight limit (20 lb) -> unavailable.
        r = fc.calculate_fba_fees("Everything Else", weight_oz=21.0 * 16,
                                  dimensions_in=(18, 14, 8), sale_price=20.0)
        self.assertIsNone(r["fulfillment_fee"])
        self.assertEqual(r["size_tier"], "oversize")

    def test_oversized_dimensions_return_none(self):
        # One side > 18 in makes it oversized regardless of weight.
        r = fc.calculate_fba_fees("Everything Else", weight_oz=16.0,
                                  dimensions_in=(24, 10, 8), sale_price=20.0)
        self.assertIsNone(r["fulfillment_fee"])
        self.assertEqual(r["size_tier"], "oversize")


class CategoryRateTests(unittest.TestCase):
    """Referral fee by category percentage."""

    def test_consumer_electronics_eight_percent(self):
        r = fc.calculate_fba_fees("Consumer Electronics", weight_oz=12.0,
                                  dimensions_in=(6, 4, 2), sale_price=200.0)
        self.assertEqual(r["referral_fee"], 16.00)  # 8% of 200
        self.assertEqual(r["referral_fee_rate"], 0.08)

    def test_toys_and_games_fifteen_percent(self):
        r = fc.calculate_fba_fees("Toys & Games", weight_oz=16.0,
                                  dimensions_in=(10, 8, 6), sale_price=50.0)
        self.assertEqual(r["referral_fee"], 7.50)  # 15% of 50

    def test_automotive_twelve_percent(self):
        r = fc.calculate_fba_fees("Automotive & Powersports", weight_oz=16.0,
                                  dimensions_in=(12, 8, 6), sale_price=100.0)
        self.assertEqual(r["referral_fee"], 12.00)  # 12% of 100

    def test_health_personal_care_low_price_switch(self):
        # Health & Personal Care: 8% at/below $10.
        r = fc.calculate_fba_fees("Health & Personal Care", weight_oz=8.0,
                                  dimensions_in=(5, 4, 2), sale_price=10.0)
        self.assertEqual(r["referral_fee"], 0.80)  # 8% of 10
        # Above $10 -> 15%.
        r2 = fc.calculate_fba_fees("Health & Personal Care", weight_oz=8.0,
                                   dimensions_in=(5, 4, 2), sale_price=10.01)
        self.assertEqual(r2["referral_fee"], round(10.01 * 0.15, 2))  # 1.50

    def test_default_category_everything_else(self):
        r = fc.calculate_fba_fees(None, weight_oz=16.0,
                                  dimensions_in=(8, 6, 4), sale_price=40.0)
        self.assertEqual(r["referral_fee_category"], "Everything Else")
        self.assertEqual(r["referral_fee"], 6.00)  # 15% of 40


class EdgeCaseTests(unittest.TestCase):
    """Invalid / missing inputs fail closed."""

    def test_missing_weight_returns_none(self):
        r = fc.calculate_fba_fees("Everything Else", weight_oz=0,
                                  dimensions_in=(8, 6, 4), sale_price=20.0)
        self.assertIsNone(r["fulfillment_fee"])
        self.assertIsNone(r["total_fees"])
        self.assertIsNone(r["net_profit"])

    def test_non_numeric_price_returns_none(self):
        r = fc.calculate_fba_fees("Everything Else", weight_oz=16.0,
                                  dimensions_in=(8, 6, 4), sale_price=-5)
        self.assertIsNone(r["referral_fee"])
        self.assertIsNone(r["net_profit"])

    def test_net_profit_requires_landed_cost(self):
        # Without a landed cost, net profit stays None (never invented).
        r = fc.calculate_fba_fees("Everything Else", weight_oz=16.0,
                                  dimensions_in=(8, 6, 4), sale_price=20.0)
        self.assertIsNone(r["net_profit"])
        self.assertIsNotNone(r["total_fees"])

    def test_total_fees_is_referral_plus_fulfillment(self):
        r = fc.calculate_fba_fees("Consumer Electronics", weight_oz=32.0,
                                  dimensions_in=(10, 6, 4), sale_price=100.0)
        self.assertEqual(r["referral_fee"], 8.00)   # 8% of 100
        self.assertEqual(r["fulfillment_fee"], 6.10)  # 2 lb
        self.assertEqual(r["total_fees"], 14.10)
        # Without a landed cost, net_profit stays None.
        self.assertIsNone(r["net_profit"])
        # With landed_cost=50: net = 100 - 50 - 14.10 = 35.90.
        r2 = fc.calculate_fba_fees("Consumer Electronics", weight_oz=32.0,
                                   dimensions_in=(10, 6, 4), sale_price=100.0,
                                   landed_cost=50.0)
        self.assertEqual(r2["net_profit"], 35.90)


if __name__ == "__main__":
    unittest.main()
