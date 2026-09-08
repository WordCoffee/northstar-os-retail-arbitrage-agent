"""Unit tests for the unified Costco live runner (provider failover + full pull).

Never makes live calls: both provider refresh functions are fully mocked.
Covers:
  (1) fail-closed gating per provider (gate + key presence), blocked summary
  (2) AUTO failover: primary hard-failure advances to the fallback AND STAYS
      there (persistent cursor), with one failover event recorded
  (3) explicit-provider mode
  (4) provider budgets switch mid-batch; exhausted-budget skip is explicit
  (5) all-providers-fail halts the whole batch (circuit breaker)
  (6) soft per-item failures do NOT trigger failover
  (7) build_full_pull_manifest from the master price capture CSV (+ dedupe +
      pending_lookup for rows without an item number)
  (8) full_pull dry-run planning (zero network) and skip-fresh-days
  (9) budget parsing for both string and dict forms
"""

import csv
import json
import os
import tempfile
import unittest
from unittest import mock

import test_network_guard  # noqa: F401  (blocks real network calls)

import bright_data_costco
import costco_live_runner as clr
import firecrawl_costco

BD = "BRIGHTDATA_WEB_UNLOCKER"
FC = "FIRECRAWL"

ENV_ON = {
    "BRIGHTDATA_COSTCO_DETAIL_ENABLED": "1",
    "BRIGHTDATA_UNLOCKER_API_KEY": "bd-test",
    "FIRECRAWL_COSTCO_DETAIL_ENABLED": "1",
    "FIRECRAWL_API_KEY": "fc-test",
}


def _env(**overrides):
    env = dict(ENV_ON)
    env.update(overrides)
    return env


def _item(item_id, status="probable_match"):
    return {
        "requested_item_id": item_id,
        "identity_match_status": status,
        "exact_title": "Kirkland Test %s" % item_id,
        "listed_price": 17.99,
    }


def _completed(item_id, provider, status="probable_match"):
    return {
        "status": "completed",
        "provider": provider,
        "items": [_item(item_id, status)],
        "failures": [],
        "evidence_paths": ["raw_%s_%s" % (provider, item_id), "norm_%s_%s" % (provider, item_id)],
    }


def _halted(item_id, provider, failure_type="auth_error"):
    return {
        "status": "halted",
        "provider": provider,
        "items": [],
        "failures": [{"item_id": item_id, "failure_type": failure_type}],
        "evidence_paths": ["raw_fail_%s" % item_id, "norm_fail_%s" % item_id],
    }


def _patch_providers(bd=None, fc=None):
    """Patch both provider module refresh functions (Mock/return values)."""
    patchers = [
        mock.patch.object(
            bright_data_costco, "refresh_product_details", side_effect=bd
        ) if bd is not None else mock.patch.object(
            bright_data_costco, "refresh_product_details"
        ),
        mock.patch.object(
            firecrawl_costco, "refresh_product_details", side_effect=fc
        ) if fc is not None else mock.patch.object(
            firecrawl_costco, "refresh_product_details"
        ),
    ]
    return patchers


class GateTests(unittest.TestCase):
    def test_status_reports_gates(self):
        with mock.patch.dict("os.environ", _env()):
            statuses = clr.provider_status()
        self.assertEqual([s["provider"] for s in statuses], [BD, FC])
        self.assertTrue(all(s["enabled"] for s in statuses))

    def test_gate_off_reports_disabled(self):
        with mock.patch.dict(
            "os.environ", _env(BRIGHTDATA_COSTCO_DETAIL_ENABLED="0")
        ):
            statuses = clr.provider_status()
        self.assertFalse(statuses[0]["enabled"])
        self.assertTrue(statuses[1]["enabled"])

    def test_no_provider_enabled_returns_blocked(self):
        with mock.patch.dict(
            "os.environ",
            {"BRIGHTDATA_COSTCO_DETAIL_ENABLED": "0", "FIRECRAWL_COSTCO_DETAIL_ENABLED": "0"},
        ):
            summary = clr.refresh_product_details(["424976"])
        self.assertEqual(summary["status"], "blocked")
        self.assertIn("no costco detail provider", summary["reason"])
        self.assertEqual(summary["items_fetched"], 0)

    def test_unknown_provider_returns_blocked(self):
        with mock.patch.dict("os.environ", _env()):
            summary = clr.refresh_product_details(["424976"], provider="NOPE")
        self.assertEqual(summary["status"], "blocked")
        self.assertIn("unknown provider", summary["reason"])

    def test_explicit_provider_disabled_returns_blocked(self):
        with mock.patch.dict(
            "os.environ",
            {"FIRECRAWL_COSTCO_DETAIL_ENABLED": "1", "FIRECRAWL_API_KEY": "k", "BRIGHTDATA_COSTCO_DETAIL_ENABLED": "0"},
        ):
            summary = clr.refresh_product_details(["424976"], provider=BD)
        self.assertEqual(summary["status"], "blocked")


class FailoverTests(unittest.TestCase):
    def test_auto_primary_succeeds_secondary_untouched(self):
        bd = mock.Mock(return_value=_completed("424976", BD))
        fc = mock.Mock()
        with mock.patch.dict("os.environ", _env()):
            with mock.patch.object(
                bright_data_costco, "refresh_product_details", side_effect=bd
            ), mock.patch.object(
                firecrawl_costco, "refresh_product_details", side_effect=fc
            ):
                summary = clr.refresh_product_details(["424976", "98501"])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_fetched"], 2)
        self.assertEqual(bd.call_count, 2)
        fc.assert_not_called()
        self.assertEqual(summary["providers_used"], [BD])
        self.assertEqual(summary["failover_events"], [])

    def test_auto_fails_over_to_secondary_and_stays(self):
        # BD hard-fails on item 1; FC takes item 1; item 2 goes straight to FC.
        def bd_side_effect(item_ids, **kwargs):
            return _halted(item_ids[0], BD, "auth_error")

        def fc_side_effect(item_ids, **kwargs):
            return _completed(item_ids[0], FC)

        with mock.patch.dict("os.environ", _env()):
            with mock.patch.object(
                bright_data_costco, "refresh_product_details", side_effect=bd_side_effect
            ), mock.patch.object(
                firecrawl_costco, "refresh_product_details", side_effect=fc_side_effect
            ):
                summary = clr.refresh_product_details(["424976", "98501"])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_fetched"], 2)
        # BD attempted only item 1 once (then cursor moved on); FC served both.
        self.assertEqual(len(summary["failover_events"]), 1)
        event = summary["failover_events"][0]
        self.assertEqual(event["from"], BD)
        self.assertEqual(event["to"], FC)
        self.assertIn("auth_error", event["reason"])
        self.assertEqual(summary["providers_used"], [BD, FC])
        # item 2 served by FC without another BD attempt
        served_items = [it["requested_item_id"] for it in summary["items"]]
        self.assertEqual(served_items, ["424976", "98501"])

    def test_all_providers_fail_halts_batch(self):
        def bd_side_effect(item_ids, **kwargs):
            return _halted(item_ids[0], BD, "auth_error")

        def fc_side_effect(item_ids, **kwargs):
            return _halted(item_ids[0], FC, "http_error")

        with mock.patch.dict("os.environ", _env()):
            with mock.patch.object(
                bright_data_costco, "refresh_product_details", side_effect=bd_side_effect
            ), mock.patch.object(
                firecrawl_costco, "refresh_product_details", side_effect=fc_side_effect
            ):
                summary = clr.refresh_product_details(["424976", "98501"])
        self.assertEqual(summary["status"], "halted")
        self.assertIn("all providers failed", summary["halted_reason"])
        self.assertEqual(summary["items_fetched"], 0)
        # Circuit breaker halts at the first unreachable item: item 2 is never
        # attempted, so exactly ONE failure is recorded (the FC halt that ended
        # the batch).
        self.assertEqual(summary["items_failed"], 1)
        self.assertEqual([f["item_id"] for f in summary["failures"]], ["424976"])
        # The second item was never attempted after the halt.
        served = [it["requested_item_id"] for it in summary["items"]]
        self.assertNotIn("98501", served)

    def test_soft_failure_does_not_failover(self):
        bd = mock.Mock(return_value=_completed("424976", BD, status="url_not_found"))
        fc = mock.Mock()
        with mock.patch.dict("os.environ", _env()):
            with mock.patch.object(
                bright_data_costco, "refresh_product_details", side_effect=bd
            ), mock.patch.object(
                firecrawl_costco, "refresh_product_details", side_effect=fc
            ):
                summary = clr.refresh_product_details(["424976"])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_soft_failed"], 1)
        self.assertEqual(summary["failover_events"], [])
        fc.assert_not_called()

    def test_budget_switches_mid_batch(self):
        def bd_side_effect(item_ids, **kwargs):
            return _completed(item_ids[0], BD)

        def fc_side_effect(item_ids, **kwargs):
            return _completed(item_ids[0], FC)

        with mock.patch.dict("os.environ", _env()):
            with mock.patch.object(
                bright_data_costco, "refresh_product_details", side_effect=bd_side_effect
            ), mock.patch.object(
                firecrawl_costco, "refresh_product_details", side_effect=fc_side_effect
            ):
                summary = clr.refresh_product_details(
                    ["424976", "98501", "690843"],
                    budgets={BD: 1, FC: 10},
                )
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_fetched"], 3)
        self.assertEqual(summary["provider_counts"][BD], 1)
        self.assertEqual(summary["provider_counts"][FC], 2)
        self.assertEqual(len(summary["failover_events"]), 1)
        self.assertEqual(summary["failover_events"][0]["reason"], "budget_exhausted")

    def test_all_budgets_exhausted_skips_explicitly(self):
        def bd_side_effect(item_ids, **kwargs):
            return _completed(item_ids[0], BD)

        with mock.patch.dict("os.environ", _env()):
            with mock.patch.object(
                bright_data_costco, "refresh_product_details", side_effect=bd_side_effect
            ), mock.patch.object(
                firecrawl_costco, "refresh_product_details",
                side_effect=lambda ids, **kw: _completed(ids[0], FC),
            ):
                summary = clr.refresh_product_details(
                    ["424976", "98501"], budgets={BD: 1, FC: 1}
                )
        self.assertEqual(summary["items_fetched"], 2)
        self.assertEqual(summary["skipped"], [])

    def test_explicit_provider_mode(self):
        fc = mock.Mock(return_value=_completed("424976", FC))
        with mock.patch.dict("os.environ", _env()):
            with mock.patch.object(
                firecrawl_costco, "refresh_product_details", side_effect=fc
            ), mock.patch.object(
                bright_data_costco, "refresh_product_details"
            ) as bd:
                summary = clr.refresh_product_details(["424976"], provider=FC)
        self.assertEqual(summary["status"], "completed")
        bd.assert_not_called()
        self.assertEqual(summary["providers_used"], [FC])


class BudgetParseTests(unittest.TestCase):
    def test_string_form(self):
        budgets = clr._parse_budgets("BRIGHTDATA_WEB_UNLOCKER=100,FIRECRAWL=50")
        self.assertEqual(
            budgets, {BD: 100, FC: 50}
        )

    def test_dict_form(self):
        self.assertEqual(clr._parse_budgets({BD: 5, FC: None}), {BD: 5, FC: None})

    def test_invalid_string_raises(self):
        with self.assertRaises(ValueError):
            clr._parse_budgets("BRIGHTDATA_WEB_UNLOCKER=abc")


class BuildManifestTests(unittest.TestCase):
    def _csv(self, path):
        # Same 35-column layout as the real master price capture CSV
        # (data/catalog/costco_master_price_capture_*.csv).
        header = [
            "Priority tier", "Opportunity score", "Decision-ready status", "ASIN",
            "Exact Amazon title", "Amazon brand", "Amazon category",
            "Amazon pack / size / count", "Amazon current price", "Amazon BSR rank",
            "Amazon BSR category", "Demand lane", "Observed offer count",
            "Costco candidate title", "Costco candidate item number",
            "Costco candidate UPC", "Costco candidate pack / size / count",
            "Costco current shelf price", "Costco instant-savings amount",
            "Costco final shelf price", "Costco unit-normalized cost",
            "Package-match status", "Match source", "Match confidence",
            "Costco found in warehouse?", "Costco warehouse location",
            "Store item number confirmed?", "UPC confirmed?", "Shelf price observed",
            "Promo observed", "Final paid price observed", "Pack / size observed",
            "Package photo captured?", "Date checked", "Notes / mismatch detail",
        ]
        rows = [
            {
                "Priority tier": "T1",
                "Opportunity score": "95",
                "Decision-ready status": "Yes",
                "ASIN": "B00YGMN122",
                "Exact Amazon title": "Kirkland Adult 50+ Mature Multi, 400 Tablets",
                "Amazon brand": "Kirkland Signature",
                "Amazon category": "Health",
                "Amazon pack / size / count": "400 Tablets",
                "Amazon current price": "17.99",
                "Costco candidate title": "Kirkland Signature Adult 50+ Mature Multi, 400 Tablets",
                "Costco candidate item number": "424976",
                "Costco candidate pack / size / count": "400 Tablets",
            },
            {
                "Priority tier": "T1",
                "Opportunity score": "90",
                "ASIN": "B00P8ZAWK0",
                "Exact Amazon title": "Kirkland Adult 50+ Mature Multi (2nd asin)",
                "Amazon brand": "Kirkland Signature",
                "Amazon pack / size / count": "400 Tablets",
                "Costco candidate title": "Kirkland Signature Adult 50+ Mature Multi, 400 Tablets",
                "Costco candidate item number": "424976",
                "Costco candidate pack / size / count": "400 Tablets",
            },
            {
                "Priority tier": "T2",
                "Opportunity score": "70",
                "Decision-ready status": "No",
                "ASIN": "B0XXXX0001",
                "Exact Amazon title": "Some Other Product",
                "Amazon brand": "SomeBrand",
                "Amazon category": "Health",
                "Costco candidate title": "Another Costco Product",
                # no Costco candidate item number -> pending_lookup
            },
        ]
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=header)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def test_build_full_pull_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "master.csv")
            self._csv(csv_path)
            manifest = clr.build_full_pull_manifest(csv_path)
        self.assertEqual(manifest["count"], 1)  # 424976 deduped
        self.assertEqual(manifest["pending_lookup_count"], 1)
        item = manifest["items"][0]
        self.assertEqual(item["item_id"], "424976")
        self.assertIn("B00YGMN122", item["mapped_asins"])
        self.assertIn("B00P8ZAWK0", item["mapped_asins"])
        self.assertEqual(item["requested_brand"], "Kirkland Signature")
        self.assertEqual(item["requested_pack"], "400 Tablets")
        pending = manifest["pending_lookup"][0]
        self.assertEqual(pending["reason"], "no_costco_item_number")
        self.assertEqual(pending["asin"], "B0XXXX0001")

    def test_manifest_written_to_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "master.csv")
            out_path = os.path.join(tmp, "sub", "full-pull.json")
            self._csv(csv_path)
            manifest = clr.build_full_pull_manifest(csv_path, out_path=out_path)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, "r", encoding="utf-8") as fh:
                reloaded = json.load(fh)
            self.assertEqual(reloaded["kind"], "costco_full_pull_manifest")
            self.assertEqual(reloaded["count"], manifest["count"])


class FullPullTests(unittest.TestCase):
    def _manifest(self, tmp, item_ids):
        manifest = {
            "schema_version": 2,
            "kind": "costco_full_pull_manifest",
            "generated_at": "2026-09-08T00:00:00+00:00",
            "source": "master.csv",
            "count": len(item_ids),
            "pending_lookup_count": 0,
            "items": [
                {"item_id": iid, "requested_title": "Kirkland %s" % iid,
                 "requested_brand": "Kirkland Signature", "requested_pack": None,
                 "mapped_asins": []}
                for iid in item_ids
            ],
            "pending_lookup": [],
        }
        path = os.path.join(tmp, "full-pull.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        return path

    def test_dry_run_plans_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._manifest(tmp, ["424976", "98501"])
            with mock.patch.dict("os.environ", _env()):
                plan = clr.full_pull(manifest_path, dry_run=True)
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["network_calls"], 0)
        self.assertEqual(plan["to_fetch"], ["424976", "98501"])
        self.assertEqual(plan["manifest_items"], 2)
        self.assertEqual(plan["estimated_credits"], {BD: 2, FC: 2})

    def test_skip_fresh_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._manifest(tmp, ["424976", "98501"])
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            fresh_iso = (now - datetime.timedelta(days=1)).isoformat()
            stale_iso = (now - datetime.timedelta(days=60)).isoformat()
            store_path = os.path.join(tmp, "costco-product-detail.json")
            with open(store_path, "w", encoding="utf-8") as fh:
                json.dump(
                    [
                        {"costco_item_id": "424976", "captured_at": fresh_iso},
                        {"costco_item_id": "98501", "captured_at": stale_iso},
                    ],
                    fh,
                )
            with mock.patch.dict("os.environ", _env()):
                with mock.patch.object(
                    clr, "_freshness_store_paths", return_value=[store_path]
                ):
                    plan = clr.full_pull(
                        manifest_path, skip_fresh_days=7, dry_run=True
                    )
        self.assertEqual(plan["to_fetch"], ["98501"])
        self.assertEqual(len(plan["skipped_fresh"]), 1)
        self.assertEqual(plan["skipped_fresh"][0]["item_id"], "424976")

    def test_full_pull_runs_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._manifest(tmp, ["424976"])
            with mock.patch.dict("os.environ", _env()):
                with mock.patch.object(
                    bright_data_costco, "refresh_product_details",
                    return_value=_completed("424976", BD),
                ):
                    summary = clr.full_pull(manifest_path)
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_fetched"], 1)
        self.assertEqual(summary["manifest_path"], manifest_path)


if __name__ == "__main__":
    unittest.main()