"""Offline tests for the proof-batch envelope + fixture comparison support
(proof_batch.py; plan: docs/user-selected-20-asin-validation-run.md).

Covers: envelope build/validation through intel_schema, secret-like key
rejection, error sanitization, fixture-only run results (explicit paths
only), benchmark comparisons, price drift classification, batch report
(no universal accuracy percentage), unknown-never-zero, zero provider calls.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import intel_schema
import proof_batch as pb

from benchmark_validation import INTERNAL_ONLY_LABEL, DEMAND_LABEL

REAL_REFERENCE = "data/benchmarks/asin_benchmark_reference.json"


def _load_reference():
    with open(REAL_REFERENCE, encoding="utf-8") as fh:
        return json.load(fh)


def _valid_snapshot(asin="B00BISGJXA"):
    return {
        "schema_version": intel_schema.SCHEMA_VERSION,
        "asin": asin,
        "ingested_at": "2026-08-18T12:00:00+00:00",
        "sources": {"fixture": {"kind": "synthetic"}},
        "facts": {
            "identity": {"name": "Stool Softener 100mg (400ct)", "reviews_count": 18931},
            "cost": {"cost_status": "costco_online_discovery", "costco_cost": None},
            "fees": {"fba_fee": None, "fba_fee_status": "unavailable"},
            "demand": {
                "estimated_monthly_sales": None,
                "sales_estimation_method": "unknown",
                "sales_estimation_confidence": "unknown",
                "bsr": 4210,
                "bsr_category": "Health & Household",
            },
            "market": {
                "amazon_price": 13.13,
                "buy_box": {"available": False, "price": None, "seller_name": None, "seller_id": None, "fulfillment": None, "source": None, "observed_at": None},
                "seller_counts": {"total_observed": None, "fba_observed": None, "fbm_observed": None, "amazon_observed": None, "claimed_total": None},
                "coverage": {"offer_list_available": False, "offers_complete_status": "unknown", "coverage_reason": "fixture"},
                "offers": [],
            },
            "economics": {"net_profit": None, "roi_pct": None, "economics_confidence": "unavailable", "economics_status": "missing_market_or_cost_inputs"},
            "provenance": {
                "identity.name": {"source": "fixture", "fetched_at": "2026-08-18T12:00:00+00:00"},
                "demand.bsr": {"source": "fixture", "fetched_at": "2026-08-18T12:00:00+00:00"},
                "demand.bsr_category": {"source": "fixture", "fetched_at": "2026-08-18T12:00:00+00:00"},
                "market.amazon_price": {"source": "fixture", "fetched_at": "2026-08-18T12:00:00+00:00"},
            },
        },
    }


class EnvelopeTests(unittest.TestCase):
    def test_build_and_validate_ok(self):
        env = pb.build_envelope(
            run_id="proof-20260818-0001",
            asin="B00BISGJXA",
            provider="EASYPARSER",
            requested_fields=["market_offers"],
            snapshot=_valid_snapshot(),
        )
        self.assertEqual(pb.validate_envelope(env), [])

    def test_validate_rejects_bad_snapshot_via_intel_schema(self):
        bad = _valid_snapshot()
        bad["facts"]["market"]["amazon_price"] = 0  # ZERO_FORBIDDEN
        env = pb.build_envelope(run_id="r1", asin="B00BISGJXA", provider="EASYPARSER", requested_fields=[], snapshot=bad)
        errors = pb.validate_envelope(env)
        self.assertTrue(any("amazon_price is 0" in e for e in errors))

    def test_validate_rejects_bad_asin_and_provider(self):
        env = pb.build_envelope(run_id="r1", asin="BAD", provider="NOTAPROVIDER", requested_fields=[], snapshot=_valid_snapshot(asin="B00BISGJXA"))
        errors = pb.validate_envelope(env)
        self.assertTrue(any("asin must be" in e for e in errors))
        self.assertTrue(any("provider must be" in e for e in errors))

    def test_secret_like_keys_rejected(self):
        env = pb.build_envelope(run_id="r1", asin="B00BISGJXA", provider="EASYPARSER", requested_fields=[], snapshot=_valid_snapshot())
        env["snapshot"]["sources"]["fixture"]["api_token"] = "sk-12345"
        self.assertTrue(pb.contains_secret_like(env))
        self.assertTrue(any("secret-like" in e for e in pb.validate_envelope(env)))

    def test_sanitize_error_shape(self):
        self.assertEqual(pb.sanitize_error(None), None)
        self.assertEqual(pb.sanitize_error({"code": "E1", "message": "boom"}), {"code": "E1", "message": "boom"})
        scrubbed = pb.sanitize_error({"code": "E1", "message": "detail"})
        self.assertEqual(len(scrubbed["message"]), 6)
        env = pb.build_envelope(run_id="r1", asin="B00BISGJXA", provider="EASYPARSER", requested_fields=[], snapshot=_valid_snapshot(), provider_status="error", error={"code": "E1", "message": "boom"})
        self.assertEqual(pb.validate_envelope(env), [])

    def test_error_status_requires_error_object(self):
        env = pb.build_envelope(run_id="r1", asin="B00BISGJXA", provider="EASYPARSER", requested_fields=[], snapshot=_valid_snapshot(), provider_status="error", error=None)
        self.assertTrue(any("requires an error object" in e for e in pb.validate_envelope(env)))

    def test_unknown_never_becomes_zero(self):
        snap = _valid_snapshot()
        snap["facts"]["market"]["amazon_price"] = None
        snap["facts"]["identity"]["reviews_count"] = None
        env = pb.build_envelope(run_id="r1", asin="B00BISGJXA", provider="EASYPARSER", requested_fields=[], snapshot=snap)
        report = pb.compare_envelope(_load_reference(), env)
        self.assertIsNone(report["price"]["absolute_variance"])
        self.assertEqual(report["price"]["classification"], "unavailable")
        self.assertIsNone(report["reviews"]["percent_change"])
        self.assertEqual(report["economics"]["readiness"], "unavailable")
        self.assertIsNone(snap["facts"]["cost"]["costco_cost"])


class FixtureRunTests(unittest.TestCase):
    def test_fixture_envelopes_valid_and_comparable(self):
        reference = _load_reference()
        envelopes = pb.build_fixture_envelopes(reference)
        self.assertEqual(len(envelopes), 2)
        for env in envelopes:
            self.assertEqual(pb.validate_envelope(env), [])
            self.assertEqual(env["result_status"], "fixture")
        report = pb.compare_envelope(reference, envelopes[0])
        self.assertEqual(report["identity"]["asin_match"], "pass")
        self.assertEqual(report["identity"]["title_status"], "match")
        self.assertIn(report["price"]["classification"], ("exact", "within_tolerance", "moderate_drift", "material_drift", "unavailable"))

    def test_price_drift_classification_via_envelope(self):
        reference = _load_reference()
        bench = reference["canonical"]["B00BISGJXA"]
        base = bench["price"]
        snap = pb.fixture_snapshot_for(bench, round(base * 1.20, 2))
        env = pb.build_envelope(run_id="r2", asin="B00BISGJXA", provider="EASYPARSER", requested_fields=[], snapshot=snap)
        report = pb.compare_envelope(reference, env)
        self.assertEqual(report["price"]["classification"], "material_drift")
        self.assertIn("freshness/context review", report["price"]["note"])

    def test_fixture_run_writes_only_to_explicit_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "fixture-envelopes.json")
            result = subprocess.run(
                [sys.executable, "proof_batch.py", "fixture-run", "--out", out],
                capture_output=True, text=True, cwd=os.path.dirname(__file__),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.isfile(out))
            payload = json.load(open(out, encoding="utf-8"))
            self.assertEqual(payload["kind"], "fixture-envelopes")
            self.assertIn("SYNTHETIC FIXTURE", payload["note"])
            self.assertEqual(len(payload["envelopes"]), 2)

    def test_cli_report_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "fixture-envelopes.json")
            subprocess.run([sys.executable, "proof_batch.py", "fixture-run", "--out", out], check=True, capture_output=True, cwd=os.path.dirname(__file__))
            report_path = os.path.join(tmp, "report.json")
            with open(report_path, "w", encoding="utf-8") as fh:
                json.dump(pb.build_batch_report(_load_reference(), json.load(open(out, encoding="utf-8"))["envelopes"]), fh, default=str)
            payload = json.load(open(report_path, encoding="utf-8"))
            self.assertEqual(payload["envelope_count"], 2)
            self.assertIn("metrics", payload)


class BatchReportTests(unittest.TestCase):
    def test_report_has_no_universal_accuracy_percentage(self):
        reference = _load_reference()
        envelopes = pb.build_fixture_envelopes(reference)
        report = pb.build_batch_report(reference, envelopes)
        self.assertNotIn("accuracy_percentage", report["metrics"])
        self.assertNotIn("overall_accuracy", report["metrics"])
        self.assertTrue(report["limitations"]["no_universal_accuracy_percentage"])
        self.assertTrue(report["limitations"]["capture_time_unknown"])
        self.assertTrue(report["limitations"]["market_drift_is_not_provider_error"])
        self.assertEqual(report["metrics"]["benchmark_matched_asin_count"], 2)
        self.assertEqual(report["metrics"]["unmatched_asin_count"], 0)

    def test_internally_validated_labels(self):
        reference = _load_reference()
        env = pb.build_fixture_envelopes(reference)[0]
        report = pb.compare_envelope(reference, env)
        self.assertEqual(report["economics"]["label"], INTERNAL_ONLY_LABEL)
        self.assertEqual(report["demand"]["label"], DEMAND_LABEL)
        self.assertNotEqual(report["economics"]["readiness"], "decision_ready")

    def test_unmatched_envelope_flagged(self):
        env = pb.build_envelope(run_id="r9", asin="B0NOTINDB01", provider="EASYPARSER", requested_fields=[], snapshot=_valid_snapshot(asin="B0NOTINDB01"))
        report = pb.compare_envelope(_load_reference(), env)
        self.assertEqual(report["identity"]["asin_match"], "fail")
        metrics = pb.build_batch_report(_load_reference(), [env])["metrics"]
        self.assertEqual(metrics["benchmark_matched_asin_count"], 0)
        self.assertEqual(metrics["unmatched_asin_count"], 1)

    def test_bsr_category_mismatch_flag(self):
        reference = _load_reference()
        bench = reference["canonical"]["B00BISGJXA"]
        snap = pb.fixture_snapshot_for(bench, bench["price"])
        snap["facts"]["demand"]["bsr_category"] = "Beauty & Personal Care"
        env = pb.build_envelope(run_id="r3", asin="B00BISGJXA", provider="EASYPARSER", requested_fields=[], snapshot=snap)
        report = pb.build_batch_report(reference, [env])
        self.assertIn("B00BISGJXA", report["mapping_mismatch_flags"])


class ContainmentTests(unittest.TestCase):
    def test_no_network_imports_in_proof_batch(self):
        src = "".join(open(pb.__file__, encoding="utf-8").readlines())
        self.assertNotIn("import requests", src)
        self.assertNotIn("import httpx", src)
        self.assertNotIn("urllib", src)

    def test_proof_batch_operations_make_zero_provider_calls(self):
        import bright_data_client
        import scavio_client
        import amazon_search
        import offer_enrichment
        import canopy_client
        import easyparser_client
        import costco_api_client

        def _boom(*args, **kwargs):
            raise AssertionError("provider call made during offline proof-batch operation")

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
            reference = _load_reference()
            env = pb.build_fixture_envelopes(reference)[0]
            self.assertEqual(pb.validate_envelope(env), [])
            self.assertEqual(pb.compare_envelope(reference, env)["identity"]["asin_match"], "pass")
            self.assertIsNotNone(pb.build_batch_report(reference, [env]))
        finally:
            for p in reversed(patches):
                p.stop()


if __name__ == "__main__":
    unittest.main()
