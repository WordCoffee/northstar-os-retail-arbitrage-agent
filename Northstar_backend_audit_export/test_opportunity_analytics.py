"""Offline unit tests for opportunity_analytics.py.

Pure, deterministic, zero network, zero writes. Covers: freshness
labels/basis, verification tasks (vocabulary + priority), match
readiness, data-completeness, opportunity readiness, recommended next
step, the opportunity score (components, blocked rows, None on missing
price/COGS, missing data can never rank best), and the assembled field
payload.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import opportunity_analytics as oa


def _ts(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _row(**overrides) -> Dict[str, Any]:
    row = {
        "name": "Kirkland Signature K-Cups (120 ct)",
        "asin": "B000000001",
        "product_url": "https://www.amazon.com/dp/B000000001",
        "amazon_price": 48.87,
        "costco_cost": 29.99,
        "match_quality": "exact",
        "match_reason": "Exact fingerprint match.",
        "economics_confidence": "estimated",
        "economics_status": "estimated_fee_stack",
        "net_profit": 12.0,
        "roi_pct": 40.0,
        "fba_fee": 8.2,
        "monthly_sales_estimate": 2500.0,
        "total_sellers": 5,
        "fba_sellers": 3,
        "enriched_at": _ts(1),
    }
    row.update(overrides)
    return row


class FreshnessTests(unittest.TestCase):
    def test_fresh_under_7_days(self):
        self.assertEqual(oa.freshness_label(_row(enriched_at=_ts(0.5))), "Fresh")

    def test_aging_between_8_and_30_days(self):
        self.assertEqual(oa.freshness_label(_row(enriched_at=_ts(14))), "Aging")

    def test_stale_over_30_days(self):
        self.assertEqual(oa.freshness_label(_row(enriched_at=_ts(45))), "Stale")

    def test_unknown_when_no_timestamp(self):
        self.assertEqual(oa.freshness_label(_row(enriched_at=None, observed_at=None, imported_at=None)), "Unknown")

    def test_unknown_when_unparseable_timestamp(self):
        self.assertEqual(oa.freshness_label(_row(enriched_at="not-a-date")), "Unknown")

    def test_cache_fetched_at_fallback(self):
        row = _row(enriched_at=None, observed_at=None, imported_at=None)
        meta = {"cache_fetched_at": _ts(2)}
        self.assertEqual(oa.freshness_label(row, meta), "Fresh")
        self.assertEqual(oa.freshness_basis(row, meta), "cache_fetched_at")

    def test_basis_priority_enriched_over_observed_over_cache(self):
        row = _row(enriched_at=_ts(1), observed_at=_ts(2))
        self.assertEqual(oa.freshness_basis(row, {"cache_fetched_at": _ts(3)}), "enriched_at")
        row2 = _row(enriched_at=None, observed_at=_ts(2))
        self.assertEqual(oa.freshness_basis(row2), "observed_at")
        row3 = _row(enriched_at=None, observed_at=None, imported_at=_ts(2))
        self.assertEqual(oa.freshness_basis(row3), "imported_at")


class VerificationTaskTests(unittest.TestCase):
    def test_mismatch_is_blocked(self):
        tasks = oa.verification_tasks(_row(match_quality="mismatch", costco_cost=31.67))
        self.assertEqual(tasks, ["blocked_mismatch"])

    def test_no_costco_candidate(self):
        tasks = oa.verification_tasks(
            _row(match_quality="unknown", costco_cost=None,
                 monthly_sales_estimate=None, total_sellers=None, fba_sellers=None)
        )
        self.assertEqual(tasks, ["no_costco_candidate", "enrich_sales", "enrich_sellers"])

    def test_candidate_rows_verify_upc_and_pack(self):
        tasks = oa.verification_tasks(_row(match_quality="candidate"))
        self.assertIn("verify_upc", tasks)
        self.assertIn("verify_pack", tasks)

    def test_provisional_rows_verify_fba_fee(self):
        tasks = oa.verification_tasks(
            _row(economics_confidence="provisional", economics_status="needs_fee_verification")
        )
        self.assertIn("verify_fba_fee", tasks)

    def test_reason_hints_map_to_tasks(self):
        tasks = oa.verification_tasks(_row(match_quality="high_confidence",
                                           match_reason="Net weight differs (Amazon ... vs Costco ...)"))
        self.assertIn("verify_weight", tasks)
        tasks = oa.verification_tasks(_row(match_quality="high_confidence",
                                           match_reason="Flavor differs: X vs Y"))
        self.assertIn("verify_flavor", tasks)

    def test_missing_sales_and_sellers_enrich(self):
        tasks = oa.verification_tasks(_row(monthly_sales_estimate=None, total_sellers=None, fba_sellers=None))
        self.assertIn("enrich_sales", tasks)
        self.assertIn("enrich_sellers", tasks)

    def test_complete_row_is_none(self):
        self.assertEqual(oa.verification_tasks(_row()), ["none"])

    def test_primary_task_priority(self):
        row = _row(match_quality="candidate", economics_confidence="provisional")
        self.assertEqual(oa.primary_verification_task(oa.verification_tasks(row)), "verify_upc")
        row = _row(match_quality="mismatch")
        self.assertEqual(oa.primary_verification_task(oa.verification_tasks(row)), "blocked_mismatch")
        row = _row(match_quality="exact", economics_confidence="provisional")
        self.assertEqual(oa.primary_verification_task(oa.verification_tasks(row)), "verify_fba_fee")
        row = _row(monthly_sales_estimate=None)
        self.assertEqual(oa.primary_verification_task(oa.verification_tasks(row)), "enrich_sales")
        self.assertIsNone(oa.primary_verification_task([]))


class MatchReadinessTests(unittest.TestCase):
    def test_readiness_mapping(self):
        self.assertEqual(oa.match_readiness(_row(match_quality="exact")), "exact_ready")
        self.assertEqual(oa.match_readiness(_row(match_quality="invoice_confirmed")), "exact_ready")
        self.assertEqual(oa.match_readiness(_row(match_quality="high_confidence")), "likely_verify_pack_upc")
        self.assertEqual(oa.match_readiness(_row(match_quality="candidate")), "candidate_manual_review")
        self.assertEqual(oa.match_readiness(_row(match_quality="mismatch")), "blocked_mismatch")
        self.assertEqual(oa.match_readiness(_row(match_quality="unknown")), "no_costco_match")
        self.assertEqual(oa.match_readiness(_row(match_quality=None)), "no_costco_match")


class CompletenessTests(unittest.TestCase):
    def test_complete_row_scores_100(self):
        self.assertEqual(oa.data_completeness_score(_row()), 100)

    def test_missing_dimensions_lose_points(self):
        row = _row(costco_cost=None, fba_fee=None, monthly_sales_estimate=None,
                   total_sellers=None, fba_sellers=None, economics_confidence="unavailable",
                   match_quality="unknown", enriched_at=None)
        score = oa.data_completeness_score(row)
        self.assertEqual(score, 20)  # identity + amazon price only

    def test_zero_never_scores_as_present(self):
        row = _row(fba_fee=0)
        with_ff = oa.data_completeness_score(row)
        row2 = _row(fba_fee=None)
        self.assertEqual(oa.data_completeness_score(row2), with_ff)
        self.assertLess(oa.data_completeness_score(_row(amazon_price=0)), 100)


class ReadinessAndNextStepTests(unittest.TestCase):
    def test_readiness_labels(self):
        self.assertEqual(oa.opportunity_readiness(_row(match_quality="mismatch")), "blocked_mismatch")
        self.assertEqual(oa.opportunity_readiness(_row(costco_cost=None)), "needs_costco_match")
        self.assertEqual(oa.opportunity_readiness(_row(amazon_price=None)), "needs_price")
        self.assertEqual(
            oa.opportunity_readiness(_row(economics_confidence="provisional")),
            "economics_provisional",
        )
        self.assertEqual(oa.opportunity_readiness(_row(match_quality="candidate")), "needs_identity_verification")
        self.assertEqual(oa.opportunity_readiness(_row(monthly_sales_estimate=None)), "needs_sales_data")
        self.assertEqual(oa.opportunity_readiness(_row(total_sellers=None)), "needs_seller_data")
        self.assertEqual(oa.opportunity_readiness(_row()), "complete_opportunity")

    def test_next_steps(self):
        self.assertEqual(oa.recommended_next_step(_row(match_quality="mismatch")), "reject_mismatch")
        self.assertEqual(oa.recommended_next_step(_row(costco_cost=None)), "find_costco_match")
        self.assertEqual(oa.recommended_next_step(_row(amazon_price=None)), "await_data")
        self.assertEqual(oa.recommended_next_step(_row(economics_confidence="provisional")), "get_fba_fee_preview")
        self.assertEqual(oa.recommended_next_step(_row(match_quality="candidate")), "verify_upc_and_variant")
        self.assertEqual(oa.recommended_next_step(_row(monthly_sales_estimate=None)), "enrich_sales_and_sellers")
        self.assertEqual(oa.recommended_next_step(_row(match_quality="high_confidence")), "verify_costco_pack_and_price")
        self.assertEqual(oa.recommended_next_step(_row()), "review_top_opportunity")


class OpportunityScoreTests(unittest.TestCase):
    def test_mismatch_scores_zero_with_blocked_reason(self):
        score, reasons = oa.opportunity_score(_row(match_quality="mismatch", costco_cost=31.67))
        self.assertEqual(score, 0.0)
        self.assertTrue(reasons[0].startswith("Blocked:"))

    def test_missing_price_never_ranked(self):
        score, reasons = oa.opportunity_score(_row(amazon_price=None))
        self.assertIsNone(score)
        self.assertIn("Missing Amazon price", reasons)

    def test_missing_cogs_never_ranked(self):
        score, _ = oa.opportunity_score(_row(costco_cost=None))
        self.assertIsNone(score)

    def test_full_row_scores_positive_with_reasons(self):
        score, reasons = oa.opportunity_score(_row())
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)
        self.assertTrue(any(r.startswith("economics") for r in reasons))
        self.assertTrue(any(r.startswith("sales velocity") for r in reasons))
        self.assertTrue(any(r.startswith("competition") for r in reasons))
        self.assertTrue(any(r.startswith("match") for r in reasons))

    def test_exact_beats_high_confidence_beats_candidate(self):
        exact = oa.opportunity_score(_row(match_quality="exact"))[0]
        high = oa.opportunity_score(_row(match_quality="high_confidence"))[0]
        candidate = oa.opportunity_score(_row(match_quality="candidate"))[0]
        self.assertGreater(exact, high)
        self.assertGreater(high, candidate)

    def test_missing_sales_never_ranks_above_complete(self):
        complete = oa.opportunity_score(_row())[0]
        missing_sales = oa.opportunity_score(
            _row(monthly_sales_estimate=None, total_sellers=None, fba_sellers=None)
        )[0]
        self.assertGreater(complete, missing_sales)

    def test_completeness_factor_penalizes_missing_dimensions(self):
        complete = oa.opportunity_score(_row())[0]
        partial = oa.opportunity_score(_row(fba_sellers=None))[0]
        self.assertGreater(complete, partial)
        reasons = oa.opportunity_score(_row(fba_sellers=None))[1]
        self.assertTrue(any(r.startswith("completeness") for r in reasons))

    def test_zero_roi_still_uses_sales_and_match(self):
        score, reasons = oa.opportunity_score(_row(roi_pct=0.0, net_profit=0.0))
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0)


class OpportunityFieldsTests(unittest.TestCase):
    def test_fields_assembled(self):
        fields = oa.opportunity_fields(_row())
        self.assertEqual(fields["match_readiness"], "exact_ready")
        self.assertEqual(fields["primary_verification_task"], "none")
        self.assertEqual(fields["opportunity_readiness"], "complete_opportunity")
        self.assertEqual(fields["recommended_next_step"], "review_top_opportunity")
        self.assertEqual(fields["data_completeness_score"], 100)
        self.assertEqual(fields["freshness_label"], "Fresh")
        self.assertEqual(fields["freshness_basis"], "enriched_at")
        self.assertEqual(fields["opportunity_score_reasons"], oa.opportunity_score(_row())[1])

    def test_match_evidence_fallback(self):
        fields = oa.opportunity_fields(_row())
        self.assertEqual(fields["match_evidence"]["match_quality"], "exact")
        fields2 = oa.opportunity_fields(_row(match_evidence={"evidence": {"title_dice": 0.5}}))
        self.assertEqual(fields2["match_evidence"]["evidence"]["title_dice"], 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
