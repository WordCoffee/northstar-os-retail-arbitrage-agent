"""Offline tests for margin_shortlist.py (zero network; CSV client mocked)."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import margin_shortlist as ms


def _mk(tmp: Path, items, enriched):
    mpath = tmp / "manifest.json"
    mpath.write_text(json.dumps({"items": items}), encoding="utf-8")
    rundir = tmp / "run"
    (rundir / "normalized").mkdir(parents=True)
    for asin, payload in enriched.items():
        (rundir / "normalized" / ("%s.json" % asin)).write_text(
            json.dumps(payload), encoding="utf-8")
    return mpath, rundir


def _item(asin, title="Kirkland T"):
    return {"asin": asin, "title": title,
            "quantity_match": {"status": "PASS"}}


def _enr(buy_box=20.0, fee=5.25, weight=None, title="Kirkland T"):
    d = {"buy_box_price": buy_box, "fba_fee": fee, "weight_lbs": weight,
         "title": title}
    return d


class MarginShortlistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _run(self, items, enriched, cost_map, **kw):
        mpath, rundir = _mk(self.tmp, items, enriched)

        def fake_cost(title):
            return cost_map.get(title, {"match_quality": "unknown",
                                        "match_reason": "none",
                                        "costco_cost": None})

        with patch.object(ms.costco_client, "get_costco_price",
                          side_effect=fake_cost):
            return ms.build_shortlist(str(mpath), str(rundir), **kw)

    def test_ranks_profitable_and_sorts_desc(self):
        items = [_item("B00BH3HPZW", "Alpha"), _item("B0017SURSY", "Beta")]
        enriched = {"B00BH3HPZW": _enr(buy_box=20.0, title="Alpha"),
                    "B0017SURSY": _enr(buy_box=40.0, title="Beta")}
        cost = {"Alpha": {"match_quality": "exact", "costco_cost": 8.0},
                "Beta": {"match_quality": "high_confidence", "costco_cost": 10.0}}
        res, err = self._run(items, enriched, cost)
        self.assertIsNone(err)
        # Beta: 40-10-6-5.25-0.18-0.35=18.22; Alpha: 20-8-3-5.25-0.18-0.35=3.22
        self.assertEqual(res["ranked_total"], 1)
        self.assertEqual(res["ranked"][0]["asin"], "B0017SURSY")
        self.assertAlmostEqual(res["ranked"][0]["profit"], 18.22, places=2)

    def test_weight_estimated_fee_used_when_enriched_missing(self):
        items = [_item("B00BH3HPZW", "Alpha")]
        enriched = {"B00BH3HPZW": _enr(buy_box=40.0, fee=None, weight=0.4,
                                       title="Alpha")}
        cost = {"Alpha": {"match_quality": "exact", "costco_cost": 10.0}}
        res, err = self._run(items, enriched, cost)
        self.assertIsNone(err)
        self.assertEqual(res["ranked_total"], 1)
        self.assertEqual(res["ranked"][0]["fba_fee_basis"], "weight-estimated")
        self.assertAlmostEqual(res["ranked"][0]["fba_fee"], 4.75, places=2)

    def test_untrusted_match_goes_to_needs_cost(self):
        items = [_item("B00BH3HPZW", "Alpha")]
        enriched = {"B00BH3HPZW": _enr(buy_box=40.0, title="Alpha")}
        cost = {"Alpha": {"match_quality": "candidate", "costco_cost": 5.0,
                          "match_reason": "weak"}}
        res, err = self._run(items, enriched, cost)
        self.assertIsNone(err)
        self.assertEqual(res["ranked_total"], 0)
        self.assertEqual(len(res["needs_cost"]), 1)

    def test_missing_fee_goes_to_needs_fee(self):
        items = [_item("B00BH3HPZW", "Alpha")]
        enriched = {"B00BH3HPZW": _enr(buy_box=40.0, fee=None, weight=None,
                                       title="Alpha")}
        cost = {"Alpha": {"match_quality": "exact", "costco_cost": 5.0}}
        res, err = self._run(items, enriched, cost)
        self.assertIsNone(err)
        self.assertEqual(len(res["needs_fee"]), 1)

    def test_price_outliers_flagged_not_ranked(self):
        items = [_item("B00BH3HPZW", "A"), _item("B0017SURSY", "B"),
                 _item("B00269UWFG", "C")]
        enriched = {"B00BH3HPZW": _enr(buy_box=None, title="A"),
                    "B0017SURSY": _enr(buy_box=0.12, title="B"),
                    "B00269UWFG": _enr(buy_box=925.0, title="C")}
        res, err = self._run(items, enriched, {})
        self.assertIsNone(err)
        self.assertEqual(len(res["price_flagged"]), 3)
        self.assertEqual(res["ranked_total"], 0)

    def test_non_pass_and_bad_asin_excluded(self):
        items = [{"asin": "B00BH3HPZW", "title": "A",
                  "quantity_match": {"status": "REVIEW"}},
                 {"asin": "SHORT", "title": "B",
                  "quantity_match": {"status": "PASS"}}]
        res, err = self._run(items, {}, {})
        self.assertIsNone(err)
        self.assertEqual(res["ranked_total"], 0)
        self.assertEqual(len(res["price_flagged"]), 0)

    def test_top_cap_applies(self):
        asins = ["B%09d" % i for i in range(5)]
        items = [_item(a, "T%d" % i) for i, a in enumerate(asins)]
        enriched = {a: _enr(buy_box=40.0, title="T%d" % i)
                    for i, a in enumerate(asins)}
        cost = {"T%d" % i: {"match_quality": "exact", "costco_cost": 5.0}
                for i in range(5)}
        res, err = self._run(items, enriched, cost, top=3)
        self.assertIsNone(err)
        self.assertEqual(res["ranked_total"], 5)
        self.assertEqual(len(res["ranked"]), 3)

    def test_below_cut_bucketed_not_ranked(self):
        items = [_item("B00BH3HPZW", "Alpha")]
        enriched = {"B00BH3HPZW": _enr(buy_box=20.0, title="Alpha")}
        cost = {"Alpha": {"match_quality": "exact", "costco_cost": 8.0}}
        res, err = self._run(items, enriched, cost)
        self.assertIsNone(err)
        # profit = 20-8-3-5.25-0.18-0.35 = 3.22 < 9
        self.assertEqual(res["ranked_total"], 0)
        self.assertEqual(len(res["below_cut"]), 1)
        self.assertAlmostEqual(res["below_cut"][0]["profit"], 3.22, places=2)

    def test_ceilings_computed_for_fee_complete_asins(self):
        items = [_item("B00BH3HPZW", "Alpha"), _item("B0017SURSY", "Beta")]
        enriched = {"B00BH3HPZW": _enr(buy_box=40.0, title="Alpha"),
                    "B0017SURSY": _enr(buy_box=40.0, fee=None, weight=None,
                                       title="Beta")}
        res, err = self._run(items, enriched, {})
        self.assertIsNone(err)
        # Alpha ceiling = 40-6-5.25-0.18-0.35-9 = 19.22; Beta needs-fee.
        self.assertEqual(len(res["ceilings"]), 1)
        self.assertAlmostEqual(res["ceilings"][0]["cogs_ceiling"], 19.22,
                               places=2)
        self.assertEqual(len(res["needs_fee"]), 1)


if __name__ == "__main__":
    unittest.main()
