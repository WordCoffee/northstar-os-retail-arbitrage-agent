"""Tests 8-9: economics blocking + Golden Goose blocker/penalty logic."""
from __future__ import annotations

import unittest

from costco_non_kirkland.economics import compute_economics
from costco_non_kirkland.enums import EconomicsCompleteness, IdentityStatus
from costco_non_kirkland.scoring import score_golden_goose, GG_SCORER_VERSION


class EconomicsBlockingTests(unittest.TestCase):
    def test_missing_cost_blocks(self):
        econ = compute_economics(cost_basis=None, sale_price=30.0,
                                 identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                 pack_verified=True)
        self.assertEqual(econ.economics_completeness, EconomicsCompleteness.INCOMPLETE_COST.value)
        self.assertIsNone(econ.net_profit)
        self.assertIn("cost_basis", econ.missing_inputs)

    def test_missing_price_blocks(self):
        econ = compute_economics(cost_basis=10.0, sale_price=None,
                                 identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                 pack_verified=True)
        self.assertEqual(econ.economics_completeness, EconomicsCompleteness.INCOMPLETE_PRICE.value)
        self.assertIsNone(econ.net_profit)

    def test_missing_fees_never_zero(self):
        econ = compute_economics(cost_basis=10.0, sale_price=30.0,
                                 identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                 pack_verified=True,
                                 referral_fee_rate=None, fba_fee=None)
        # canonical engine leaves fee outputs None; nothing becomes zero.
        if econ.net_profit is not None:
            self.assertNotEqual(econ.fba_fee, 0.0)
        self.assertIn(econ.economics_completeness, (
            EconomicsCompleteness.COMPLETE.value,
            EconomicsCompleteness.INCOMPLETE_FEES.value,
        ))

    def test_identity_conflict_blocks(self):
        econ = compute_economics(cost_basis=10.0, sale_price=30.0,
                                 identity_status=IdentityStatus.IDENTITY_CONFLICT.value,
                                 pack_verified=False)
        self.assertEqual(econ.economics_completeness, EconomicsCompleteness.BLOCKED_IDENTITY_MISMATCH.value)
        self.assertIsNone(econ.net_profit)
        self.assertIsNone(econ.roi_percent)

    def test_pack_mismatch_blocks(self):
        econ = compute_economics(cost_basis=10.0, sale_price=30.0,
                                 identity_status=IdentityStatus.PACK_MISMATCH.value,
                                 pack_verified=False)
        self.assertEqual(econ.economics_completeness, EconomicsCompleteness.BLOCKED_IDENTITY_MISMATCH.value)

    def test_hypothetical_class_when_assumptions_used(self):
        econ = compute_economics(cost_basis=10.0, sale_price=30.0,
                                 identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                 pack_verified=True,
                                 referral_fee_rate=0.15, fba_fee=5.0,
                                 assumptions=["assumed FBA fee"])
        self.assertEqual(econ.calculation_class, "hypothetical")
        self.assertIn("assumed FBA fee", econ.assumptions)

    def test_complete_economics(self):
        econ = compute_economics(cost_basis=10.0, sale_price=30.0,
                                 identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                 pack_verified=True,
                                 referral_fee_rate=0.15, fba_fee=5.0,
                                 prep_cost=0.5, inbound_shipping_cost=0.4)
        self.assertEqual(econ.economics_completeness, EconomicsCompleteness.COMPLETE.value)
        self.assertIsNotNone(econ.net_profit)
        self.assertIsNotNone(econ.roi_percent)
        self.assertIsNotNone(econ.net_margin_percent)


class GoldenGooseBlockerTests(unittest.TestCase):
    def test_kirkland_source_blocked(self):
        gg = score_golden_goose(eligible=False, identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                pack_verified=True, economics_completeness="complete")
        self.assertIsNone(gg.score)
        self.assertEqual(gg.recommendation_status, "blocked_compliance_risk")
        self.assertIn("KIRKLAND_SOURCE", gg.risk_flags)

    def test_identity_mismatch_blocked(self):
        gg = score_golden_goose(eligible=True, identity_status=IdentityStatus.PACK_MISMATCH.value,
                                pack_verified=False, economics_completeness="complete")
        self.assertEqual(gg.recommendation_status, "blocked_identity_mismatch")
        self.assertIn("IDENTITY_MISMATCH", gg.risk_flags)

    def test_missing_economics_blocked(self):
        gg = score_golden_goose(eligible=True, identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                pack_verified=True, economics_completeness="not_calculated")
        self.assertEqual(gg.recommendation_status, "blocked_incomplete_economics")
        self.assertIn("MISSING_ECONOMICS", gg.risk_flags)

    def test_purchase_authorization_always_not_authorized(self):
        gg = score_golden_goose(eligible=True, identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                pack_verified=True, economics_completeness="complete",
                                economics={"net_margin_percent": 40.0, "roi_percent": 80.0,
                                           "economics_completeness": "complete"},
                                selleramp={"estimated_monthly_sales": 20000})
        self.assertEqual(gg.purchase_authorization_status, "not_authorized")

    def test_penalty_reduces_score(self):
        base = score_golden_goose(eligible=True, identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                  pack_verified=True, economics_completeness="complete",
                                  economics={"net_margin_percent": 40.0, "roi_percent": 80.0,
                                             "economics_completeness": "complete"},
                                  selleramp={"estimated_monthly_sales": 20000})
        penalized = score_golden_goose(eligible=True, identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
                                       pack_verified=True, economics_completeness="complete",
                                       economics={"net_margin_percent": 40.0, "roi_percent": 80.0,
                                                  "economics_completeness": "complete"},
                                       selleramp={"estimated_monthly_sales": 20000},
                                       risk_hints={"hazardous": True, "expiry_risk": True})
        self.assertIsNotNone(base.score)
        self.assertIsNotNone(penalized.score)
        self.assertLess(penalized.score, base.score)
        self.assertIn("hazardous", penalized.risk_flags)

    def test_version_is_constant(self):
        self.assertEqual(GG_SCORER_VERSION, "golden-goose-costco-nonkirkland-1.0.0")


if __name__ == "__main__":
    unittest.main()