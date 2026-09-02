"""Offline tests for the mapping-review CLI (mapping_review).

Covers review-row generation, suggested actions per match quality,
coverage metrics, read-only import validation (never writes the
ledger), append-only audit, CSV writing, and byte-identity guards
proving the real cache, snapshot store, Costco CSV, and ledger files
are untouched by this module.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import csv
import glob
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import mapping_review as mr

_TMP = tempfile.mkdtemp(prefix="mapping-review-test-")
LEDGER_PATH = os.path.join(_TMP, "costco-amazon-mapping.json")

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REAL_CACHE = os.path.join(_BACKEND_DIR, "data", "scanner-search-cache.json")
_REAL_BACKUPS = sorted(
    glob.glob(os.path.join(_BACKEND_DIR, "data", "scanner-search-cache.brightdata-*.json"))
)
_REAL_SNAPSHOTS = os.path.join(_BACKEND_DIR, "data", "amazon-market-snapshots.json")
_REAL_COSTCO_CSV = os.path.join(_BACKEND_DIR, "data", "costco-items.csv")

if os.path.exists(_REAL_CACHE):
    _CACHE_SHA = hashlib.sha256(open(_REAL_CACHE, "rb").read()).hexdigest()
else:
    _CACHE_SHA = None
if _REAL_BACKUPS:
    _BACKUP_SHA = hashlib.sha256(open(_REAL_BACKUPS[0], "rb").read()).hexdigest()
else:
    _BACKUP_SHA = None
if os.path.exists(_REAL_SNAPSHOTS):
    _SNAPSHOTS_SHA = hashlib.sha256(open(_REAL_SNAPSHOTS, "rb").read()).hexdigest()
else:
    _SNAPSHOTS_SHA = None
if os.path.exists(_REAL_COSTCO_CSV):
    _COSTCO_CSV_SHA = hashlib.sha256(open(_REAL_COSTCO_CSV, "rb").read()).hexdigest()
else:
    _COSTCO_CSV_SHA = None


def _sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _candidate(asin="B00GYZWNY6", name="Kirkland Signature Paper Towels 12 Pack", **extra):
    row = {"asin": asin, "name": name}
    row.update(extra)
    return row


def _costco(match_quality="exact", item_name="Kirkland Signature Paper Towels", **extra):
    row = {
        "match_quality": match_quality,
        "item_name": item_name,
        "costco_item_id": "12345",
        "costco_cost": 18.99,
        "evidence": {},
    }
    row.update(extra)
    return row


class ReviewRowTests(unittest.TestCase):
    def test_no_costco_candidate_stays_unknown(self):
        with patch("product_analysis.get_costco_price", return_value=None):
            rows = mr.review_rows([_candidate()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["match_quality"], "unknown")
        self.assertEqual(rows[0]["suggested_action"], mr.ACTION_NO_CANDIDATE)
        self.assertIsNone(rows[0]["costco_candidate_title"])

    def test_exact_with_upc_confirms(self):
        with patch("product_analysis.get_costco_price", return_value=_costco("exact")):
            rows = mr.review_rows([_candidate(upc="096619330192")])
        self.assertEqual(rows[0]["suggested_action"], mr.ACTION_CONFIRM_EXACT)
        self.assertIn("upc=096619330192", rows[0]["amazon_count_weight_variant_evidence"])

    def test_exact_without_upc_asks_for_upc_verification(self):
        with patch("product_analysis.get_costco_price", return_value=_costco("exact")):
            rows = mr.review_rows([_candidate()])
        self.assertEqual(rows[0]["suggested_action"], mr.ACTION_VERIFY_UPC)

    def test_invoice_confirmed_confirms(self):
        with patch("product_analysis.get_costco_price", return_value=_costco("invoice_confirmed")):
            rows = mr.review_rows([_candidate()])
        self.assertEqual(rows[0]["suggested_action"], mr.ACTION_CONFIRM_EXACT)

    def test_high_confidence_with_count_hint(self):
        with patch(
            "product_analysis.get_costco_price",
            return_value=_costco("high_confidence", match_reason="pack/count differs"),
        ):
            rows = mr.review_rows([_candidate()])
        self.assertEqual(rows[0]["suggested_action"], mr.ACTION_VERIFY_COUNT_PACK)

    def test_high_confidence_default_verify_upc(self):
        with patch(
            "product_analysis.get_costco_price",
            return_value=_costco("high_confidence", match_reason="title similarity"),
        ):
            rows = mr.review_rows([_candidate()])
        self.assertEqual(rows[0]["suggested_action"], mr.ACTION_VERIFY_UPC)

    def test_candidate_default_verify_variant(self):
        with patch("product_analysis.get_costco_price", return_value=_costco("candidate")), patch(
            "opportunity_analytics.verification_tasks", return_value=[]
        ):
            rows = mr.review_rows([_candidate()])
        self.assertEqual(rows[0]["suggested_action"], mr.ACTION_VERIFY_VARIANT)

    def test_mismatch_rejects(self):
        with patch("product_analysis.get_costco_price", return_value=_costco("mismatch")):
            rows = mr.review_rows([_candidate()])
        self.assertEqual(rows[0]["suggested_action"], mr.ACTION_REJECT)

    def test_conflicts_and_evidence_carried(self):
        costco = _costco(
            "exact",
            evidence={
                "matched_brand": True,
                "matched_upc": True,
                "known_conflicts": ["net weight differs"],
            },
        )
        with patch("product_analysis.get_costco_price", return_value=costco):
            rows = mr.review_rows([_candidate(upc="096619330192")])
        self.assertIn("matched_brand", rows[0]["match_evidence"])
        self.assertIn("net weight differs", rows[0]["conflict_reasons"])


class CsvAndCoverageTests(unittest.TestCase):
    def test_write_review_csv(self):
        path = os.path.join(_TMP, "review.csv")
        rows = [
            {
                "asin": "B00GYZWNY6",
                "amazon_title": "Kirkland Signature Paper Towels 12 Pack",
                "match_quality": "exact",
                "suggested_action": mr.ACTION_CONFIRM_EXACT,
                "verification_task": "",
                "conflict_reasons": "",
            }
        ]
        count = mr.write_review_csv(rows, path)
        self.assertEqual(count, 1)
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, mr.CSV_COLUMNS)
            self.assertEqual(len(list(reader)), 1)

    def test_coverage_metrics_actions_and_ledger_hits(self):
        ledger = {"B00GYZWNY6": "Kirkland Signature Paper Towels"}
        rows = [
            {"asin": "B00GYZWNY6", "amazon_upc": "096619330192", "amazon_gtin_ean": None,
             "conflict_reasons": "net weight differs", "verification_task": "verify",
             "suggested_action": mr.ACTION_CONFIRM_EXACT},
            {"asin": "B0OTHER0001", "amazon_upc": None, "amazon_gtin_ean": None,
             "conflict_reasons": "", "verification_task": "verify",
             "suggested_action": mr.ACTION_VERIFY_UPC},
        ]
        with patch("costco_api_client._load_ledger", return_value=ledger):
            metrics = mr.coverage_metrics([], rows)
        self.assertEqual(metrics["total_candidates"], 2)
        self.assertEqual(metrics["ledger_hits"], 1)
        self.assertEqual(metrics["ledger_confirmable"], 1)
        self.assertEqual(metrics["verification_queue_size"], 2)
        self.assertEqual(metrics["top_conflict_type"], "net weight differs")
        self.assertEqual(metrics["missing_identifier_counts"], {"ean": 1, "upc_and_ean": 1})


class ValidateImportTests(unittest.TestCase):
    def setUp(self):
        self.ledger = {"B00GYZWNY6": "Kirkland Signature Paper Towels"}

    def _write_import(self, name, rows):
        path = os.path.join(_TMP, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _validate(self, path):
        with patch("costco_api_client._load_ledger", return_value=self.ledger):
            return mr.validate_import(path)

    def test_classification_full_matrix(self):
        path = self._write_import(
            "proposed.csv",
            [
                {"asin": "B00GYZWNY6", "item_name": "Different Item", "upc_or_ean": "123456789012"},
                {"asin": "B0GOOD0001", "item_name": "Kirkland Item", "upc_or_ean": "098765432109"},
                {"asin": "SHORT", "item_name": "Kirkland Item"},
                {"asin": "B0GOOD0002", "item_name": ""},
                {"asin": "B0GOOD0003", "item_name": "Kirkland Item"},
            ],
        )
        report = self._validate(path)
        self.assertEqual(report["rows"], 5)
        self.assertEqual(report["counts"]["ledger_confirmable"], 1)
        self.assertEqual(report["counts"]["research"], 1)
        self.assertEqual(report["counts"]["rejected"], 2)
        self.assertEqual(report["counts"]["held_for_review"], 1)
        by_status = {r["asin"]: r["status"] for r in report["results"]}
        self.assertEqual(by_status["B00GYZWNY6"], "held_for_review")
        self.assertEqual(by_status["B0GOOD0001"], "ledger_confirmable")
        self.assertEqual(by_status["SHORT"], "rejected")
        self.assertEqual(by_status["B0GOOD0002"], "rejected")
        self.assertEqual(by_status["B0GOOD0003"], "research")
        self.assertIn("exclusively", report["note"].lower())

    def test_validate_never_writes_ledger(self):
        before = _sha256(LEDGER_PATH) if os.path.exists(LEDGER_PATH) else None
        path = self._write_import(
            "proposed2.csv", [{"asin": "B0GOOD0001", "item_name": "Kirkland Item", "upc_or_ean": "1"}]
        )
        self._validate(path)
        if before is None:
            self.assertFalse(os.path.exists(LEDGER_PATH))
        else:
            self.assertEqual(_sha256(LEDGER_PATH), before)

    def test_validate_writes_only_validate_output(self):
        path = self._write_import(
            "proposed3.csv", [{"asin": "B0GOOD0001", "item_name": "Kirkland Item", "upc_or_ean": "1"}]
        )
        out = os.path.join(_TMP, "validation.json")
        rc = mr.main(["--validate-import", path, "--validate-output", out])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(out))
        report = json.load(open(out, encoding="utf-8"))
        self.assertEqual(report["counts"]["ledger_confirmable"], 1)
        self.assertFalse(os.path.exists(LEDGER_PATH))


class AuditAndMainTests(unittest.TestCase):
    def test_audit_appends_jsonl(self):
        path = os.path.join(_TMP, "audit.jsonl")
        mr.append_audit(path, {"mode": "review", "rows": 3})
        mr.append_audit(path, {"mode": "review", "rows": 5})
        lines = open(path, encoding="utf-8").read().strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[1])["rows"], 5)

    def test_main_review_mode_with_output(self):
        out = os.path.join(_TMP, "main-review.csv")
        with patch(
            "amazon_search.load_cached_candidates",
            return_value=[_candidate(upc="096619330192")],
        ), patch("product_analysis.get_costco_price", return_value=_costco("exact")), patch(
            "costco_api_client._load_ledger", return_value={}
        ):
            rc = mr.main(["--input", os.path.join(_TMP, "fake-cache.json"), "--output", out])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(out))

    def test_main_audit_written_when_requested(self):
        out = os.path.join(_TMP, "main-review2.csv")
        audit = os.path.join(_TMP, "main-audit.jsonl")
        with patch(
            "amazon_search.load_cached_candidates",
            return_value=[_candidate(upc="096619330192")],
        ), patch("product_analysis.get_costco_price", return_value=_costco("exact")), patch(
            "costco_api_client._load_ledger", return_value={}
        ):
            rc = mr.main(
                ["--input", os.path.join(_TMP, "fake-cache.json"), "--output", out, "--audit", audit]
            )
        self.assertEqual(rc, 0)
        self.assertEqual(len(open(audit, encoding="utf-8").read().strip().splitlines()), 1)

    def test_main_no_candidates_returns_1(self):
        with patch("amazon_search.load_cached_candidates", return_value=[]):
            rc = mr.main(["--input", os.path.join(_TMP, "empty-cache.json"), "--output", os.path.join(_TMP, "x.csv")])
        self.assertEqual(rc, 1)


class RealDataByteIdentityTests(unittest.TestCase):
    def test_real_cache_untouched(self):
        if _CACHE_SHA is None:
            self.skipTest("real cache missing")
        self.assertEqual(_sha256(_REAL_CACHE), _CACHE_SHA)

    def test_real_backup_untouched(self):
        if _BACKUP_SHA is None:
            self.skipTest("real backup missing")
        self.assertEqual(_sha256(_REAL_BACKUPS[0]), _BACKUP_SHA)

    def test_real_snapshot_store_untouched(self):
        if _SNAPSHOTS_SHA is None:
            self.skipTest("real snapshot store missing")
        self.assertEqual(_sha256(_REAL_SNAPSHOTS), _SNAPSHOTS_SHA)

    def test_real_costco_csv_untouched(self):
        if _COSTCO_CSV_SHA is None:
            self.skipTest("real costco csv missing")
        self.assertEqual(_sha256(_REAL_COSTCO_CSV), _COSTCO_CSV_SHA)


if __name__ == "__main__":
    unittest.main()