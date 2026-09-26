import unittest
from decimal import Decimal

from faire_research import (
    DEFAULT_MIN_CONTRIBUTION_PROFIT,
    FeeConfidence,
    FeeInputs,
    LandedCostInputs,
    contribution_profit,
    downside_scenarios,
    landed_unit_cost,
)


class LandedCostTests(unittest.TestCase):
    def test_landed_unit_cost_divides_by_verified_units(self):
        got = landed_unit_cost(LandedCostInputs(
            wholesale_case_cost=Decimal("120.00"), supplier_shipping=Decimal("10.00"),
            nonrecoverable_tax=Decimal("0"), duties=Decimal("0"),
            receiving_cost=Decimal("2.00"), case_level_prep_cost=Decimal("0"),
            verified_sellable_units=12))
        self.assertEqual(got, Decimal("11"))

    def test_unknown_units_unresolved(self):
        self.assertIsNone(landed_unit_cost(LandedCostInputs(
            wholesale_case_cost=Decimal("120"), verified_sellable_units=None)))

    def test_unknown_component_is_not_zero(self):
        self.assertIsNone(landed_unit_cost(LandedCostInputs(
            wholesale_case_cost=Decimal("120"), supplier_shipping=None,
            verified_sellable_units=12)))

    def test_zero_units_unresolved(self):
        self.assertIsNone(landed_unit_cost(LandedCostInputs(
            wholesale_case_cost=Decimal("120"), verified_sellable_units=0)))


class ContributionTests(unittest.TestCase):
    def _fees(self, **kw):
        base = dict(referral_fee=Decimal("3.00"), fba_fulfillment_fee=Decimal("4.75"),
                    inbound_fba_per_unit=Decimal("0.35"), prep_label_per_unit=Decimal("0.10"),
                    storage_alloc_per_unit=Decimal("0.10"), advertising_reserve_per_unit=Decimal("1.00"),
                    return_reserve_per_unit=Decimal("0.50"), other_per_unit=Decimal("0.00"),
                    confidence=FeeConfidence.ESTIMATED_FROM_COMPLETE_INPUTS)
        base.update(kw)
        return FeeInputs(**base)

    def test_contribution_profit_roi_margin_distinct(self):
        r = contribution_profit(Decimal("30.00"), Decimal("11.00"), self._fees())
        self.assertTrue(r.resolved)
        # price - fee_total - landed = 30 - 9.80 - 11 = 9.20
        self.assertEqual(r.contribution_profit, Decimal("9.20"))
        self.assertIsNotNone(r.roi_pct)
        self.assertIsNotNone(r.margin_pct)
        self.assertNotEqual(r.roi_pct, r.margin_pct)

    def test_does_not_use_faire_minus_amazon(self):
        # a "faire price - amazon price" style calc would be negative; ours isn't
        r = contribution_profit(Decimal("30.00"), Decimal("11.00"), self._fees())
        self.assertGreater(r.contribution_profit, Decimal("0"))

    def test_fee_unknown_cannot_pass(self):
        r = contribution_profit(Decimal("30.00"), Decimal("11.00"),
                                self._fees(confidence=FeeConfidence.FEE_UNKNOWN))
        self.assertFalse(r.resolved)
        self.assertTrue(any("FEE_UNKNOWN" in x for x in r.reasons))

    def test_unknown_fee_component_not_zero(self):
        r = contribution_profit(Decimal("30.00"), Decimal("11.00"), self._fees(fba_fulfillment_fee=None))
        self.assertFalse(r.resolved)

    def test_missing_landed_cost_unresolved(self):
        r = contribution_profit(Decimal("30.00"), None, self._fees())
        self.assertFalse(r.resolved)

    def test_negative_profit_still_reported(self):
        r = contribution_profit(Decimal("12.00"), Decimal("20.00"), self._fees())
        self.assertTrue(r.resolved)
        self.assertLess(r.contribution_profit, Decimal("0"))

    def test_below_min_profit_flagged(self):
        r = contribution_profit(Decimal("13.00"), Decimal("11.00"), self._fees())
        self.assertLess(r.contribution_profit, DEFAULT_MIN_CONTRIBUTION_PROFIT)
        self.assertTrue(r.reasons)

    def test_decimal_precision_quantized_to_cents(self):
        r = contribution_profit(Decimal("30.005"), Decimal("11.001"), self._fees())
        self.assertEqual(r.contribution_profit.as_tuple().exponent, -2)

    def test_downside_scenarios_scale_referral(self):
        ds = downside_scenarios(Decimal("30.00"), Decimal("11.00"), self._fees())
        self.assertEqual(len(ds), 4)
        self.assertEqual(ds[0]["decline_pct"], Decimal("0"))
        self.assertLess(ds[-1]["contribution_profit"], ds[0]["contribution_profit"])


if __name__ == "__main__":
    unittest.main()
