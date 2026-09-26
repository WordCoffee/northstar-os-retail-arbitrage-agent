import unittest
from decimal import Decimal

from faire_research import (
    BrandRiskState,
    CandidateAssessment,
    EligibilityState,
    FeeConfidence,
    FeeInputs,
    LandedCostInputs,
    MatchConfidence,
    MarketplacePermission,
    OpportunityState,
    can_be_purchase_ready,
    can_be_source_ready,
    contribution_profit,
    derive_state,
    hard_disqualifiers,
    landed_unit_cost,
    score,
)


def _economics():
    return contribution_profit(
        Decimal("30.00"), landed_unit_cost(LandedCostInputs(
            wholesale_case_cost=Decimal("132.00"), supplier_shipping=Decimal("0"),
            nonrecoverable_tax=Decimal("0"), duties=Decimal("0"),
            receiving_cost=Decimal("0"), case_level_prep_cost=Decimal("0"),
            verified_sellable_units=12)),
        FeeInputs(referral_fee=Decimal("4.50"), fba_fulfillment_fee=Decimal("4.75"),
                  inbound_fba_per_unit=Decimal("0.35"), prep_label_per_unit=Decimal("0.10"),
                  storage_alloc_per_unit=Decimal("0.10"), advertising_reserve_per_unit=Decimal("1.00"),
                  return_reserve_per_unit=Decimal("0.50"), other_per_unit=Decimal("0.00"),
                  confidence=FeeConfidence.ESTIMATED_FROM_COMPLETE_INPUTS))


def _base(**kw):
    a = CandidateAssessment(
        org_id="org_t2", match_confidence=MatchConfidence.EXACT_IDENTIFIER_MATCH,
        economics=_economics(), faire_is_only_sourcing_route=True,
        brand_permission=MarketplacePermission.UNKNOWN,
        eligibility=EligibilityState.ELIGIBILITY_UNKNOWN,
        direct_supplier_verified=False, invoice_path_ready=False)
    for k, v in kw.items():
        setattr(a, k, v)
    return a


class ComplianceTests(unittest.TestCase):
    def test_faire_only_sourcing_is_hard_rejected(self):
        a = _base(faire_is_only_sourcing_route=True, match_confidence=MatchConfidence.EXACT_IDENTIFIER_MATCH,
                  invoice_path_ready=True, direct_supplier_verified=True,
                  brand_permission=MarketplacePermission.YES,
                  eligibility=EligibilityState.ELIGIBLE_CONFIRMED)
        self.assertIn("faire_is_only_sourcing_route", hard_disqualifiers(a))
        self.assertEqual(derive_state(a), OpportunityState.REJECTED)

    def test_brand_prohibits_amazon_rejected(self):
        a = _base(brand_permission=MarketplacePermission.NO, invoice_path_ready=True)
        self.assertIn("brand_prohibits_amazon", hard_disqualifiers(a))

    def test_not_on_amazon_is_a_risk_not_an_opportunity(self):
        a = _base(brand_risk=BrandRiskState.BRAND_POLICY_RESTRICTS_MARKETPLACES, invoice_path_ready=True)
        self.assertIn("direct_supplier_prohibits_amazon", hard_disqualifiers(a))

    def test_eligibility_restricted_rejected(self):
        a = _base(eligibility=EligibilityState.RESTRICTED, invoice_path_ready=True)
        self.assertIn("amazon_eligibility_restricted_or_not_eligible", hard_disqualifiers(a))

    def test_unknown_authorization_blocks_purchase(self):
        a = _base(invoice_path_ready=True, direct_supplier_verified=True,
                  brand_permission=MarketplacePermission.UNKNOWN)
        ok, reasons = can_be_purchase_ready(a)
        self.assertFalse(ok)
        self.assertIn("brand_authorization_not_confirmed", reasons)

    def test_invoice_path_missing_disqualifies(self):
        a = _base(invoice_path_ready=False)
        self.assertIn("invoice_path_absent", hard_disqualifiers(a))

    def test_unknown_eligibility_blocks_purchase(self):
        a = _base(invoice_path_ready=True, direct_supplier_verified=True,
                  brand_permission=MarketplacePermission.YES,
                  eligibility=EligibilityState.ELIGIBILITY_UNKNOWN)
        ok, reasons = can_be_purchase_ready(a)
        self.assertFalse(ok)
        self.assertIn("eligibility_not_confirmed", reasons)

    def test_direct_supplier_authorization_allows_qualified_review(self):
        a = _base(invoice_path_ready=True, direct_supplier_verified=True,
                  brand_permission=MarketplacePermission.YES,
                  eligibility=EligibilityState.ELIGIBLE_CONFIRMED,
                  faire_is_only_sourcing_route=False)
        self.assertEqual(hard_disqualifiers(a), [])
        self.assertEqual(derive_state(a), OpportunityState.QUALIFIED_FOR_MANUAL_REVIEW)
        self.assertTrue(can_be_source_ready(a)[0])
        self.assertTrue(can_be_purchase_ready(a)[0])

    def test_source_ready_requires_verified_supplier(self):
        a = _base(invoice_path_ready=True, direct_supplier_verified=False,
                  brand_permission=MarketplacePermission.YES,
                  eligibility=EligibilityState.ELIGIBLE_CONFIRMED,
                  faire_is_only_sourcing_route=False)
        ok, reasons = can_be_source_ready(a)
        self.assertFalse(ok)
        self.assertIn("direct_supplier_not_verified", reasons)

    def test_ambiguous_match_goes_to_match_review(self):
        a = _base(match_confidence=MatchConfidence.PROBABLE_MATCH_REVIEW_REQUIRED,
                  invoice_path_ready=True, direct_supplier_verified=True,
                  brand_permission=MarketplacePermission.YES,
                  eligibility=EligibilityState.ELIGIBLE_CONFIRMED,
                  faire_is_only_sourcing_route=False)
        self.assertEqual(derive_state(a), OpportunityState.MATCH_REVIEW)

    def test_unresolved_economics_incomplete(self):
        a = _base(match_confidence=MatchConfidence.EXACT_IDENTIFIER_MATCH, economics=None,
                  invoice_path_ready=True, faire_is_only_sourcing_route=False)
        self.assertEqual(derive_state(a), OpportunityState.ECONOMICS_INCOMPLETE)


class ScoringTests(unittest.TestCase):
    def test_score_bounds(self):
        a = _base()
        s, _ = score(a, components={})
        self.assertEqual(s, 0)
        full = {k: 1.0 for k in [
            "verified_profit_and_roi", "size_weight_fba_burden",
            "marketplace_eligibility_authorization", "direct_supplier_invoice_readiness",
            "demand_evidence", "competition_quality", "price_stability",
            "replenishment_quality", "operational_simplicity"]}
        s2, _ = score(a, components=full)
        self.assertEqual(s2, 100)

    def test_score_never_assumes_missing_components(self):
        a = _base()
        s, _ = score(a, components={"verified_profit_and_roi": 1.0})
        self.assertEqual(s, 20)


if __name__ == "__main__":
    unittest.main()
