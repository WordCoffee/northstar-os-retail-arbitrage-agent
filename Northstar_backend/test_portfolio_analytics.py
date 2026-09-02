"""Offline tests for portfolio analytics (portfolio_analytics).

Covers revenue basis rules (Buy Box landed price first, candidate-record
amazon_price second, never an arbitrary offer price), profit pools,
completeness dimensions, readiness/next-step/category ladders, risk
flags, score reasons, and the honesty rule that unknown seller data
never improves readiness, category, share, or score.
"""

import unittest
from datetime import datetime, timedelta, timezone

import portfolio_analytics as pa


def _fresh_snapshot(status="available", offers=None, offers_returned=None,
                    offers_complete=True, claimed=None, buy_box=None):
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    return {
        "data_status": status,
        "offers": offers if offers is not None else [],
        "offers_returned": offers_returned if offers_returned is not None else len(offers or []),
        "offers_complete": offers_complete,
        "seller_counts": {"claimed_total": claimed if claimed is not None else len(offers or []),
                          "observed_total": len(offers or []),
                          "fba_observed": sum(1 for o in (offers or []) if o.get("is_fba")),
                          "fbm_observed": sum(1 for o in (offers or []) if o.get("is_fbm")),
                          "amazon_observed": 0, "counts_from_observed": True},
        "buy_box": buy_box or {},
        "freshness": {"offers_fresh_until": future},
    }


def _offer(price, fba=False, fbm=False, free=True):
    return {"price": {"value": price}, "is_fba": fba, "is_fbm": fbm,
            "is_sba": False, "is_prime": fba, "seller_name": "Seller Co",
            "fulfilled_by_amazon": fba, "shipping_is_free": free}


def _demand(est=1000, confidence="medium"):
    return {
        "estimated_monthly_sales": est,
        "sales_estimation_confidence": confidence,
        "sales_estimate_low": int(est * 0.7),
        "sales_estimate_high": int(est * 1.3),
        "sales_estimation_method": "provider_monthly_sales_estimate",
        "sales_estimation_source": "provider_estimate",
        "monthly_sales_estimated": True,
        "bsr": 2000, "bsr_category": "Home & Kitchen", "bsr_observed_at": None,
        "calibration_model_name": "x", "calibration_model_version": "1.0",
    }


def _competition(observed=3, fba=2, fbm=1, complete=True, reason=None, est=1000):
    return {
        "observed_total_sellers": observed,
        "observed_fba_sellers": fba,
        "observed_fbm_sellers": fbm,
        "observed_amazon_sellers": 0,
        "claimed_offer_count": observed if complete else observed + 9,
        "offers_returned": observed,
        "offers_complete": complete,
        "offer_roster_reason": reason,
        "observed_buy_box_available": True,
        "observed_buy_box_price": 50.0,
        "observed_buy_box_landed_price": None,
        "observed_buy_box_seller": "Seller Co",
        "observed_buy_box_fulfillment": "FBA",
        "lowest_returned_offer_price": 49.0,
        "lowest_returned_landed_price": 49.0,
        "highest_returned_landed_price": 50.0,
        "returned_offer_price_spread": 1.0,
        "prime_offer_count": fba,
        "fulfilled_by_amazon_offer_count": fba,
        "estimated_units_per_observed_fba_seller": round(est / fba, 1) if fba else None,
        "estimated_units_per_observed_fbm_seller": round(est / fbm, 1) if fbm else None,
        "estimated_units_per_observed_seller": round(est / observed, 1) if observed else None,
        "seller_share_confidence": "medium" if complete else "low",
        "seller_share_basis": "complete returned offer set (3)",
        "offer_competition_note": None,
        "seller_share_note": "Estimated allocation only.",
    }


def _row(**overrides):
    row = {
        "pack_match": "exact",
        "costco_cost": 15.0,
        "costco_cost_basis": "estimated",
        "economics_confidence": "estimated",
        "economics_status": "estimated_fee_stack",
        "fba_fee": 5.0,
        "net_profit": 9.5,
        "opportunity_score_reasons": ["strong margin"],
    }
    row.update(overrides)
    return row


class RevenueBasisTests(unittest.TestCase):
    def test_buy_box_landed_price_wins_when_supplied(self):
        comp = _competition()
        comp["observed_buy_box_landed_price"] = 52.0
        fields = pa.monthly_pool_fields(_row(), _demand(), comp, candidate_amazon_price=55.0)
        self.assertEqual(fields["estimated_monthly_revenue"], round(1000 * 52.0, 2))
        self.assertEqual(fields["monthly_revenue_basis"], pa.REVENUE_BASIS_BUY_BOX)
        self.assertEqual(fields["monthly_revenue_confidence"], "medium")

    def test_candidate_price_fallback_when_landed_unknown(self):
        fields = pa.monthly_pool_fields(_row(), _demand(), _competition(), candidate_amazon_price=55.0)
        self.assertEqual(fields["estimated_monthly_revenue"], 55000.0)
        self.assertEqual(fields["monthly_revenue_basis"], pa.REVENUE_BASIS_CANDIDATE)

    def test_never_falls_back_to_offer_prices(self):
        comp = _competition()
        comp["observed_buy_box_landed_price"] = None
        comp["lowest_returned_offer_price"] = 40.0
        comp["lowest_returned_landed_price"] = 40.0
        # No candidate-record price either -> Unknown, despite offer prices.
        fields = pa.monthly_pool_fields(_row(), _demand(), comp, candidate_amazon_price=None)
        self.assertIsNone(fields["estimated_monthly_revenue"])
        self.assertIsNone(fields["monthly_revenue_basis"])
        self.assertIsNone(fields["monthly_revenue_confidence"])

    def test_unknown_when_no_estimate_at_all(self):
        demand = _demand()
        demand["estimated_monthly_sales"] = None
        fields = pa.monthly_pool_fields(_row(), demand, _competition(), candidate_amazon_price=55.0)
        self.assertIsNone(fields["estimated_monthly_revenue"])
        self.assertIsNone(fields["estimated_monthly_profit_pool"])
        self.assertIsNone(fields["monthly_pool_note"])

    def test_profit_pool_uses_net_profit_only(self):
        fields = pa.monthly_pool_fields(_row(net_profit=9.5), _demand(), _competition())
        self.assertEqual(fields["estimated_monthly_profit_pool"], round(1000 * 9.5, 2))
        self.assertEqual(fields["monthly_profit_pool_basis"], pa.POOL_BASIS)
        fields2 = pa.monthly_pool_fields(_row(net_profit=None), _demand(), _competition())
        self.assertIsNone(fields2["estimated_monthly_profit_pool"])

    def test_seller_profits_require_share_denominator(self):
        fields = pa.monthly_pool_fields(_row(net_profit=9.5), _demand(), _competition(observed=3, fba=2, fbm=1))
        self.assertEqual(fields["estimated_observed_seller_monthly_profit"], round(333.3 * 9.5, 2))
        self.assertEqual(fields["estimated_fba_seller_monthly_profit"], round(500.0 * 9.5, 2))
        # Unknown roster: no share, no seller profit.
        comp = _competition(observed=None, fba=None, fbm=None, reason="offer_roster_unavailable")
        fields2 = pa.monthly_pool_fields(_row(net_profit=9.5), _demand(), comp)
        self.assertIsNone(fields2["estimated_observed_seller_monthly_profit"])

    def test_disclaimer_present_with_any_pool_value(self):
        fields = pa.monthly_pool_fields(_row(), _demand(), _competition(), candidate_amazon_price=50.0)
        self.assertIn("not a forecast", fields["monthly_pool_note"])
        self.assertIn("modeled", fields["monthly_pool_note"].lower())


class CompletenessTests(unittest.TestCase):
    def test_full_row_scores_high(self):
        snap = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        fields = pa.completeness_dimensions(_row(), _demand(), _competition(), snap)
        self.assertEqual(fields["identity_completeness"], 1.0)
        self.assertEqual(fields["cost_completeness"], 1.0)
        self.assertEqual(fields["economics_completeness"], 1.0)
        self.assertEqual(fields["demand_completeness"], 1.0)
        self.assertEqual(fields["competition_completeness"], 1.0)
        self.assertEqual(fields["freshness_completeness"], 1.0)
        self.assertEqual(fields["total_completeness_score"], 100)

    def test_unknown_roster_scores_competition_zero(self):
        comp = _competition(observed=None, fba=None, fbm=None, reason="offer_roster_unavailable")
        fields = pa.completeness_dimensions(_row(), _demand(), comp, None)
        self.assertEqual(fields["competition_completeness"], 0.0)

    def test_explicit_zero_proof_scores_competition_full(self):
        comp = _competition(observed=0, fba=0, fbm=0, complete=True)
        fields = pa.completeness_dimensions(_row(), _demand(), comp, None)
        self.assertEqual(fields["competition_completeness"], 1.0)

    def test_partial_roster_scores_half(self):
        comp = _competition(observed=2, fba=1, fbm=1, complete=False)
        fields = pa.completeness_dimensions(_row(), _demand(), comp, None)
        self.assertEqual(fields["competition_completeness"], 0.5)


class ReadinessLadderTests(unittest.TestCase):
    def test_complete_opportunity(self):
        snap = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        readiness = pa.portfolio_readiness(_row(), _demand(), _competition(), snap)
        self.assertEqual(readiness, pa.READY_COMPLETE)
        self.assertEqual(pa.portfolio_next_step(readiness), "review_top_opportunity")

    def test_blocked_mismatch(self):
        snap = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        readiness = pa.portfolio_readiness(_row(pack_match="mismatch"), _demand(), _competition(), snap)
        self.assertEqual(readiness, pa.READY_BLOCKED)
        self.assertEqual(pa.portfolio_next_step(readiness), "reject_mismatch")

    def test_needs_costco_mapping(self):
        snap = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        readiness = pa.portfolio_readiness(_row(costco_cost=None), _demand(), _competition(), snap)
        self.assertEqual(readiness, pa.READY_NEEDS_COSTCO)
        self.assertEqual(pa.portfolio_next_step(readiness), "find_costco_match")

    def test_needs_identity_verification(self):
        snap = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        readiness = pa.portfolio_readiness(
            _row(pack_match="candidate", costco_cost_basis="candidate_match"),
            _demand(), _competition(), snap,
        )
        self.assertEqual(readiness, pa.READY_NEEDS_IDENTITY)

    def test_needs_fee_verification(self):
        snap = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        readiness = pa.portfolio_readiness(
            _row(economics_confidence="provisional", fba_fee=None),
            _demand(), _competition(), snap,
        )
        self.assertEqual(readiness, pa.READY_NEEDS_FEE)
        self.assertEqual(pa.portfolio_next_step(readiness), "get_fba_fee_preview")

    def test_needs_bsr_category(self):
        snap = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        demand = _demand()
        demand["estimated_monthly_sales"] = None
        readiness = pa.portfolio_readiness(_row(), demand, _competition(), snap)
        self.assertEqual(readiness, pa.READY_NEEDS_BSR)

    def test_needs_offer_snapshot(self):
        readiness = pa.portfolio_readiness(_row(), _demand(), _competition(), None)
        self.assertEqual(readiness, pa.READY_NEEDS_SNAPSHOT)
        self.assertEqual(pa.portfolio_next_step(readiness), "run_offer_snapshot")

    def test_unknown_roster_never_complete(self):
        snap = _fresh_snapshot(offers=[], offers_returned=0, offers_complete=False, claimed=12)
        comp = _competition(observed=None, fba=None, fbm=None, reason="partial_offer_roster")
        readiness = pa.portfolio_readiness(_row(), _demand(), comp, snap)
        self.assertEqual(readiness, pa.READY_NEEDS_SELLERS)
        self.assertEqual(pa.portfolio_next_step(readiness), "enrich_sellers")

    def test_stale_snapshot(self):
        snap = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        snap["freshness"]["offers_fresh_until"] = (
            datetime.now(timezone.utc) - timedelta(days=2)
        ).isoformat()
        readiness = pa.portfolio_readiness(_row(), _demand(), _competition(), snap)
        self.assertEqual(readiness, pa.READY_STALE)
        self.assertEqual(pa.portfolio_next_step(readiness), "refresh_market_data")


class CategoryRecommendationTests(unittest.TestCase):
    def test_core_replenishable_requires_strong_economics_and_demand(self):
        snap = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        cat = pa.portfolio_category(pa.READY_COMPLETE, _row(net_profit=12.0), _demand(est=2000))
        self.assertEqual(cat, "core_replenishable")

    def test_complete_but_weak_gets_test_buy(self):
        cat = pa.portfolio_category(pa.READY_COMPLETE, _row(net_profit=4.0), _demand(est=2000))
        self.assertEqual(cat, "test_buy_candidate")
        cat2 = pa.portfolio_category(pa.READY_COMPLETE, _row(net_profit=12.0), _demand(est=50))
        self.assertEqual(cat2, "test_buy_candidate")

    def test_blocked_is_avoid(self):
        self.assertEqual(pa.portfolio_category(pa.READY_BLOCKED, _row(), _demand()), "avoid_mismatch")

    def test_unknown_roster_stays_watchlist_not_core(self):
        cat = pa.portfolio_category(pa.READY_NEEDS_SELLERS, _row(net_profit=12.0), _demand(est=2000))
        self.assertEqual(cat, "watchlist")

    def test_fee_verification_is_test_buy(self):
        self.assertEqual(pa.portfolio_category(pa.READY_NEEDS_FEE, _row(), _demand()), "test_buy_candidate")


class RiskFlagTests(unittest.TestCase):
    def test_flags_from_real_facts(self):
        comp = _competition(observed=15, fba=10, fbm=5, complete=False)
        flags = pa.risk_flags(_row(net_profit=3.0), _demand(est=50), comp, None, portfolio_size=1)
        self.assertIn(pa.RISK_THIN_MARGIN, flags)
        self.assertIn(pa.RISK_LOW_DEMAND, flags)
        self.assertIn(pa.RISK_HIGH_COMPETITION, flags)
        self.assertIn(pa.RISK_PARTIAL_SAMPLE, flags)
        self.assertIn(pa.RISK_SINGLE_ASIN, flags)

    def test_unknown_roster_flag(self):
        comp = _competition(observed=None, fba=None, fbm=None, reason="offer_roster_unavailable")
        flags = pa.risk_flags(_row(), _demand(), comp, None, portfolio_size=5)
        self.assertIn(pa.RISK_ROSTER_UNAVAILABLE, flags)

    def test_stale_flag_only_when_explicitly_stale(self):
        stale = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        stale["freshness"]["offers_fresh_until"] = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        flags = pa.risk_flags(_row(), _demand(), _competition(), stale, portfolio_size=5)
        self.assertIn(pa.RISK_STALE, flags)
        fresh = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        flags2 = pa.risk_flags(_row(), _demand(), _competition(), fresh, portfolio_size=5)
        self.assertNotIn(pa.RISK_STALE, flags2)

    def test_no_single_asin_flag_in_multi_row_portfolio(self):
        flags = pa.risk_flags(_row(), _demand(), _competition(), None, portfolio_size=10)
        self.assertNotIn(pa.RISK_SINGLE_ASIN, flags)


class ScoreReasonTests(unittest.TestCase):
    def test_penalties_appended_never_replace(self):
        reasons = pa.enriched_score_reasons(["strong margin", "missing fba fee"], [pa.RISK_THIN_MARGIN])
        self.assertEqual(reasons, ["strong margin", "missing fba fee", "risk: thin_margin"])

    def test_no_score_never_gains_one(self):
        self.assertIsNone(pa.enriched_score_reasons(None, [pa.RISK_THIN_MARGIN]))
        self.assertIsNone(pa.enriched_score_reasons([], []))

    def test_no_risk_flags_keeps_reasons_unchanged(self):
        reasons = pa.enriched_score_reasons(["strong margin"], [])
        self.assertEqual(reasons, ["strong margin"])


class UnknownSellerDataNeverImprovesTests(unittest.TestCase):
    """User-mandated honesty test: absent/unknown seller data must never
    improve score, readiness, seller-share, or opportunity category."""

    def test_readiness_blocks_complete_without_roster(self):
        snap_unknown = _fresh_snapshot(offers=[], offers_returned=0, offers_complete=False, claimed=12)
        comp_unknown = _competition(observed=None, fba=None, fbm=None, reason="partial_offer_roster")
        readiness = pa.portfolio_readiness(_row(), _demand(), comp_unknown, snap_unknown)
        self.assertEqual(readiness, pa.READY_NEEDS_SELLERS)
        snap_known = _fresh_snapshot(offers=[_offer(50.0, fba=True)])
        readiness2 = pa.portfolio_readiness(_row(), _demand(), _competition(), snap_known)
        self.assertEqual(readiness2, pa.READY_COMPLETE)
        self.assertNotEqual(readiness2, readiness)

    def test_category_never_upgrades_to_core_with_unknown_roster(self):
        comp_unknown = _competition(observed=None, fba=None, fbm=None, reason="offer_roster_unavailable")
        cat = pa.portfolio_category(pa.READY_NEEDS_SELLERS, _row(net_profit=99.0), _demand(est=99999))
        self.assertNotEqual(cat, "core_replenishable")

    def test_share_fields_null_with_unknown_roster(self):
        comp_unknown = _competition(observed=None, fba=None, fbm=None, reason="offer_roster_unavailable")
        fields = pa.monthly_pool_fields(_row(net_profit=9.5), _demand(), comp_unknown)
        self.assertIsNone(fields["estimated_observed_seller_monthly_profit"])
        self.assertIsNone(fields["estimated_fba_seller_monthly_profit"])

    def test_score_reasons_never_positive_for_unknown_sellers(self):
        comp_unknown = _competition(observed=None, fba=None, fbm=None, reason="offer_roster_unavailable")
        flags = pa.risk_flags(_row(), _demand(), comp_unknown, None, portfolio_size=1)
        self.assertIn(pa.RISK_ROSTER_UNAVAILABLE, flags)
        reasons = pa.enriched_score_reasons(["strong margin"], flags)
        self.assertIn("risk: offer_roster_unavailable", reasons)

    def test_completeness_competition_zero_for_unknown_roster(self):
        comp_unknown = _competition(observed=None, fba=None, fbm=None, reason="offer_roster_unavailable")
        dims = pa.completeness_dimensions(_row(), _demand(), comp_unknown, None)
        self.assertEqual(dims["competition_completeness"], 0.0)


if __name__ == "__main__":
    unittest.main()