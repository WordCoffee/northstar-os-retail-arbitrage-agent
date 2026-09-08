"""Unit tests for the offline lookup-evidence backfill helper.

Never makes network calls: operates only on temp CSV files and temp
normalized evidence JSON. Covers:
  (1) acceptance gate (lookup_candidate + score >= 0.50 only)
  (2) duplicate-query resolution (highest score wins, conflicts counted)
  (3) no in-place overwrite of the input CSV
  (4) weak / no-result / page-not-found records reported, never fabricated
  (5) CLI dry-run writes nothing
"""

import csv
import json
import os
import tempfile
import unittest

import bright_data_costco_backfill as backfill


def _evidence_record(query, item_id=None, score=0.8, status="lookup_candidate",
                     run_id="lookup_20260908T000000Z"):
    best = None
    if item_id:
        best = {"item_id": item_id, "title": f"Kirkland {item_id}", "score": score}
    return {
        "run_id": run_id,
        "operation": "costco_search_lookup",
        "query": query,
        "provider": "BRIGHTDATA_WEB_UNLOCKER",
        "identity_match_status": status,
        "best_candidate": best,
        "candidate_count": 1,
    }


def _write_evidence(tmpdir, records):
    norm = os.path.join(tmpdir, "normalized")
    os.makedirs(norm, exist_ok=True)
    for i, rec in enumerate(records):
        with open(os.path.join(norm, f"lookup_key{i}_{rec['run_id']}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(rec, fh)
    return tmpdir


def _write_csv(tmpdir, rows, header=None):
    header = header or [
        "Priority tier", "ASIN", "Exact Amazon title", "Amazon brand",
        "Costco candidate title", "Costco candidate item number",
        "Costco candidate pack / size / count", "Match source",
        "Match confidence", "Notes / mismatch detail",
    ]
    path = os.path.join(tmpdir, "master.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return path


class ResolveMapTests(unittest.TestCase):
    def test_only_lookup_candidate_over_threshold_accepted(self):
        recs = [
            _evidence_record("Strong A", item_id="111", score=0.90),
            _evidence_record("Weak B", item_id="222", score=0.40, status="lookup_weak_match"),
            _evidence_record("NoRes C", item_id=None, status="lookup_no_results"),
            _evidence_record("PageNF D", item_id=None, status="lookup_page_not_found"),
            _evidence_record("Barely E", item_id="333", score=0.50),
            _evidence_record("Under F", item_id="444", score=0.49),
        ]
        resolved = backfill.build_resolved_map(recs)
        self.assertEqual(set(resolved.keys()), {"Strong A", "Barely E"})
        self.assertEqual(resolved["Strong A"]["item_id"], "111")
        self.assertEqual(resolved["Barely E"]["item_id"], "333")

    def test_duplicate_query_keeps_highest_score_and_counts_conflict(self):
        recs = [
            _evidence_record("Same", item_id="100", score=0.70),
            _evidence_record("Same", item_id="100", score=0.90),
            _evidence_record("Same", item_id="999", score=0.60),
        ]
        resolved = backfill.build_resolved_map(recs)
        self.assertEqual(resolved["Same"]["item_id"], "100")
        self.assertEqual(resolved["Same"]["score"], 0.90)
        # only the evidence record that disagreed with the winner counts
        self.assertEqual(resolved["Same"]["conflicts"], 1)


class BackfillCsvTests(unittest.TestCase):
    def _setup(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        lookup = _write_evidence(
            self.tmp.name, [
                _evidence_record("KIRKLAND B12 300 ct", item_id="111", score=0.91),
                _evidence_record("KIRKLAND Vitamin E 500", item_id="222", score=0.55),
                _evidence_record("KIRKLAND Weak Match Omega 3", item_id="333",
                                 score=0.35, status="lookup_weak_match"),
                _evidence_record("KIRKLAND Not Found", item_id=None,
                                 status="lookup_no_results"),
            ]
        )
        rows = [
            {"Priority tier": "1", "ASIN": "B00U6I4YLM",
             "Exact Amazon title": "KIRKLAND B12 300 ct", "Amazon brand": "Kirkland Signature",
             "Costco candidate title": "", "Costco candidate item number": "",
             "Costco candidate pack / size / count": "",
             "Match source": "", "Match confidence": "", "Notes / mismatch detail": ""},
            {"Priority tier": "2", "ASIN": "B00UP99X1I",
             "Exact Amazon title": "KIRKLAND Vitamin E 500", "Amazon brand": "Kirkland Signature",
             "Costco candidate title": "", "Costco candidate item number": "",
             "Costco candidate pack / size / count": "",
             "Match source": "", "Match confidence": "", "Notes / mismatch detail": ""},
            {"Priority tier": "3", "ASIN": "B00ALREADY",
             "Exact Amazon title": "KIRKLAND B12 300 ct", "Amazon brand": "Kirkland Signature",
             "Costco candidate title": "", "Costco candidate item number": "999",
             "Costco candidate pack / size / count": "",
             "Match source": "manual", "Match confidence": "", "Notes / mismatch detail": ""},
            {"Priority tier": "4", "ASIN": "B00WEAK",
             "Exact Amazon title": "KIRKLAND Weak Match Omega 3", "Amazon brand": "Kirkland Signature",
             "Costco candidate title": "", "Costco candidate item number": "",
             "Costco candidate pack / size / count": "",
             "Match source": "", "Match confidence": "", "Notes / mismatch detail": ""},
            {"Priority tier": "5", "ASIN": "B00NOTFOUND",
             "Exact Amazon title": "KIRKLAND Not Found", "Amazon brand": "Kirkland Signature",
             "Costco candidate title": "", "Costco candidate item number": "",
             "Costco candidate pack / size / count": "",
             "Match source": "", "Match confidence": "", "Notes / mismatch detail": ""},
            {"Priority tier": "6", "ASIN": "B00UNRELATED",
             "Exact Amazon title": "KIRKLAND Unrelated Thing", "Amazon brand": "Kirkland Signature",
             "Costco candidate title": "", "Costco candidate item number": "",
             "Costco candidate pack / size / count": "",
             "Match source": "", "Match confidence": "", "Notes / mismatch detail": ""},
        ]
        csv_path = _write_csv(self.tmp.name, rows)
        return lookup, csv_path

    def test_fills_strong_matches_and_reports_weak(self):
        lookup, csv_path = self._setup()
        out = os.path.join(self.tmp.name, "master_backfilled.csv")
        report = backfill.backfill_csv(csv_path, out, [lookup])

        self.assertEqual(report["rows_filled"], 2)
        self.assertEqual(report["conflicts"], 1)
        self.assertEqual(report["weak_and_unresolved_titles"], [
            {"amazon_title": "KIRKLAND Weak Match Omega 3",
             "reason": "lookup did not clear acceptance gate"},
            {"amazon_title": "KIRKLAND Not Found",
             "reason": "lookup did not clear acceptance gate"},
        ])

        with open(out, "r", encoding="utf-8-sig", newline="") as fh:
            out_rows = list(csv.DictReader(fh))
        by_asin = {r["ASIN"]: r for r in out_rows}
        self.assertEqual(by_asin["B00U6I4YLM"]["Costco candidate item number"], "111")
        self.assertEqual(by_asin["B00UP99X1I"]["Costco candidate item number"], "222")
        self.assertEqual(by_asin["B00UP99X1I"]["Match source"], "BRIGHTDATA_WEB_UNLOCKER")
        self.assertIn("jaccard 0.55", by_asin["B00UP99X1I"]["Match confidence"])
        # already-annotated row with a different id must NOT be overwritten
        self.assertEqual(by_asin["B00ALREADY"]["Costco candidate item number"], "999")
        # weak and not-found rows are reported but never fabricated
        self.assertEqual(by_asin["B00WEAK"]["Costco candidate item number"], "")
        self.assertEqual(by_asin["B00NOTFOUND"]["Costco candidate item number"], "")
        # unrelated row untouched
        self.assertEqual(by_asin["B00UNRELATED"]["Costco candidate item number"], "")

    def test_refuses_in_place_overwrite(self):
        lookup, csv_path = self._setup()
        with self.assertRaises(ValueError):
            backfill.backfill_csv(csv_path, csv_path, [lookup])

    def test_empty_evidence_fills_nothing(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        csv_path = _write_csv(tmp.name, [{"ASIN": "B00X",
                                          "Exact Amazon title": "Some Kirkland",
                                          "Costco candidate item number": ""}])
        out = os.path.join(tmp.name, "out.csv")
        report = backfill.backfill_csv(
            csv_path, out, [os.path.join(tmp.name, "no-evidence-run")]
        )
        self.assertEqual(report["rows_filled"], 0)
        self.assertEqual(report["evidence_records"], 0)
        # fail-closed: with zero evidence nothing is produced (the CLI guards
        # this case with rc=1 before ever calling backfill_csv).
        self.assertFalse(os.path.exists(out))


class CliTests(unittest.TestCase):
    def _run(self, argv):
        return backfill._cli(argv)

    def test_cli_dry_run_writes_nothing(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        lookup = _write_evidence(
            tmp.name,
            [_evidence_record("KIRKLAND B12 300 ct", item_id="111", score=0.91)],
        )
        csv_path = _write_csv(tmp.name, [
            {"ASIN": "B00U6I4YLM", "Exact Amazon title": "KIRKLAND B12 300 ct",
             "Costco candidate item number": ""}
        ])
        out = os.path.join(tmp.name, "never.json")
        rc = self._run([
            "--csv", csv_path, "--lookup-dir", lookup, "--out", out, "--dry-run",
        ])
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(out))

    def test_cli_no_evidence_returns_nonzero(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        csv_path = _write_csv(tmp.name, [{"ASIN": "B00X",
                                          "Exact Amazon title": "X",
                                          "Costco candidate item number": ""}])
        rc = self._run(["--csv", csv_path, "--lookup-root",
                        os.path.join(tmp.name, "no-such-root")])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()