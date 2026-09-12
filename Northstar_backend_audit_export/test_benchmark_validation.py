"""Offline tests for the benchmark comparison engine (benchmark_validation.py).

Covers: identity (exact/likely/pack-mismatch/unavailable), price
classification (exact/within/moderate/material/unavailable), review trend,
BSR/category rules, seller internal-consistency, economics/demand internal
labels, batch metrics, and zero provider calls.
"""

import unittest
from unittest import mock

import benchmark_validation as bv

BENCH = {
    "asin": "B00BISGJXA",
    "title": "Stool Softener 100mg (400ct)",
    "price": 12.75,
    "reviews": 18629,
    "prime_fba": "yes",
    "bsr_rank_number": 4960,
    "bsr_category": "Health & Household",
    "capture_time_status": "unknown",
    "source_files": ["BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv"],
}


def _snapshot(overrides=None, market=None, identity=None, economics=None, demand=None, cost=None, fees=None, provenance=None):
    facts = {
        "identity": {"name": "Stool Softener 100mg (400ct)", "reviews_count": 19000},
        "cost": {"cost_status": "invoice_confirmed"},
        "fees": {"fba_fee": {"source": "fee_engine"}, "referral_fee": {"method": "category_rule"}},
        "demand": {
            "estimated_monthly_sales": 3000,
            "sales_estimation_method": "bsr_category_model",
            "sales_estimation_confidence": "medium",
            "bsr": 4200,
            "bsr_category": "Health & Household",
        },
        "market": {
            "amazon_price": 12.99,
            "prime_fba": "yes",
            "buy_box": {"available": True, "price": 12.99, "fulfillment": "FBA", "observed_at": "2026-08-17T12:00:00+00:00"},
            "seller_counts": {"total_observed": 12, "fba_observed": 8, "fbm_observed": 4, "amazon_observed": 0},
            "coverage": {"offer_list_available": True, "offers_complete_status": "full"},
            "offers": [{"price": 12.99, "fulfillment": "FBA", "is_buy_box_winner": True}],
        },
        "economics": {"net_profit": 3.1, "roi_pct": 31.4, "economics_confidence": "estimated"},
        "provenance": {"market.seller_counts": {"source": "easyparser", "fetched_at": "2026-08-17T12:00:00+00:00"}},
    }
    if identity is not None:
        facts["identity"].update(identity)
    if market is not None:
        facts["market"].update(market)
    if economics is not None:
        facts["economics"].update(economics)
    if demand is not None:
        facts["demand"].update(demand)
    if cost is not None:
        facts["cost"].update(cost)
    if fees is not None:
        facts["fees"].update(fees)
    if provenance is not None:
        facts["provenance"].update(provenance)
    return {
        "schema_version": 1,
        "asin": "B00BISGJXA",
        "ingested_at": "2026-08-17T12:00:00+00:00",
        "sources": {},
        "facts": facts,
    }


class IdentityTests(unittest.TestCase):
    def test_exact_title_and_pack_match(self):
        result = bv.compare_identity("Stool Softener 100mg (400ct)", "Stool Softener 100mg (400ct)")
        self.assertEqual(result["title_status"], "match")
        self.assertEqual(result["pack_status"], "match")
        self.assertFalse(result["pack_mismatch_block"])

    def test_likely_title_match(self):
        result = bv.compare_identity(
            "Aller-Flo Fluticasone (Pack of 5)", "Aller-Flo Fluticasone (5 Pack)"
        )
        self.assertEqual(result["title_status"], "likely_match")

    def test_pack_mismatch_never_auto_resolved(self):
        result = bv.compare_identity(
            "Sleep Aid Doxylamine (2pk/192ct)", "Sleep Aid Doxylamine (96ct)"
        )
        self.assertEqual(result["pack_status"], "conflict")
        self.assertTrue(result["pack_mismatch_block"])
        self.assertIn("NEVER auto-resolved", result["note"])

    def test_title_mismatch(self):
        result = bv.compare_identity("Compactor Trash Bag", "Minoxidil Extra Strength")
        self.assertEqual(result["title_status"], "mismatch")
        self.assertLess(result["title_similarity"], 0.55)

    def test_unavailable_when_title_missing(self):
        result = bv.compare_identity(None, "Compactor Trash Bag")
        self.assertEqual(result["title_status"], "unavailable")
        self.assertIsNone(result["title_similarity"])

    def test_asin_match_in_full_record(self):
        report = bv.compare_benchmark_record(BENCH, _snapshot())
        self.assertEqual(report["identity"]["asin_match"], "pass")
        bad = _snapshot()
        bad["asin"] = "B0000000000"
        report = bv.compare_benchmark_record(BENCH, bad)
        self.assertEqual(report["identity"]["asin_match"], "fail")


class PriceTests(unittest.TestCase):
    def _price(self, b, l):
        return bv.compare_price(b, l)

    def test_exact(self):
        result = self._price(12.75, 12.75)
        self.assertEqual(result["classification"], "exact")
        self.assertEqual(result["absolute_variance"], 0.0)
        self.assertTrue(result["comparable"])

    def test_within_tolerance(self):
        result = self._price(12.75, 12.99)
        self.assertEqual(result["classification"], "within_tolerance")
        self.assertAlmostEqual(result["percent_variance"], 0.0188, places=3)

    def test_moderate_drift(self):
        result = self._price(12.75, 13.60)
        self.assertEqual(result["classification"], "moderate_drift")

    def test_material_drift(self):
        result = self._price(12.75, 16.00)
        self.assertEqual(result["classification"], "material_drift")
        self.assertIn("freshness/context review", result["note"])
        self.assertIn("not a provider error", result["note"])

    def test_unavailable(self):
        result = self._price(None, 12.99)
        self.assertEqual(result["classification"], "unavailable")
        self.assertFalse(result["comparable"])
        result = self._price(12.75, None)
        self.assertEqual(result["classification"], "unavailable")

    def test_capture_time_status_on_drift(self):
        result = self._price(12.75, 16.00)
        self.assertEqual(result["capture_time_status"], "unknown")


class ReviewTests(unittest.TestCase):
    def test_expected_growth(self):
        result = bv.compare_reviews(18629, 19234)
        self.assertEqual(result["trend"], "expected_growth")
        self.assertEqual(result["direction"], "up")

    def test_decline_flagged_not_failed(self):
        result = bv.compare_reviews(18629, 15000)
        self.assertEqual(result["trend"], "decline_flag")
        self.assertIn("not auto-failed", result["note"])

    def test_unchanged(self):
        result = bv.compare_reviews(18629, 18629)
        self.assertEqual(result["trend"], "unchanged")

    def test_unavailable(self):
        result = bv.compare_reviews(None, 19234)
        self.assertEqual(result["trend"], "unavailable")
        self.assertFalse(result["comparable"])


class PrimeFbaTests(unittest.TestCase):
    def test_match(self):
        result = bv.compare_prime_fba("yes", "yes")
        self.assertEqual(result["status"], "match")

    def test_changed_not_error(self):
        result = bv.compare_prime_fba("yes", "no")
        self.assertEqual(result["status"], "changed")
        self.assertIn("does not imply provider error", result["note"])

    def test_unavailable(self):
        result = bv.compare_prime_fba(None, "yes")
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["comparable"])


class BsrTests(unittest.TestCase):
    def test_comparable_and_change(self):
        result = bv.compare_bsr(4960, "Health & Household", 4210, "Health & Household")
        self.assertTrue(result["comparable"])
        self.assertEqual(result["category_context"], "match")
        self.assertEqual(result["observed_change"], -750.0)
        self.assertEqual(result["direction"], "improved_rank")
        self.assertIn("not provider inaccuracy", result["note"])

    def test_category_mismatch_flagged(self):
        result = bv.compare_bsr(4960, "Health & Household", 4210, "Beauty & Personal Care")
        self.assertFalse(result["comparable"])
        self.assertEqual(result["category_context"], "mismatch")

    def test_missing_rank_unavailable(self):
        result = bv.compare_bsr(None, "Health & Household", 4210, "Health & Household")
        self.assertFalse(result["comparable"])
        self.assertEqual(result["category_context"], "unavailable")


class OfferSectionTests(unittest.TestCase):
    def test_full_consistent(self):
        result = bv.validate_offer_section(_snapshot())
        self.assertTrue(result["present"])
        self.assertEqual(result["coverage"], "full")
        self.assertEqual(result["internal_consistency"]["status"], "consistent")
        self.assertTrue(result["buy_box_present"])
        self.assertEqual(result["label"], bv.INTERNAL_ONLY_LABEL)

    def test_inconsistent_counts(self):
        snap = _snapshot(market={"seller_counts": {"total_observed": 10, "fba_observed": 8, "fbm_observed": 4}})
        result = bv.validate_offer_section(snap)
        self.assertEqual(result["internal_consistency"]["status"], "inconsistent")

    def test_missing_counts_unavailable(self):
        snap = _snapshot(market={"seller_counts": {"total_observed": None, "fba_observed": None, "fbm_observed": None}})
        result = bv.validate_offer_section(snap)
        self.assertEqual(result["internal_consistency"]["status"], "unavailable")

    def test_buy_box_without_offer_data_flagged(self):
        snap = _snapshot(
            market={
                "buy_box": {"available": True, "price": 12.99},
                "seller_counts": {"total_observed": None, "fba_observed": None, "fbm_observed": None},
                "coverage": {"offer_list_available": False, "offers_complete_status": "unknown"},
                "offers": [],
            }
        )
        result = bv.validate_offer_section(snap)
        self.assertFalse(result["present"])
        self.assertEqual(result["buy_box_requires_offer_data"]["status"], "warning")


class EconomicsDemandTests(unittest.TestCase):
    def test_decision_ready_with_provenance(self):
        result = bv.validate_economics_internal(_snapshot())
        self.assertEqual(result["readiness"], "decision_ready")
        self.assertEqual(result["label"], bv.INTERNAL_ONLY_LABEL)

    def test_unavailable_when_roi_missing(self):
        result = bv.validate_economics_internal(_snapshot(economics={"roi_pct": None, "net_profit": None}))
        self.assertEqual(result["readiness"], "unavailable")

    def test_roi_zero_flagged(self):
        result = bv.validate_economics_internal(_snapshot(economics={"roi_pct": 0, "net_profit": 0}))
        self.assertEqual(result["readiness"], "unavailable")
        self.assertIn("unknown must be null", result["note"])

    def test_assumption_based_without_cost_provenance(self):
        snap = _snapshot(cost={"cost_status": "unavailable"}, fees={"fba_fee": None})
        result = bv.validate_economics_internal(snap)
        self.assertEqual(result["readiness"], "assumption_based")

    def test_demand_internal_labels(self):
        result = bv.validate_demand_internal(_snapshot())
        self.assertTrue(result["bsr_input_present"])
        self.assertEqual(result["estimation_method"], "bsr_category_model")
        self.assertEqual(result["label"], bv.DEMAND_LABEL)

    def test_demand_zero_flagged(self):
        snap = _snapshot(demand={"estimated_monthly_sales": 0})
        result = bv.validate_demand_internal(snap)
        self.assertIn("unknown must be null", result["note"])

    def test_not_externally_benchmarked_labels_present(self):
        report = bv.compare_benchmark_record(BENCH, _snapshot())
        self.assertEqual(report["economics"]["label"], bv.INTERNAL_ONLY_LABEL)
        self.assertEqual(report["demand"]["label"], bv.DEMAND_LABEL)
        self.assertEqual(report["internally_validated"]["label"], bv.INTERNAL_ONLY_LABEL)


class BatchMetricsTests(unittest.TestCase):
    def _reports(self):
        matched = bv.compare_benchmark_record(BENCH, _snapshot())
        drift = bv.compare_benchmark_record(
            dict(BENCH, price=12.75),
            _snapshot(market={"amazon_price": 16.00}),
        )
        unmatched = {
            "asin": "B0UNKNOWN01",
            "identity": {"asin_match": "fail"},
        }
        return [matched, drift, unmatched]

    def test_batch_metrics(self):
        metrics = bv.summarize_batch(self._reports())
        self.assertEqual(metrics["benchmark_matched_asin_count"], 2)
        self.assertEqual(metrics["unmatched_asin_count"], 1)
        self.assertEqual(metrics["price_comparable_count"], 2)
        self.assertEqual(metrics["price_exact_count"], 0)
        self.assertEqual(metrics["price_within_tolerance_count"], 1)
        self.assertEqual(metrics["price_material_drift_count"], 1)
        self.assertEqual(metrics["review_comparable_count"], 2)
        self.assertEqual(metrics["prime_fba_comparable_count"], 2)
        self.assertEqual(metrics["bsr_comparable_count"], 2)
        self.assertEqual(metrics["market_snapshot_coverage"]["seller_roster_present"], 2)
        self.assertEqual(metrics["market_snapshot_coverage"]["coverage_full"], 2)
        self.assertEqual(metrics["economics_readiness"]["decision_ready"], 2)

    def test_no_single_accuracy_percentage(self):
        metrics = bv.summarize_batch(self._reports())
        keys = set(metrics)
        self.assertNotIn("accuracy_percentage", keys)
        self.assertNotIn("overall_accuracy", keys)
        self.assertTrue(metrics["benchmark_limitations"]["capture_time_unknown"])
        self.assertIn("not live market stability", metrics["benchmark_limitations"]["price_bsr_drift_expected"])

    def test_decline_flag_count(self):
        reports = [bv.compare_benchmark_record(BENCH, _snapshot(identity={"reviews_count": 15000}))]
        metrics = bv.summarize_batch(reports)
        self.assertEqual(metrics["review_decline_flag_count"], 1)


class ContainmentTests(unittest.TestCase):
    def test_compare_makes_zero_provider_calls(self):
        import bright_data_client
        import scavio_client
        import amazon_search
        import offer_enrichment
        import canopy_client
        import easyparser_client
        import costco_api_client

        def _boom(*args, **kwargs):
            raise AssertionError("provider call made during offline comparison")

        patches = (
            mock.patch.object(bright_data_client, "search_products", side_effect=_boom),
            mock.patch.object(bright_data_client, "get_product_detail", side_effect=_boom),
            mock.patch.object(scavio_client, "search_kirkland_products", side_effect=_boom),
            mock.patch.object(amazon_search, "_search_brightdata", side_effect=_boom),
            mock.patch.object(amazon_search, "_search_chocodata", side_effect=_boom),
            mock.patch.object(offer_enrichment, "get_easyparser_offers", side_effect=_boom),
            mock.patch.object(offer_enrichment, "get_offer_data", side_effect=_boom),
            mock.patch.object(canopy_client.requests, "get", side_effect=_boom),
            mock.patch.object(costco_api_client.requests, "get", side_effect=_boom),
            mock.patch.object(easyparser_client.requests, "get", side_effect=_boom),
        )
        for p in patches:
            p.start()
        try:
            report = bv.compare_benchmark_record(BENCH, _snapshot())
            self.assertEqual(report["identity"]["asin_match"], "pass")
            self.assertIsNotNone(bv.summarize_batch([report]))
        finally:
            for p in reversed(patches):
                p.stop()


if __name__ == "__main__":
    unittest.main()
