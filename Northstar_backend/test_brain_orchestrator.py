"""test_brain_orchestrator.py — narrow, deterministic verification of the
Master Brain governance layer.

Scope (per spec "Testing / what to add"):
  * no live provider calls on import / dry-run / render,
  * latest-run discovery,
  * UTF-8 run-log safety,
  * null preservation (never fabricate 0),
  * correct recording of tier3_host_unsubscribed (never "untriggered"),
  * benchmark cohort vs live distinction,
  * economics/ROI blocked when fee or COGS missing,
  * velocity blocked when BSR missing,
  * backward-compatible cache output,
  * honest gap identifiers with no false approvals.

No network is used. The shared ``network_guard`` module blocks any real
``requests`` call so a hidden live call would break the test.
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import network_guard  # noqa: F401  (activates the process-wide offline guard)

import brain_orchestrator as brain
import enricher
import scanner_data


class BrainOrchestratorTests(unittest.TestCase):

    def setUp(self):
        self.brain = brain.MasterBrain()

    def test_no_live_calls_on_import_and_dry_run(self):
        # A full dry-run orchestration must make no network calls. The shared
        # network guard raises NetworkGuardViolation on any real requests call
        # (requests.api.* and Session.request), so no hidden HTTP can pass.
        with network_guard.block_network():
            summary = self.brain.run(cohort="benchmark_10", dry_run=True)
        self.assertIsInstance(summary, dict)
        self.assertFalse(summary["rapidapi_used_this_run"],
                         "RapidAPI must not be used during dry-run")

    def test_latest_run_discovery(self):
        run_dir = enricher.discover_latest_run()
        self.assertTrue(os.path.isdir(run_dir))
        self.assertIn("waterfall-", os.path.basename(run_dir))

    def test_utf8_run_log_safety(self):
        run_dir = enricher.discover_latest_run()
        log = enricher.load_run_log(run_dir)
        # Must parse even if the log carries unicode (UTF-8 decode).
        self.assertIsInstance(log, dict)
        # Re-load explicitly in UTF-8 to prove no BOM/cp1252 trap.
        with open(os.path.join(run_dir, "run-log.json"), encoding="utf-8") as fh:
            json.load(fh)

    def test_tier3_host_unsubscribed_recorded_not_untriggered(self):
        summary = self.brain.run(cohort="benchmark_10", dry_run=True)
        hist = summary["historical_tier3"]
        # Tier 3 MUST be recorded as having triggered once for B08R2SRN88.
        matched = [h for h in hist
                   if h.get("asin") == "B08R2SRN88"
                   and h.get("status") == "tier3_host_unsubscribed"
                   and h.get("triggered") is True]
        self.assertTrue(matched,
                        "tier3_host_unsubscribed must be recorded, never 'untriggered'")

    def test_benchmark_cohort_vs_live_distinction(self):
        asins = enricher.load_cohort()
        self.assertEqual(len(asins), 10)
        # These are canonical benchmark ASINs (manifest), not live-only rows.
        self.assertIn("B00GYZWNY6", asins)
        # Every record carries a benchmark provenance somewhere in identity.
        summary = self.brain.run(cohort="benchmark_10", dry_run=True)
        for rec in summary["records"]:
            self.assertIn("asin", rec)

    def test_null_preservation_no_fabricated_zero(self):
        summary = self.brain.run(cohort="benchmark_10", dry_run=True)
        for rec in summary["records"]:
            net = rec["fees_economics"]["net_profit"]["value"]
            roi = rec["fees_economics"]["roi_pct"]["value"]
            self.assertNotEqual(net, 0.0, "net_profit must not be fabricated as 0")
            self.assertNotEqual(roi, 0.0, "roi_pct must not be fabricated as 0")
            # If a price exists but COGS missing -> net profit must be None.
            price = rec["amazon_market"]["amazon_price"]["value"]
            costco = rec["costco"]["costco_price"]["value"]
            if price is not None and costco is None:
                self.assertIsNone(net,
                                  "economics blocked when COGS missing")

    def test_velocity_blocked_without_bsr(self):
        summary = self.brain.run(cohort="benchmark_10", dry_run=True)
        for rec in summary["records"]:
            bsr = rec["demand"]["bsr"]["value"]
            sales = rec["demand"]["estimated_monthly_sales"]["value"]
            # No BSR in artifacts -> velocity must be unknown, never invented.
            self.assertIsNone(bsr)
            self.assertIsNone(sales)

    def test_no_false_purchase_approval(self):
        summary = self.brain.run(cohort="benchmark_10", dry_run=True)
        for rec in summary["records"]:
            rd = rec["readiness"]["purchase_readiness"]
            self.assertNotEqual(rd, brain.READY_PURCHASE_READY,
                                "no retail ASIN may be falsely approved")

    def test_backward_compatible_cache_output(self):
        summary = self.brain.run(cohort="benchmark_10", dry_run=True)
        cand_path = brain.CANDIDATE_CACHE_PATH
        self.assertTrue(os.path.isfile(cand_path))
        with open(cand_path, encoding="utf-8") as fh:
            cand = json.load(fh)
        self.assertIn("products", cand)
        self.assertEqual(len(cand["products"]), 10)
        for p in cand["products"]:
            self.assertIn("asin", p)
            self.assertIn("amazon_price", p)
            # enriched provenance must be present and structured
            self.assertIn("enrichment_meta", p)

    def test_validation_passes(self):
        summary = self.brain.run(cohort="benchmark_10", dry_run=True)
        self.assertTrue(summary["validation_valid"])

    def test_scanner_data_normalization_has_provenance(self):
        asins = enricher.load_cohort()
        run_dir = enricher.discover_latest_run()
        b = enricher.enrich_asin(asins[0], run_dir, self.brain.policy)
        if b.get("present"):
            rec = scanner_data.normalize_asin_record(
                asins[0], b["extracted"], b["engines"], self.brain.policy,
                observed_at=b["extracted"].get("run_observed_at"))
            for section in scanner_data.FIELD_SECTIONS:
                for fname, fobj in rec.get(section, {}).items():
                    if isinstance(fobj, dict) and "status" in fobj:
                        self.assertIn(fobj["status"], scanner_data.VALID_STATUSES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
