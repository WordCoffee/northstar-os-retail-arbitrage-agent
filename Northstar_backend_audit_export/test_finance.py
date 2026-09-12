import test_network_guard  # noqa: F401  (blocks real network calls)
import unittest

import finance as f


class TestFinanceEngine(unittest.TestCase):
    def test_profitable_product(self):
        """Sale price 37.99, fees total 12.48, COGS 17.99, prep 0, inbound 0."""
        r = f.project_finances(
            amazon_sale_price=37.99,
            referral_fee=7.49,
            fba_fulfillment_fee=4.99,
            cogs=17.99,
            prep_cost=0,
            inbound_shipping_cost=0,
        )
        self.assertAlmostEqual(r["amazon_fees_total"], 12.48, places=2)
        self.assertAlmostEqual(r["amazon_payout_before_inventory_costs"], 25.51, places=2)
        self.assertAlmostEqual(r["landed_cost"], 17.99, places=2)
        self.assertAlmostEqual(r["projected_net_profit"], 7.52, places=2)
        self.assertAlmostEqual(r["projected_roi_pct"], 41.80, places=1)
        self.assertEqual(r["financial_status"], f.STATUS_SCORED)
        self.assertEqual(r["financial_data_gaps"], [])
        self.assertIsInstance(r["projected_net_profit"], float)

    def test_unprofitable_product(self):
        r = f.project_finances(
            amazon_sale_price=20.00,
            referral_fee=3.00,
            fba_fulfillment_fee=5.00,
            cogs=17.99,
            prep_cost=0,
            inbound_shipping_cost=0,
        )
        self.assertLessEqual(r["projected_net_profit"], 0)
        self.assertEqual(r["financial_status"], f.STATUS_UNPROFITABLE)

    def test_missing_cogs(self):
        r = f.project_finances(
            amazon_sale_price=37.99,
            referral_fee=7.49,
            fba_fulfillment_fee=4.99,
            cogs=None,
            prep_cost=0,
            inbound_shipping_cost=0,
        )
        self.assertIsNone(r["projected_net_profit"])
        self.assertIsNone(r["landed_cost"])
        self.assertEqual(r["financial_status"], f.STATUS_NEED_COST_DATA)
        self.assertTrue(any("cogs is missing" in g for g in r["financial_data_gaps"]))

    def test_missing_fba_or_referral_fee(self):
        r = f.project_finances(
            amazon_sale_price=37.99,
            referral_fee=None,
            fba_fulfillment_fee=4.99,
            cogs=17.99,
            prep_cost=0,
            inbound_shipping_cost=0,
        )
        self.assertIsNone(r["projected_net_profit"])
        self.assertEqual(r["financial_status"], f.STATUS_NEED_FEE_DATA)
        self.assertTrue(any("referral_fee is missing" in g for g in r["financial_data_gaps"]))

    def test_missing_both_prefers_cost_status(self):
        r = f.project_finances(
            amazon_sale_price=None, referral_fee=None, fba_fulfillment_fee=None,
            cogs=None, prep_cost=None, inbound_shipping_cost=None,
        )
        self.assertEqual(r["financial_status"], f.STATUS_NEED_COST_DATA)

    def test_explicit_zero_prep_and_inbound_are_valid(self):
        r = f.project_finances(
            amazon_sale_price=50.00,
            referral_fee=7.50,
            fba_fulfillment_fee=5.00,
            cogs=30.00,
            prep_cost=0,
            inbound_shipping_cost=0,
        )
        self.assertEqual(r["prep_cost"], 0)
        self.assertEqual(r["inbound_shipping_cost"], 0)
        self.assertAlmostEqual(r["landed_cost"], 30.00, places=2)
        self.assertAlmostEqual(r["projected_net_profit"], 7.50, places=2)
        self.assertEqual(r["financial_status"], f.STATUS_SCORED)

    def test_negative_value_is_invalid_financial_data(self):
        for field in (
            "amazon_sale_price", "referral_fee", "fba_fulfillment_fee",
            "cogs", "prep_cost", "inbound_shipping_cost",
        ):
            kwargs = {
                "amazon_sale_price": 37.99,
                "referral_fee": 7.49,
                "fba_fulfillment_fee": 4.99,
                "cogs": 17.99,
                "prep_cost": 0,
                "inbound_shipping_cost": 0,
            }
            kwargs[field] = -1.0
            r = f.project_finances(**kwargs)
            self.assertEqual(r["financial_status"], f.STATUS_INVALID_FINANCIAL_DATA, field)
            self.assertIsNone(r["projected_net_profit"])
            self.assertTrue(any(f"{field} is negative" in g for g in r["financial_data_gaps"]))

    def test_zero_landed_cost_roi_is_null_no_div_zero(self):
        r = f.project_finances(
            amazon_sale_price=10.00,
            referral_fee=1.50,
            fba_fulfillment_fee=2.00,
            cogs=0,
            prep_cost=0,
            inbound_shipping_cost=0,
        )
        self.assertEqual(r["landed_cost"], 0)
        self.assertIsNone(r["projected_roi_pct"])
        self.assertAlmostEqual(r["projected_net_profit"], 6.50, places=2)

    def test_precision_numeric_not_rounded(self):
        """Full float precision is preserved; no display rounding here."""
        r = f.project_finances(
            amazon_sale_price=3.3,
            referral_fee=0.1,
            fba_fulfillment_fee=0.2,
            cogs=0.1,
            prep_cost=0.1,
            inbound_shipping_cost=0.1,
        )
        profit = r["projected_net_profit"]
        self.assertIsInstance(profit, float)
        self.assertNotEqual(profit, round(profit, 0))
        self.assertAlmostEqual(profit, 2.7, places=2)
        self.assertEqual(r["financial_status"], f.STATUS_SCORED)

    def test_invalid_non_numeric_input(self):
        r = f.project_finances(
            amazon_sale_price="37.99",
            referral_fee=7.49,
            fba_fulfillment_fee=4.99,
            cogs=17.99,
            prep_cost=0,
            inbound_shipping_cost=0,
        )
        self.assertIsNone(r["projected_net_profit"])
        self.assertEqual(r["financial_status"], f.STATUS_NEED_FEE_DATA)

    def test_invalid_bool_input(self):
        r = f.project_finances(
            amazon_sale_price=37.99,
            referral_fee=7.49,
            fba_fulfillment_fee=4.99,
            cogs=True,
            prep_cost=0,
            inbound_shipping_cost=0,
        )
        self.assertEqual(r["financial_status"], f.STATUS_NEED_COST_DATA)

    def test_non_finite_input_is_invalid_financial_data(self):
        for bad in (float("nan"), float("inf")):
            r = f.project_finances(
                amazon_sale_price=bad,
                referral_fee=7.49,
                fba_fulfillment_fee=4.99,
                cogs=17.99,
                prep_cost=0,
                inbound_shipping_cost=0,
            )
            self.assertEqual(r["financial_status"], f.STATUS_INVALID_FINANCIAL_DATA)
            self.assertIsNone(r["projected_net_profit"])


class TestIndividualFunctions(unittest.TestCase):
    def test_payout(self):
        self.assertAlmostEqual(f.amazon_payout_before_inventory_costs(100, 15, 7), 78.0, places=2)
        self.assertIsNone(f.amazon_payout_before_inventory_costs(100, None, 7))
        self.assertIsNone(f.amazon_payout_before_inventory_costs(100, -15, 7))

    def test_landed(self):
        self.assertAlmostEqual(f.landed_cost(30, 2, 1), 33.0, places=2)
        self.assertIsNone(f.landed_cost(30, None, 1))

    def test_net_profit(self):
        self.assertAlmostEqual(f.projected_net_profit(100, 15, 7, 30, 2, 1), 45.0, places=2)
        self.assertIsNone(f.projected_net_profit(100, 15, None, 30, 2, 1))

    def test_roi_pct(self):
        self.assertAlmostEqual(f.projected_roi_pct(45, 33), 136.36, places=2)
        self.assertIsNone(f.projected_roi_pct(None, 33))
        self.assertIsNone(f.projected_roi_pct(45, None))
        self.assertIsNone(f.projected_roi_pct(45, 0))


class TestSortContract(unittest.TestCase):
    def test_scored_first_high_to_low(self):
        high = f.project_finances(amazon_sale_price=100, referral_fee=15, fba_fulfillment_fee=7, cogs=30, prep_cost=2, inbound_shipping_cost=1)
        low = f.project_finances(amazon_sale_price=60, referral_fee=9, fba_fulfillment_fee=7, cogs=30, prep_cost=2, inbound_shipping_cost=1)
        incomplete = f.project_finances(amazon_sale_price=60, referral_fee=9, fba_fulfillment_fee=7, cogs=None, prep_cost=2, inbound_shipping_cost=1)
        for r in (high, low, incomplete):
            r["title"] = "T"
            r["asin"] = "B000000001"
        ordered = f.sort_by_projected_net_profit([low, incomplete, high])
        self.assertEqual(ordered, [high, low, incomplete])
        self.assertIsNone(incomplete["projected_net_profit"])

    def test_numeric_sort_not_alphabetical(self):
        r1 = {"projected_net_profit": 9.5, "title": "A", "asin": "B000000001"}
        r2 = {"projected_net_profit": 75.0, "title": "B", "asin": "B000000002"}
        r3 = {"projected_net_profit": None, "title": "C", "asin": "B000000003"}
        ordered = f.sort_by_projected_net_profit([r1, r3, r2])
        self.assertEqual([r["projected_net_profit"] for r in ordered], [75.0, 9.5, None])

    def test_roi_null_last(self):
        scored = {"projected_net_profit": 1.0, "projected_roi_pct": 5.0, "title": "A", "asin": "B000000001"}
        null_roi = {"projected_net_profit": 9.0, "projected_roi_pct": None, "title": "B", "asin": "B000000002"}
        self.assertEqual(f.projected_roi_pct_sort_key(scored), (0, -5.0))
        self.assertEqual(f.projected_roi_pct_sort_key(null_roi), (1, 0.0))

    def test_field_naming(self):
        self.assertEqual(f.DISPLAY_FIELD_NAME, "Projected Net Profit ($)")
        self.assertEqual(f.DEFAULT_SORT_LABEL, "Projected Net Profit: High to Low")
        with open(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\finance.py", encoding="utf-8") as fh:
            source = fh.read()
        for banned in ("ROI Dollar Amount", "ROI dollars", "return dollars", "roi_dollar"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)