#!/usr/bin/env python3
"""End-to-end full-pull rehearsal: real adapters + real fixtures, mocked transport.

This is the pre-live dress rehearsal for the FULL chain:

  costco_live_runner.full_pull(...)          # real runner + real adapters
    -> evidence under a temp runs root
  kirkland_costco_merge.run_merge(...)        # real merge
    -> data/costco-product-detail.json store

Both provider TRANSPORTS are mocked at the API boundary
(bright_data_client._fetch and firecrawl_costco.requests.post), so NO live or
paid call is ever made. The parsers, identity cross-checks, circuit breaker,
failover cursor, evidence persistence, and the merge all execute their REAL
code paths against the REAL captured fixtures in fixtures/brightdata_costco/.

Scenarios covered:
  1. Bright Data primary only -> full chain into the store (6 items, one
     content-404 soft failure that must NOT halt the batch and MUST NOT land
     in the store).
  2. Primary hard-fails mid-batch -> REAL failover to Firecrawl with the
     persistent cursor, both providers' evidence merged into the store.
  3. Firecrawl only (primary gate off) -> full chain into the store.
  4. Both providers hard-fail -> circuit breaker halts the pull, the store
     stays empty (no half-truth evidence ever imports).
"""

import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

import test_network_guard  # noqa: F401  (blocks real network calls)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bright_data_client
import bright_data_costco
import costco_live_runner as runner
import firecrawl_costco
import kirkland_costco_merge as merge

BD_GATE = bright_data_costco.GATE_ENV
BD_KEY = "BRIGHTDATA_UNLOCKER_API_KEY"
FC_GATE = firecrawl_costco.GATE_ENV
FC_KEY = firecrawl_costco.KEY_ENV

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "brightdata_costco"
)

# Real identity metadata from the captured fixtures (matches the parser tests).
EXPECTED = {
    "424976": (
        "Kirkland Signature Adult 50+ Mature Multi Vitamins & Minerals, 400 Tablets",
        "400 Tablets",
        17.99,
    ),
    "926628": (
        "Kirkland Signature Fish Oil 1000 mg, 400 Softgels",
        "400 Softgels",
        20.99,
    ),
    "98501": (
        "Kirkland Signature Chewable Vitamin C 500 mg, 500 Tablets",
        "500 Tablets",
        17.99,
    ),
    "690843": (
        "Kirkland Signature Quick Dissolve B-12 5000 mcg, 300 Tablets",
        "300 Tablets",
        21.99,
    ),
    "1089787": (
        "Kirkland Signature Flex-Tech 13-Gallon Kitchen Trash Bag, 200-count",
        "200 count",
        22.49,
    ),
    "1493188": (
        "Kirkland Signature Baby Wipes Fragrance Free, 900-count",
        "900-count (9x100ct)",
        None,  # content-404 fixture -> url_not_found, never imported
    ),
}

_fixture_cache = {}


def _fixture(item_id):
    if item_id not in _fixture_cache:
        path = os.path.join(FIXTURE_DIR, f"{item_id}.html")
        with open(path, "r", encoding="utf-8-sig") as fh:
            _fixture_cache[item_id] = fh.read()
    return _fixture_cache[item_id]


def _item_id_from_url(url):
    m = re.search(r"\.product\.(\d+)\.html", url or "")
    return m.group(1) if m else ""


def _url_fetch(overrides=None):
    """A bright_data_client._fetch replacement that serves the right fixture.

    ``overrides`` maps item id -> "auth_403" to simulate a hard 403 on that
    item (sets the live globals exactly like the real transport).
    """
    overrides = overrides or {}

    def _fetch(url):
        item_id = _item_id_from_url(url)
        if overrides.get(item_id) == "auth_403":
            bright_data_client.LAST_HTTP_STATUS = 403
            bright_data_client.LAST_ERROR = "auth_error: HTTP 403"
            bright_data_client.LAST_RESPONSE_HEADERS = None
            return None
        bright_data_client.LAST_HTTP_STATUS = 200
        bright_data_client.LAST_ERROR = None
        bright_data_client.LAST_RESPONSE_HEADERS = None
        return _fixture(item_id)

    return _fetch


def _fc_post(fail_ids=()):
    """A firecrawl_costco.requests.post replacement that serves fixtures per
    item id. Firecrawl posts to the API endpoint with the target page URL in
    ``json["url"]``. fail_ids -> HTTP 403 hard failure (no fixture served)."""

    def fake_post(url, json=None, headers=None, timeout=None):
        target = (json or {}).get("url") or url
        item_id = _item_id_from_url(target)
        if item_id in fail_ids:
            return _FcResponse(
                {"success": False, "error": "auth_error: HTTP 403"},
                status_code=403,
            )
        return _FcResponse(
            {
                "success": True,
                "data": {
                    "rawHtml": _fixture(item_id),
                    "metadata": {"statusCode": 200},
                },
            },
            status_code=200,
        )

    return fake_post


class _FcResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


def setUpModule():
    """Opt into both adapter gates and keep evidence OUT of the repo run dir
    even if a test forgets to pass run_dir explicitly."""
    os.environ[BD_GATE] = "1"
    os.environ[BD_KEY] = "test-key-brightdata"
    os.environ[FC_GATE] = "1"
    os.environ[FC_KEY] = "test-key-firecrawl"
    bright_data_costco.DEFAULT_RUN_DIR = tempfile.mkdtemp(prefix="rehearsal-bd-")
    firecrawl_costco.DEFAULT_RUN_DIR = tempfile.mkdtemp(prefix="rehearsal-fc-")


def tearDownModule():
    os.environ.pop(BD_GATE, None)
    os.environ.pop(BD_KEY, None)
    os.environ.pop(FC_GATE, None)
    os.environ.pop(FC_KEY, None)
    bright_data_client.LAST_ERROR = None
    bright_data_client.LAST_HTTP_STATUS = None
    bright_data_client.LAST_RESPONSE_HEADERS = None
    firecrawl_costco.LAST_ERROR = None
    firecrawl_costco.LAST_HTTP_STATUS = None
    firecrawl_costco.LAST_PAGE_STATUS = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_manifest(path, item_ids):
    items = []
    for item_id in item_ids:
        title, pack, _price = EXPECTED[item_id]
        # requested_title mirrors the real manifest (candidate title without
        # the brand prefix); the parser prepends the brand to build the title.
        items.append(
            {
                "item_id": item_id,
                "requested_title": title.replace("Kirkland Signature ", ""),
                "requested_brand": "Kirkland Signature",
                "requested_pack": pack,
                "mapped_asins": [],
            }
        )
    manifest = {
        "schema_version": 2,
        "kind": "costco_full_pull_manifest",
        "generated_at": "2026-09-08T00:00:00Z",
        "source": "rehearsal.csv",
        "count": len(items),
        "pending_lookup_count": 0,
        "items": items,
        "pending_lookup": [],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return path


def _rehearsal(tmp, name, item_ids, env, fetch_overrides=None, fc_fail_ids=()):
    """Run full_pull + merge against a hermetic manifest. Returns
    (runner_summary, merge_summary, store_path)."""
    runs_root = os.path.join(tmp, "runs")
    run_dir = os.path.join(runs_root, f"rehearsal-{name}")
    store_path = os.path.join(tmp, f"store-{name}.json")

    manifest_path = _write_manifest(os.path.join(tmp, f"manifest-{name}.json"), item_ids)

    with mock.patch.dict("os.environ", env, clear=False):
        with mock.patch.object(
            bright_data_client, "_fetch", new=_url_fetch(fetch_overrides)
        ):
            with mock.patch(
                "firecrawl_costco.requests.post", side_effect=_fc_post(fc_fail_ids)
            ):
                summary = runner.full_pull(
                    manifest_path,
                    run_dir=run_dir,
                    delay=0,
                )

    with mock.patch.dict("os.environ", {"COSTCO_CATALOG_DETAIL_PATH": store_path}):
        merge_summary = merge.run_merge(runs_root=runs_root)

    return summary, merge_summary, store_path


def _load_store(store_path):
    with open(store_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class FullPullRehearsalBrightDataPrimary(unittest.TestCase):
    """Scenario 1: Bright Data primary only (Firecrawl gate off)."""

    ENV = {
        BD_GATE: "1",
        FC_GATE: "0",
    }

    def test_full_chain_to_store_with_soft_404_item(self):
        item_ids = ["424976", "926628", "98501", "690843", "1089787", "1493188"]
        with tempfile.TemporaryDirectory() as tmp:
            summary, merge_summary, store_path = _rehearsal(
                tmp, "bd-primary", item_ids, self.ENV
            )

            # Runner: completed, Bright Data only, soft 404 does NOT halt.
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(
                summary["providers_active"], ["BRIGHTDATA_WEB_UNLOCKER"]
            )
            self.assertEqual(
                summary["provider_counts"], {"BRIGHTDATA_WEB_UNLOCKER": 6, "FIRECRAWL": 0}
            )
            self.assertEqual(summary["items_requested"], 6)
            self.assertEqual(summary["items_failed"], 0)
            self.assertEqual(summary["items_soft_failed"], 1)
            self.assertEqual(len(summary["failover_events"]), 0)
            self.assertEqual(len(summary["evidence_paths"]), 12)
            for path in summary["evidence_paths"]:
                self.assertTrue(os.path.exists(path), path)

            # Identity cross-checks MUST have run: manifest-driven probable_match
            # for served items (not the unverified fallback), url_not_found for
            # the content-404 item.
            statuses = {
                it["requested_item_id"]: it.get("identity_match_status")
                for it in summary["items"]
            }
            self.assertEqual(statuses["424976"], "probable_match")
            self.assertEqual(statuses["926628"], "probable_match")
            self.assertEqual(statuses["1089787"], "probable_match")
            self.assertEqual(statuses["1493188"], "url_not_found")

            # Merge: 5 imports (1493188 never imports), correct prices.
            self.assertEqual(merge_summary["records_imported"], 5)
            self.assertEqual(merge_summary["unique_item_ids_with_evidence"], 6)
            rows = {
                r["costco_item_id"]: r for r in _load_store(store_path)
            }
            self.assertEqual(set(rows), {"424976", "926628", "98501", "690843", "1089787"})
            self.assertEqual(rows["424976"]["current_price"], 17.99)
            self.assertEqual(rows["926628"]["current_price"], 20.99)
            self.assertEqual(rows["98501"]["current_price"], 17.99)
            self.assertEqual(rows["690843"]["current_price"], 21.99)
            self.assertEqual(rows["1089787"]["current_price"], 22.49)
            self.assertEqual(
                rows["424976"]["item_name"],
                "Kirkland Signature Adult 50+ Mature Multi Vitamins & Minerals, 400 Tablets",
            )
            self.assertEqual(rows["1089787"]["source"], "brightdata_web_unlocker")


class FullPullRehearsalFailover(unittest.TestCase):
    """Scenario 2: Bright Data hard-fails mid-batch -> real failover to
    Firecrawl with the persistent cursor; both providers merge into the store."""

    ENV = {
        BD_GATE: "1",
        FC_GATE: "1",
    }

    def test_failover_mid_batch_and_merge(self):
        item_ids = ["424976", "926628", "690843", "1089787"]
        with tempfile.TemporaryDirectory() as tmp:
            summary, merge_summary, store_path = _rehearsal(
                tmp,
                "failover",
                item_ids,
                self.ENV,
                fetch_overrides={"690843": "auth_403"},
            )

            # Runner: all four fetched, no hard failures left over.
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(
                summary["providers_active"],
                ["BRIGHTDATA_WEB_UNLOCKER", "FIRECRAWL"],
            )
            self.assertEqual(
                summary["provider_counts"],
                {"BRIGHTDATA_WEB_UNLOCKER": 3, "FIRECRAWL": 2},
            )
            self.assertEqual(summary["items_requested"], 4)
            self.assertEqual(summary["items_fetched"], 4)
            self.assertEqual(summary["items_failed"], 0)

            # One failover event, primary -> fallback, on the 403 item.
            self.assertEqual(len(summary["failover_events"]), 1)
            ev = summary["failover_events"][0]
            self.assertEqual(ev["item_id"], "690843")
            self.assertEqual(ev["from"], "BRIGHTDATA_WEB_UNLOCKER")
            self.assertEqual(ev["to"], "FIRECRAWL")
            self.assertTrue(ev["reason"].startswith("hard_failure:"))

            # Evidence provenance: first two items served by Bright Data, the
            # failover item + everything after it by Firecrawl (cursor moved).
            normalized = [
                os.path.basename(p)
                for p in summary["evidence_paths"]
                if "/normalized/" in p.replace("\\", "/")
            ]
            self.assertTrue(
                any("424976" in n and "brightdata" in n for n in normalized)
            )
            self.assertTrue(
                any("926628" in n and "brightdata" in n for n in normalized)
            )
            self.assertTrue(
                any("690843" in n and "firecrawl" in n for n in normalized)
            )
            self.assertTrue(
                any("1089787" in n and "firecrawl" in n for n in normalized)
            )

            # Merge: all four import regardless of which provider served them.
            self.assertEqual(merge_summary["records_imported"], 4)
            rows = {r["costco_item_id"]: r for r in _load_store(store_path)}
            self.assertEqual(set(rows), set(item_ids))
            self.assertEqual(rows["690843"]["current_price"], 21.99)
            self.assertEqual(rows["1089787"]["current_price"], 22.49)
            self.assertEqual(rows["690843"]["source"], "firecrawl_scrape")
            self.assertEqual(rows["1089787"]["source"], "firecrawl_scrape")
            self.assertEqual(rows["424976"]["source"], "brightdata_web_unlocker")
            self.assertEqual(rows["926628"]["source"], "brightdata_web_unlocker")


class FullPullRehearsalFirecrawlPrimary(unittest.TestCase):
    """Scenario 3: Firecrawl only (Bright Data gate off) — the free-tier
    fallback must carry the whole pull by itself."""

    ENV = {
        BD_GATE: "0",
        FC_GATE: "1",
    }

    def test_firecrawl_only_full_chain_to_store(self):
        item_ids = ["424976", "98501", "1089787"]
        with tempfile.TemporaryDirectory() as tmp:
            summary, merge_summary, store_path = _rehearsal(
                tmp, "fc-primary", item_ids, self.ENV
            )

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["providers_active"], ["FIRECRAWL"])
            self.assertEqual(
                summary["provider_counts"],
                {"BRIGHTDATA_WEB_UNLOCKER": 0, "FIRECRAWL": 3},
            )
            self.assertEqual(summary["items_fetched"], 3)
            self.assertEqual(len(summary["evidence_paths"]), 6)
            self.assertEqual(merge_summary["records_imported"], 3)
            rows = {r["costco_item_id"]: r for r in _load_store(store_path)}
            self.assertEqual(set(rows), set(item_ids))
            self.assertEqual(rows["424976"]["current_price"], 17.99)
            self.assertEqual(rows["98501"]["current_price"], 17.99)
            self.assertTrue(
                all(r["source"] == "firecrawl_scrape" for r in rows.values())
            )


class FullPullRehearsalCircuitBreaker(unittest.TestCase):
    """Scenario 4: both providers hard-fail -> the pull halts and NOTHING
    imports into the store (fail-closed, circuit breaker)."""

    ENV = {
        BD_GATE: "1",
        FC_GATE: "1",
    }

    def test_all_providers_fail_halts_empty_store(self):
        item_ids = ["424976", "98501"]
        with tempfile.TemporaryDirectory() as tmp:
            summary, merge_summary, store_path = _rehearsal(
                tmp,
                "all-fail",
                item_ids,
                self.ENV,
                fetch_overrides={"424976": "auth_403", "98501": "auth_403"},
                fc_fail_ids=("424976", "98501"),
            )

            self.assertEqual(summary["status"], "halted")
            self.assertTrue("all providers failed on item 424976" in summary["halted_reason"])
            self.assertEqual(summary["items_failed"], 1)
            self.assertEqual(summary["items_fetched"], 0)
            # Circuit breaker: the un-attempted item is explicitly recorded,
            # so requested == fetched + failed + skipped.
            self.assertEqual(summary["items_halted_skipped"], 1)
            self.assertEqual(len(summary["skipped"]), 1)
            self.assertEqual(summary["skipped"][0]["item_id"], "98501")
            self.assertEqual(summary["skipped"][0]["reason"], "halted")

            # Fail-closed at the store: no half-truth evidence ever imports.
            self.assertEqual(merge_summary["records_imported"], 0)
            self.assertEqual(_load_store(store_path), [])


if __name__ == "__main__":
    unittest.main()