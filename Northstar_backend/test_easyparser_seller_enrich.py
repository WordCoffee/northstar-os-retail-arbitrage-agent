"""Offline tests for easyparser_seller_enrich.py (zero network, zero creds).

All provider calls are mocked at the offer_enrichment.get_seller_offer_contract
boundary; live_gate.live_enabled is patched so tests never depend on CWD/.env
state (see known_issue credential_exposure_in_test_failure_diff — no real
credential value may ever appear in test output).
"""

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import easyparser_seller_enrich as ese


def _manifest(path: Path, asins):
    items = [{"asin": a, "title": "Kirkland T%d" % i,
              "quantity_match": {"status": "PASS"}} for i, a in enumerate(asins)]
    path.write_text(json.dumps({"items": items}), encoding="utf-8")


def _payload(asin, status="available", used=1, remaining=50):
    return {
        "asin": asin,
        "offer_data_status": status,
        "offer_data_source": "easyparser",
        "offer_data_fetched_at": "2026-09-13T00:00:00+00:00",
        "total_sellers": 10,
        "fba_sellers": 4,
        "fbm_sellers": 6,
        "buy_box": {"seller_name": "S", "price": 9.99},
        "offers": [],
        "offers_returned": 10,
        "credits_used": used,
        "credits_remaining": remaining,
    }


def _args(manifest, **kw):
    base = {"live": True, "manifest": str(manifest), "max_requests": 10,
            "max_credits": 20, "resume_from": None, "only_asins": None,
            "asin_file": None}
    base.update(kw)
    return argparse.Namespace(**base)


class SellerEnrichTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.manifest = self.tmp / "manifest.json"
        _manifest(self.manifest, ["B00BH3HPZW", "B0017SURSY", "B002AAAAAAAA"[:10]])
        # Redirect run base into temp dir.
        self._base = ese.RUNS_BASE_DIR
        ese.RUNS_BASE_DIR = self.tmp / "runs"
        self._live = patch.object(ese.live_gate, "live_enabled", return_value=True)
        self._live.start()
        self.addCleanup(self._live.stop)

    def tearDown(self):
        ese.RUNS_BASE_DIR = self._base

    def test_dry_run_accepts_pass_manifest_zero_network(self):
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=AssertionError("network in dry-run")):
            rc = ese.run_dry_run(argparse.Namespace(manifest=str(self.manifest)))
        self.assertEqual(rc, 0)

    def test_run_refuses_without_caps(self):
        rc = ese.run_batch(_args(self.manifest, max_requests=None))
        self.assertEqual(rc, 2)
        rc = ese.run_batch(_args(self.manifest, max_credits=None))
        self.assertEqual(rc, 2)

    def test_run_writes_summary_and_ledger_stream(self):
        asins = ["B00BH3HPZW", "B0017SURSY"]
        _manifest(self.manifest, asins)
        calls = []

        def fake(asin):
            calls.append(asin)
            return _payload(asin)

        with patch.object(ese.offer_enrichment, "get_seller_offer_contract", side_effect=fake):
            rc = ese.run_batch(_args(self.manifest))
        self.assertEqual(rc, 0)
        run_dirs = [d for d in ese.RUNS_BASE_DIR.iterdir() if d.is_dir()]
        self.assertEqual(len(run_dirs), 1)
        run_dir = run_dirs[0]
        self.assertTrue((run_dir / "summary.json").exists())
        self.assertTrue((run_dir / "run.log").exists())
        ledger_lines = (run_dir / "ledger.jsonl").read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(ledger_lines), 2)
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["requests_used"], 2)
        self.assertEqual(summary["stop_reason"], None)
        self.assertEqual(summary["outcome_counts"]["available"], 2)
        self.assertEqual(calls, asins)

    def test_max_requests_cap_stops_batch(self):
        _manifest(self.manifest, ["B00BH3HPZW", "B0017SURSY", "B003CCCCCC"])
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=lambda a: _payload(a)) as m:
            rc = ese.run_batch(_args(self.manifest, max_requests=2, max_credits=100))
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_count, 2)
        run_dir = [d for d in ese.RUNS_BASE_DIR.iterdir() if d.is_dir()][0]
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["stop_reason"], "max_requests")

    def test_provider_balance_zero_stops_before_next_call(self):
        _manifest(self.manifest, ["B00BH3HPZW", "B0017SURSY", "B003CCCCCC"])
        seq = [_payload("B00BH3HPZW", remaining=0), _payload("B0017SURSY"), _payload("B003CCCCCC")]
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=seq) as m:
            rc = ese.run_batch(_args(self.manifest, max_requests=10, max_credits=100))
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_count, 1)
        run_dir = [d for d in ese.RUNS_BASE_DIR.iterdir() if d.is_dir()][0]
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["stop_reason"], "provider_balance_exhausted")

    def test_resume_skips_finished_asins(self):
        _manifest(self.manifest, ["B00BH3HPZW", "B0017SURSY"])
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=lambda a: _payload(a)):
            ese.run_batch(_args(self.manifest))
        run_id = [d for d in ese.RUNS_BASE_DIR.iterdir() if d.is_dir()][0].name
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=AssertionError("re-spend on resume")) as m:
            rc = ese.run_batch(_args(self.manifest, resume_from=run_id))
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_count, 0)

    def test_summary_written_on_provider_exception(self):
        _manifest(self.manifest, ["B00BH3HPZW", "B0017SURSY"])
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=RuntimeError("boom")):
            rc = ese.run_batch(_args(self.manifest))
        self.assertEqual(rc, 0)
        run_dir = [d for d in ese.RUNS_BASE_DIR.iterdir() if d.is_dir()][0]
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertTrue(str(summary["stop_reason"]).startswith("error:"))
        # The failed ASIN wrote no normalized file; resume must retry it.
        self.assertFalse((run_dir / "normalized" / "B00BH3HPZW.json").exists())

    def test_rejects_non_pass_scope(self):
        self.manifest.write_text(json.dumps({"items": [
            {"asin": "B00BH3HPZW", "quantity_match": {"status": "REVIEW"}}]}),
            encoding="utf-8")
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=AssertionError("network on reject")):
            rc = ese.run_batch(_args(self.manifest))
        self.assertEqual(rc, 4)

    def test_only_asins_filter_targets_subset_in_manifest_order(self):
        _manifest(self.manifest, ["B00BH3HPZW", "B0017SURSY", "B003CCCCCC"])
        calls = []
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=lambda a: calls.append(a) or _payload(a)):
            rc = ese.run_batch(_args(self.manifest, only_asins="B003CCCCCC,B00BH3HPZW"))
        self.assertEqual(rc, 0)
        self.assertEqual(calls, ["B00BH3HPZW", "B003CCCCCC"])

    def test_asin_file_filter_and_empty_match_refuses(self):
        _manifest(self.manifest, ["B00BH3HPZW", "B0017SURSY"])
        afile = self.tmp / "targets.txt"
        afile.write_text("B0017SURSY\nNOTANASIN\n", encoding="utf-8")
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=lambda a: _payload(a)) as m:
            rc = ese.run_batch(_args(self.manifest, asin_file=str(afile)))
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_count, 1)
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=AssertionError("network on empty filter")):
            rc = ese.run_batch(_args(self.manifest, only_asins="B999999999"))
        self.assertEqual(rc, 2)

    def test_cumulative_counter_accounted_by_balance_delta(self):
        # Live run c414 proved credits_used is cumulative (2,3,4...) while the
        # balance falls 1/call. Budget must total true spend (3.0), not the
        # sum of the counter (9.0), and must not trip caps early.
        _manifest(self.manifest, ["B00BH3HPZW", "B0017SURSY", "B003CCCCCC"])
        seq = [_payload("B00BH3HPZW", used=12, remaining=88),
               _payload("B0017SURSY", used=13, remaining=87),
               _payload("B003CCCCCC", used=14, remaining=86)]
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=seq) as m:
            rc = ese.run_batch(_args(self.manifest, max_requests=10, max_credits=100))
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_count, 3)
        run_dir = [d for d in ese.RUNS_BASE_DIR.iterdir() if d.is_dir()][0]
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["stop_reason"], None)
        self.assertAlmostEqual(summary["credits_used"], 3.0, places=1)

    def test_resume_recomputes_prefixed_bad_ledger(self):
        # A ledger written by the pre-fix bug (credits_this_call 12,13,14)
        # must replay to truthful spend (1.0 + 1 + 1) via balance deltas so
        # the resume continues instead of tripping max_credits instantly.
        _manifest(self.manifest, ["B00BH3HPZW", "B0017SURSY", "B003CCCCCC",
                                  "B004DDDDDD"])
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=lambda a: _payload(a)):
            ese.run_batch(_args(self.manifest, max_requests=10, max_credits=1000))
        run_id = [d for d in ese.RUNS_BASE_DIR.iterdir() if d.is_dir()][0].name
        run_dir = ese.RUNS_BASE_DIR / run_id
        rows = [json.loads(line) for line in
                (run_dir / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
        bad = []
        for i, row in enumerate(rows):
            row["credits_this_call"] = float(12 + i)
            row["credit_basis"] = "reported"
            row["credits_remaining"] = 50 - i
            bad.append(row)
        (run_dir / "ledger.jsonl").write_text(
            "\n".join(json.dumps(r) for r in bad) + "\n", encoding="utf-8")
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          side_effect=lambda a: _payload(a, remaining=46)) as m:
            rc = ese.run_batch(_args(self.manifest, max_requests=10,
                                     max_credits=1000, resume_from=run_id))
        self.assertEqual(rc, 0)
        # 4 rows replay (first estimated 1.0 + deltas), 0 new calls needed
        # only if files exist for all 4 — they do, so zero new provider calls.
        self.assertEqual(m.call_count, 0)
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(summary["credits_used"], 4.0, places=1)

    def test_tee_survives_unencodable_console(self):
        # Live run c414 resume died on a flag-emoji seller name via the
        # cp1252 console. The UTF-8 stream must keep full fidelity while the
        # limited stream degrades gracefully — and the batch must not die.
        import io as _io
        limited = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252",
                                    errors="strict")
        full = _io.StringIO()
        tee = ese._Tee(limited, full)
        tee.write("buybox=EzShop \U0001f1fa\U0001f1f8 ok\n")
        tee.flush()
        self.assertIn("\U0001f1fa\U0001f1f8", full.getvalue())
        limited.seek(0)
        self.assertIn("buybox=EzShop", limited.read())

    def test_batch_survives_emoji_seller_name(self):
        _manifest(self.manifest, ["B00BH3HPZW"])
        payload = _payload("B00BH3HPZW")
        payload["buy_box"] = {"seller_name": "EzShop \U0001f1fa\U0001f1f8"}
        with patch.object(ese.offer_enrichment, "get_seller_offer_contract",
                          return_value=payload):
            rc = ese.run_batch(_args(self.manifest))
        self.assertEqual(rc, 0)
        run_dir = [d for d in ese.RUNS_BASE_DIR.iterdir() if d.is_dir()][0]
        saved = json.loads((run_dir / "normalized" / "B00BH3HPZW.json")
                           .read_text(encoding="utf-8"))
        self.assertIn("\U0001f1fa", saved["buy_box"]["seller_name"])


if __name__ == "__main__":
    unittest.main()
