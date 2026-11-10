"""Tests for Costco audit, disallowed-filter CLI, and ChromeControl bridge."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import test_network_guard  # noqa: F401

from costco_non_kirkland.audit import audit, render_audit_markdown, parse_weight_lb
from costco_non_kirkland.apply_disallowed_filter import main as apply_disallowed_main
from costco_non_kirkland.chromecontrol_bridge import read_cc_state, sync_to_northstar, default_cc_db_path
from .fixtures import source_fixture


def _isolated_store():
    import data_layer
    tmp = Path(tempfile.mkdtemp(prefix="cnk-audit-"))
    data_layer._SQLITE_PATH = tmp / "northstar.db"
    data_layer._db_instance = None
    from costco_non_kirkland.store import PipelineStore
    return PipelineStore()


class WeightParseTests(unittest.TestCase):
    def test_weight_unknown(self):
        self.assertIsNone(parse_weight_lb(None))
        self.assertIsNone(parse_weight_lb("no weight here"))

    def test_weight_lb(self):
        self.assertEqual(parse_weight_lb("1.5 lb"), 1.5)

    def test_weight_oz(self):
        self.assertAlmostEqual(parse_weight_lb("32 oz"), 2.0, places=3)


class AuditTests(unittest.TestCase):
    def _populate(self, store):
        # 1 eligible with brand+cost+pack, weight unknown
        store.upsert_source_product(source_fixture(id="c1"), run_id="run_a")
        # 1 eligible with weight <=3
        store.upsert_source_product(source_fixture(id="c2", size_or_weight_raw="2 lb"), run_id="run_a")
        # 1 eligible weight >3
        store.upsert_source_product(source_fixture(id="c3", size_or_weight_raw="8 lb"), run_id="run_a")
        # 1 kirkland excluded
        store.upsert_source_product(source_fixture(id="c4", exclusion_reason="kirkland_signature_out_of_scope",
                                                   eligible_for_costco_non_kirkland_workflow=False), run_id="run_a")
        # 1 disallowed excluded
        store.upsert_source_product(source_fixture(id="c5", exclusion_reason="disallowed_product_class",
                                                   eligible_for_costco_non_kirkland_workflow=False), run_id="run_a")

    def test_audit_counts(self):
        store = _isolated_store()
        self._populate(store)
        a = audit(store, run_id="run_a")
        self.assertEqual(a["total_source_records"], 5)
        self.assertEqual(a["kirkland_excluded"], 1)
        self.assertEqual(a["disallowed_excluded"], 1)
        self.assertEqual(a["confirmed_le_3lb"], 1)
        self.assertEqual(a["confirmed_gt_3lb"], 1)
        self.assertEqual(a["unknown_weight"], 1)
        self.assertEqual(a["strict_costco_side_eligible"], 1)  # only the 2 lb record
        self.assertGreaterEqual(a["provisional_eligible"], 1)

    def test_audit_markdown(self):
        store = _isolated_store()
        self._populate(store)
        md = render_audit_markdown(audit(store, run_id="run_a"))
        self.assertIn("Strict Costco-side eligible", md)
        self.assertIn("Not purchase authorized", md)


class DisallowedFilterCliTests(unittest.TestCase):
    def test_dry_run_no_write(self):
        store = _isolated_store()
        store.upsert_source_product(source_fixture(id="d1", title_raw="Industrial Muriatic Acid Cleaner",
                                                   brand_raw="Acme"), run_id="run_d")
        rc = apply_disallowed_main(["--run-id", "run_d", "--dry-run"])
        self.assertEqual(rc, 0)


class BridgeTests(unittest.TestCase):
    def test_read_cc_state_missing_db(self):
        state = read_cc_state(str(Path(tempfile.mkdtemp()) / "nope.db"))
        self.assertFalse(state["available"])
        self.assertEqual(state["tabs"], [])

    def test_default_cc_db_path(self):
        self.assertTrue(default_cc_db_path().endswith("northstar.db"))

    def test_sync_no_cc_db(self):
        store = _isolated_store()
        out = sync_to_northstar(store, cc_db_path=str(Path(tempfile.mkdtemp()) / "nope.db"))
        self.assertEqual(out["available"], False)


if __name__ == "__main__":
    unittest.main()
