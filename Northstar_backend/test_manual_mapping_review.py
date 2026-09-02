"""Focused offline tests for the manual mapping-resolution record writer.

No provider / network calls. Validates that the B0CP6LXPLK review record
is schema-complete, carries the required identity/purchase/validation
statuses, and contains NO purchase authorization or benchmark-mutation
recommendation.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import manual_mapping_review as mmr

REVIEW_PATH = os.path.join(
    "data", "batch", "manual-mapping-review", "B0CP6LXPLK-review.json"
)

REQUIRED_KEYS = [
    "asin",
    "status",
    "identity_status",
    "purchase_status",
    "provider_validation_status",
    "source_preflight_run_ids",
    "failure_run_directory",
    "failure_manifest_sha256",
    "benchmark_title",
    "benchmark_title_variants",
    "title_conflict",
    "live_returned_title",
    "mapping_outcome",
    "reason",
    "conclusion_about_correct_source",
    "purchase_authorization",
    "benchmark_mutation_recommendation",
    "next_required_evidence",
]


class ManualMappingReviewRecordTests(unittest.TestCase):
    def test_built_record_has_all_required_keys(self):
        rec = mmr.build_review_record()
        for key in REQUIRED_KEYS:
            self.assertIn(key, rec, "missing required key: %s" % key)

    def test_built_record_status_values(self):
        rec = mmr.build_review_record()
        self.assertEqual(rec["asin"], "B0CP6LXPLK")
        self.assertEqual(rec["status"], "manual_resolution_required")
        self.assertEqual(rec["identity_status"], "manual_resolution_required")
        self.assertEqual(rec["purchase_status"], "blocked")
        self.assertEqual(
            rec["provider_validation_status"],
            "unresolved_nonconflict_mapping_mismatch",
        )

    def test_built_record_mapping_fields(self):
        rec = mmr.build_review_record()
        self.assertEqual(rec["benchmark_title"], "Minoxidil Extra Strength (6-mo)")
        self.assertIs(rec["title_conflict"], False)
        self.assertEqual(rec["mapping_outcome"], "unexpected_mapping_mismatch")
        self.assertIn(
            "proof-batch-preflight-attempt-2-20260819T030931Z",
            rec["source_preflight_run_ids"],
        )
        self.assertEqual(
            len(rec["failure_manifest_sha256"]), 64
        )

    def test_no_purchase_authorization_or_benchmark_mutation(self):
        rec = mmr.build_review_record()
        self.assertIsNone(rec["purchase_authorization"])
        self.assertIsNone(rec["benchmark_mutation_recommendation"])
        self.assertIsNone(rec["conclusion_about_correct_source"])

    def test_next_required_evidence_has_six_items(self):
        rec = mmr.build_review_record()
        self.assertEqual(len(rec["next_required_evidence"]), 6)

    def test_on_disk_record_matches_schema(self):
        self.assertTrue(
            os.path.exists(REVIEW_PATH),
            "review record not found at %s" % REVIEW_PATH,
        )
        with open(REVIEW_PATH, "r", encoding="utf-8") as fh:
            rec = json.load(fh)
        for key in REQUIRED_KEYS:
            self.assertIn(key, rec, "on-disk record missing key: %s" % key)
        self.assertEqual(rec["asin"], "B0CP6LXPLK")
        self.assertEqual(rec["status"], "manual_resolution_required")
        self.assertEqual(rec["mapping_outcome"], "unexpected_mapping_mismatch")
        self.assertIsNone(rec["purchase_authorization"])
        self.assertIsNone(rec["benchmark_mutation_recommendation"])

    def test_writer_atomic_roundtrip(self):
        rec = mmr.build_review_record()
        tmp = os.path.join(
            "data", "batch", "manual-mapping-review", "_tmp_test_review.json"
        )
        try:
            path = mmr.write_review_record(rec, tmp)
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.assertEqual(loaded["asin"], "B0CP6LXPLK")
            self.assertEqual(
                loaded["provider_validation_status"],
                "unresolved_nonconflict_mapping_mismatch",
            )
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
