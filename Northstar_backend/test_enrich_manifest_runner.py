"""Offline tests for enrich_manifest_run.py.

Every test is mocked and zero-network:
- sitecustomize.py blocks real ``requests`` during pytest runs;
- each run test additionally patches
  ``enrich_manifest_run.easyparser_client.get_easyparser_offers``;
- the explicit containment test patches ``requests.api.get`` to raise, then
  runs status + dry-run end-to-end proving zero transport calls;
- ``amazon_search.load_cached_candidates`` is spied to prove the runner
  NEVER falls back to scanner-cache ordering.

Run dirs are redirected into a temp directory via patching
``_runs_base_dir``, so real data/ is never touched.
"""

import json
import os
import tempfile
import unittest
from io import StringIO
from unittest import mock

import amazon_search
import requests

import enrich_manifest_run as emr

CANONICAL = [
    "B01H40O42I", "B08R2SRN88", "B0CP6LXPLK", "B00BISGJXA", "B00BH3HPZW",
    "B00GYZWNY6", "B0045XGE9E", "B002L4M4M0", "B081THWMDK", "B085F1QCB9",
]

CSV_TITLES = {
    "B01H40O42I": "Aller-Flo Fluticasone (Pack of 5)",
    "B08R2SRN88": "Aller-Flo Fluticasone (5 Bottles/600 sprays)",
    "B0CP6LXPLK": "Minoxidil Extra Strength (6-mo)",
    "B00BISGJXA": "Stool Softener 100mg (400ct)",
    "B00BH3HPZW": "Fiber Capsules (360ct)",
    "B00GYZWNY6": "Glucosamine 1500/Chondroitin 1200 (220ct)",
    "B0045XGE9E": "Sleep Aid Doxylamine (2pk/192ct)",
    "B002L4M4M0": "Sleep Aid Doxylamine (96ct)",
    "B081THWMDK": "Stretch Tite Food Wrap (2pk)",
    "B085F1QCB9": "Compactor Trash Bag",
}
CSV_PRICES = {
    "B01H40O42I": 26.74, "B08R2SRN88": 26.80, "B0CP6LXPLK": 33.12,
    "B00BISGJXA": 12.75, "B00BH3HPZW": 17.84, "B00GYZWNY6": 29.25,
    "B0045XGE9E": 13.84, "B002L4M4M0": 7.93, "B081THWMDK": 28.79,
    "B085F1QCB9": 28.07,
}


def valid_manifest_obj():
    asins = []
    for i, a in enumerate(CANONICAL, 1):
        asins.append({
            "position": i,
            "asin": a,
            "product_title_csv": CSV_TITLES[a],
            "price_csv": CSV_PRICES[a],
            "reviews_csv": 500 + i,
            "prime_fba_flag_csv": "Yes",
            "bsr_text_csv": "Not listed on page",
        })
    return {
        "kind": "live-10asin-manifest",
        "canonical_asin_order": list(CANONICAL),
        "asins": asins,
    }


def fake_result(asin, title="Widget Offer Set", n_offers=1, offer_count=None,
                credits_used=5, credits_remaining=995, gap=None):
    """Mirror easyparser_client.get_easyparser_offers shapes (success + default failure)."""
    if gap is not None:
        return {
            "source": "easyparser", "asin": asin, "provider_asin": None,
            "request_id": None, "title": None, "offer_count": None,
            "offers_returned_count": 0, "buy_box_price": None,
            "buy_box_price_raw": None, "buy_box_seller": None,
            "buy_box_seller_id": None, "buy_box_is_fba": None,
            "buy_box_is_fbm": None, "buy_box_is_prime": None,
            "buy_box_condition": None, "observed_fba_offer_count": 0,
            "observed_fbm_offer_count": 0, "observed_amazon_offer_count": 0,
            "offers": [], "request_zip_code": None, "observed_at": None,
            "credits_used": None, "credits_remaining": None,
            "data_gaps": [gap],
        }
    offers = []
    for i in range(n_offers):
        offers.append({
            "position": i + 1, "buybox_winner": i == 0,
            "price": {"value": 10.0}, "condition": "New",
            "seller": {"id": "A%d" % i, "name": "Amazon.com"},
            "seller_type": {"fba": True, "fbm": False, "sba": False},
            "is_prime": True, "is_fba": True, "is_fbm": False,
            "fulfilled_by_amazon": True, "shipping_text": "",
            "shipping_is_free": True, "ships_from": "Amazon",
            "minimum_order_quantity": 1, "maximum_order_quantity": None,
        })
    return {
        "source": "easyparser", "asin": asin, "provider_asin": asin,
        "request_id": "req-%s" % asin, "title": title,
        "offer_count": n_offers if offer_count is None else offer_count,
        "offers_returned_count": len(offers),
        "buy_box_price": 10.0, "buy_box_price_raw": {"value": 10.0},
        "buy_box_seller": "Amazon.com", "buy_box_seller_id": "A0",
        "buy_box_is_fba": True, "buy_box_is_fbm": False,
        "buy_box_is_prime": True, "buy_box_condition": "New",
        "observed_fba_offer_count": len(offers),
        "observed_fbm_offer_count": 0,
        "observed_amazon_offer_count": len(offers),
        "offers": offers, "request_zip_code": "75201",
        "observed_at": "2026-08-22T00:00:00Z",
        "credits_used": credits_used, "credits_remaining": credits_remaining,
        "data_gaps": [],
    }


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = tmp.name
        self.runs_root = os.path.join(self.base, "runs")
        p = mock.patch.object(emr, "_runs_base_dir", lambda: self.runs_root)
        p.start()
        self.addCleanup(p.stop)

    # -- helpers ---------------------------------------------------------- #
    def write_manifest(self, obj=None, name="manifest.json", raw=None):
        path = os.path.join(self.base, name)
        with open(path, "w", encoding="utf-8") as f:
            if raw is not None:
                f.write(raw)
            else:
                json.dump(obj if obj is not None else valid_manifest_obj(), f)
        return path

    def install_client(self, fn):
        calls = []

        def wrapper(asin):
            calls.append(asin)
            return fn(asin)

        p = mock.patch.object(emr.easyparser_client, "get_easyparser_offers", wrapper)
        p.start()
        self.addCleanup(p.stop)
        return calls

    def ok_client(self, **kw):
        return lambda asin: fake_result(asin, **kw)

    def single_run_dir(self):
        entries = [e for e in os.listdir(self.runs_root) if e != "run-index.jsonl"]
        self.assertEqual(len(entries), 1, entries)
        return os.path.join(self.runs_root, entries[0])

    def read_ledger(self, run_dir):
        with open(os.path.join(run_dir, "request-ledger.json"), "r", encoding="utf-8") as f:
            return json.load(f)["entries"]

    def index_lines(self):
        p = os.path.join(self.runs_root, "run-index.jsonl")
        if not os.path.exists(p):
            return []
        with open(p, "r", encoding="utf-8") as f:
            return [json.loads(x) for x in f.read().splitlines() if x.strip()]

    def snapshot_tree(self, root):
        out = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                out.append(os.path.relpath(os.path.join(dirpath, fn), root))
        return sorted(out)


class ManifestValidationTests(Base):
    def test_01_valid_manifest_accepted(self):
        path = self.write_manifest()
        m, err = emr.load_and_validate_manifest(path)
        self.assertIsNone(err)
        self.assertEqual(m["canonical_asin_order"], CANONICAL)

    def test_02_more_than_ten_rejected(self):
        obj = valid_manifest_obj()
        extra = "B0ZZZZZZZZZ"
        obj["canonical_asin_order"] = CANONICAL + [extra]
        obj["asins"].append({
            "position": 11, "asin": extra, "product_title_csv": "x",
            "price_csv": 1.0, "reviews_csv": 1, "prime_fba_flag_csv": "Yes",
            "bsr_text_csv": "Not listed on page",
        })
        m, err = emr.load_and_validate_manifest(self.write_manifest(obj))
        self.assertIsNone(m)
        self.assertIn("10-ASIN hard limit", err)

    def test_03_duplicate_rejected(self):
        obj = valid_manifest_obj()
        obj["canonical_asin_order"][5] = CANONICAL[0]
        m, err = emr.load_and_validate_manifest(self.write_manifest(obj))
        self.assertIsNone(m)
        self.assertIn("duplicate", err)

    def test_04_outside_approved_set_rejected(self):
        obj = valid_manifest_obj()
        rogue = "B0" + "Y" * 8
        obj["canonical_asin_order"][3] = rogue
        obj["asins"][3]["asin"] = rogue
        m, err = emr.load_and_validate_manifest(self.write_manifest(obj))
        self.assertIsNone(m)
        self.assertIn("outside the approved", err)

    def test_05_malformed_json_rejected(self):
        m, err = emr.load_and_validate_manifest(
            self.write_manifest(raw="{ this is not json "))
        self.assertIsNone(m)
        self.assertTrue(err.startswith("malformed JSON"))

    def test_06_missing_file_rejected(self):
        m, err = emr.load_and_validate_manifest(
            os.path.join(self.base, "nope.json"))
        self.assertIsNone(m)
        self.assertIn("not found", err)

    def test_07_wrong_kind_rejected(self):
        obj = valid_manifest_obj()
        obj["kind"] = "something-else"
        m, err = emr.load_and_validate_manifest(self.write_manifest(obj))
        self.assertIsNone(m)
        self.assertIn("kind mismatch", err)

    def test_08_missing_required_field_rejected(self):
        obj = valid_manifest_obj()
        del obj["asins"][2]["bsr_text_csv"]
        m, err = emr.load_and_validate_manifest(self.write_manifest(obj))
        self.assertIsNone(m)
        self.assertIn("missing required field", err)


class SelectionAndCapsTests(Base):
    def test_09_order_exact_and_no_cache_fallback(self):
        patcher = mock.patch.object(amazon_search, "load_cached_candidates")
        spy = patcher.start()
        self.addCleanup(patcher.stop)
        path = self.write_manifest()
        calls = self.install_client(self.ok_client())
        rc = emr.main(["run", "--live", "--manifest", path,
                       "--max-requests", "10", "--max-credits", "100"])
        self.assertEqual(rc, 0)
        self.assertEqual(calls, CANONICAL)          # exact manifest order
        spy.assert_not_called()                     # never touches cache loader
        run_dir = self.single_run_dir()
        ledger = self.read_ledger(run_dir)
        self.assertEqual([e["asin"] for e in ledger], CANONICAL)

    def test_10_max_requests_cap_enforced_before_call(self):
        path = self.write_manifest()
        calls = self.install_client(self.ok_client())
        rc = emr.main(["run", "--live", "--manifest", path,
                       "--max-requests", "3", "--max-credits", "100"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls, CANONICAL[:3])
        run_dir = self.single_run_dir()
        ledger = self.read_ledger(run_dir)
        skipped = [e for e in ledger if e["outcome"] == "skipped_cap"]
        invoked = [e for e in ledger if not e["skipped"]]
        self.assertEqual(len(skipped), 7)
        self.assertEqual(len(invoked), 3)
        with open(os.path.join(run_dir, "run-summary.md"), encoding="utf-8") as f:
            self.assertIn("max_requests", f.read())

    def test_11_max_credits_cap_stops_with_reason(self):
        path = self.write_manifest()
        calls = self.install_client(lambda a: fake_result(a, credits_used=4))
        rc = emr.main(["run", "--live", "--manifest", path,
                       "--max-requests", "10", "--max-credits", "6"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 2)             # 4 + 4 = 8 >= 6 stops call 3
        run_dir = self.single_run_dir()
        ledger = self.read_ledger(run_dir)
        skipped = [e for e in ledger if e["outcome"] == "skipped_cap"]
        self.assertEqual(len(skipped), 8)
        with open(os.path.join(run_dir, "run-summary.md"), encoding="utf-8") as f:
            self.assertIn("max_credits", f.read())

    def test_12_zero_retry_on_failure_shape(self):
        path = self.write_manifest()

        def flaky(asin):
            if asin == "B0CP6LXPLK":
                return fake_result(asin, gap="Easyparser request timed out.")
            return fake_result(asin)

        calls = self.install_client(flaky)
        rc = emr.main(["run", "--live", "--manifest", path,
                       "--max-requests", "10", "--max-credits", "100"])
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(calls), sorted(CANONICAL))   # exactly once per ASIN
        self.assertEqual(len(calls), len(set(calls)))         # no second call ever
        ledger = self.read_ledger(self.single_run_dir())
        target = [e for e in ledger if e["asin"] == "B0CP6LXPLK"]
        self.assertEqual(len(target), 1)
        self.assertFalse(target[0]["skipped"])

    def test_13_duplicate_run_id_refused_no_overwrite(self):
        path = self.write_manifest()
        fixed = "manifest-FIXEDTEST-dead"
        with mock.patch.object(emr, "make_run_id", lambda: fixed):
            calls = self.install_client(self.ok_client())
            rc1 = emr.main(["run", "--live", "--manifest", path,
                            "--max-requests", "10", "--max-credits", "100"])
            self.assertEqual(rc1, 0)
            run_dir = os.path.join(self.runs_root, fixed)
            before = self.snapshot_tree(run_dir)
            rc2 = emr.main(["run", "--live", "--manifest", path,
                            "--max-requests", "10", "--max-credits", "100"])
            self.assertEqual(rc2, 3)                 # refusal exit code
            self.assertEqual(self.snapshot_tree(run_dir), before)
            self.assertEqual(len(self.index_lines()), 1)

    def test_14_raw_and_normalized_only_for_invoked(self):
        path = self.write_manifest()
        self.install_client(self.ok_client())
        emr.main(["run", "--live", "--manifest", path,
                  "--max-requests", "2", "--max-credits", "100"])
        run_dir = self.single_run_dir()
        raw = sorted(os.listdir(os.path.join(run_dir, "raw")))
        norm = sorted(os.listdir(os.path.join(run_dir, "normalized")))
        expected = sorted([CANONICAL[0] + ".json", CANONICAL[1] + ".json"])
        self.assertEqual(raw, expected)
        self.assertEqual(norm, expected)


class FailureAndAccountingTests(Base):
    def test_15_provider_error_never_raises_run_completes(self):
        path = self.write_manifest()
        calls = self.install_client(
            lambda a: fake_result(a, gap="Easyparser request timed out."))
        rc = emr.main(["run", "--live", "--manifest", path,
                       "--max-requests", "10", "--max-credits", "200"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 10)
        rows = self._comparison_rows()
        self.assertTrue(all(r["outcome"] == "unavailable" for r in rows))

    def test_16_credits_reported_vs_estimated(self):
        path = self.write_manifest()

        def mixed(asin):
            r = fake_result(asin, credits_used=7)
            if asin == CANONICAL[1]:
                r["credits_used"] = None
            return r

        self.install_client(mixed)
        rc = emr.main(["run", "--live", "--manifest", path,
                       "--max-requests", "2", "--max-credits", "100"])
        self.assertEqual(rc, 0)
        ledger = self.read_ledger(self.single_run_dir())
        self.assertEqual(ledger[0]["credit_basis"], "reported")
        self.assertEqual(ledger[0]["credits_this_call"], 7)
        self.assertEqual(ledger[1]["credit_basis"], "estimated")
        self.assertEqual(ledger[1]["credits_this_call"],
                         emr.ESTIMATED_CREDITS_PER_ASIN)
        idx = self.index_lines()[0]
        self.assertAlmostEqual(idx["credits_used"], 12.0)
        self.assertIn("reported=7", open(
            os.path.join(self.single_run_dir(), "run-summary.md"),
            encoding="utf-8").read())

    def test_16b_ledger_keeps_raw_store_status(self):
        path = self.write_manifest()

        def mixed(asin):
            if asin == CANONICAL[0]:
                return fake_result(asin)                       # available
            return fake_result(asin, gap="Easyparser API returned HTTP 500.")

        self.install_client(mixed)
        emr.main(["run", "--live", "--manifest", path,
                  "--max-requests", "2", "--max-credits", "100"])
        ledger = self.read_ledger(self.single_run_dir())
        self.assertEqual(ledger[0]["outcome"], "available")
        self.assertEqual(ledger[0]["data_status_raw"], "available")
        self.assertEqual(ledger[1]["outcome"], "unavailable")
        self.assertIn(ledger[1]["data_status_raw"],
                      ("failed", "unavailable"))

    # shared helper ------------------------------------------------------- #
    def _comparison_rows(self):
        run_dir = self.single_run_dir()
        import csv as _csv
        with open(os.path.join(run_dir, "live-vs-csv-comparison.csv"),
                  newline="", encoding="utf-8") as f:
            return list(_csv.DictReader(f))


class ComparisonLogicTests(unittest.TestCase):
    def _rows(self, live_map, outcome="available"):
        man = valid_manifest_obj()
        results = {}
        outs = {}
        for a in CANONICAL:
            if a in live_map:
                results[a] = live_map[a]
                outs[a] = outcome
            else:
                outs[a] = "skipped_cap"
        return emr._build_comparison_rows(man, results, outs), man

    def test_17_math_labels_and_fixed_strings(self):
        live_a = fake_result(CANONICAL[0], title=CSV_TITLES[CANONICAL[0]])
        live_a["buy_box_price"] = 21.0                    # csv 26.74 -> -0.2148...
        live_b = fake_result(CANONICAL[1], title="Totally Different Gadget X")
        live_b["buy_box_price"] = 38.0                    # hmm keep simple: use own row below
        rows, _man = self._rows({CANONICAL[0]: live_a})

        # direct math checks on two synthetic cases via the pure pipeline
        man = valid_manifest_obj()
        rec0 = man["asins"][0]
        rec0["price_csv"] = 20.0
        res0 = dict(live_a)
        res0["buy_box_price"] = 21.0
        rows2 = emr._build_comparison_rows(
            {"canonical_asin_order": [CANONICAL[0]], "asins": [rec0]},
            {CANONICAL[0]: res0}, {CANONICAL[0]: "available"})
        self.assertAlmostEqual(rows2[0]["price_delta_abs"], 1.0)
        self.assertAlmostEqual(rows2[0]["price_delta_pct"], 0.05)

        rec1 = dict(rec0)
        rec1["asin"] = CANONICAL[1]
        rec1["price_csv"] = 40.0
        res1 = dict(res0)
        res1["asin"] = CANONICAL[1]
        res1["buy_box_price"] = 38.0
        rows3 = emr._build_comparison_rows(
            {"canonical_asin_order": [CANONICAL[1]], "asins": [rec1]},
            {CANONICAL[1]: res1}, {CANONICAL[1]: "available"})
        self.assertAlmostEqual(rows3[0]["price_delta_pct"], -0.05)

        # every row: fixed honest strings
        for r in rows:
            self.assertEqual(r["reviews_live"], "Unknown")
            self.assertNotEqual(r["reviews_live"], 0)
            self.assertEqual(r["bsr_live_note"], "provider does not supply BSR")

    def test_17b_all_four_similarity_labels(self):
        base = "Alpha Beta Gamma Delta"
        self.assertEqual(emr._title_similarity(base, "alpha beta gamma delta"),
                         "Exact/near-exact")
        self.assertEqual(emr._title_similarity(
            base, "Alpha beta gamma delta plus one"), "Minor cosmetic difference")
        self.assertEqual(emr._title_similarity(
            base, "Alpha beta zulu yankee"), "Potentially conflicting")
        self.assertEqual(emr._title_similarity(base, None), "Unrelated")

    def test_17c_skipped_rows_present_with_honest_notes(self):
        rows, _ = self._rows({})
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(r["outcome"] == "skipped_cap" for r in rows))
        self.assertTrue(all("No provider call made" in r["notes"] for r in rows))


class GateAndContainmentTests(Base):
    def test_18_status_dry_run_make_zero_network_calls(self):
        def boom(*a, **k):
            raise AssertionError("real network transport was called")

        with mock.patch.object(requests.api, "get", boom), \
             mock.patch.object(requests.api, "post", boom), \
             mock.patch.object(requests.api, "request", boom):
            path = self.write_manifest()
            self.assertEqual(emr.main(["status", "--manifest", path]), 0)
            self.assertEqual(emr.main(["dry-run", "--manifest", path]), 0)

    def test_19_missing_live_refuses_before_any_call(self):
        path = self.write_manifest()
        calls = self.install_client(self.ok_client())
        rc = emr.main(["run", "--manifest", path,
                       "--max-requests", "10", "--max-credits", "100"])
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])

    def test_20_missing_caps_refuse_before_any_call(self):
        path = self.write_manifest()
        calls = self.install_client(self.ok_client())
        rc1 = emr.main(["run", "--live", "--manifest", path])
        rc2 = emr.main(["run", "--live", "--manifest", path,
                        "--max-requests", "10"])
        rc3 = emr.main(["run", "--live", "--manifest", path,
                        "--max-credits", "50"])
        self.assertEqual((rc1, rc2, rc3), (2, 2, 2))
        self.assertEqual(calls, [])
        self.assertFalse(os.path.isdir(self.runs_root))


if __name__ == "__main__":
    unittest.main()
