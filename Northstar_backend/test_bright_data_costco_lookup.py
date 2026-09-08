"""Unit tests for the Bright Data Web Unlocker Costco search lookup.

Never makes live calls: bright_data_client._fetch is fully mocked with
synthetic Costco search-results HTML. Covers the search-page parser
(candidate extraction + Jaccard ranking), the three lookup outcomes
(lookup_candidate / lookup_weak_match / lookup_no_results), the fail-closed
gate, the hard-failure circuit breaker (halt), soft per-item continuation,
zero retries, and scrubbed evidence persistence.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

import test_network_guard  # noqa: F401  (blocks real network calls)

import bright_data_client
import bright_data_costco_lookup as lookup
from bright_data_costco_lookup import (
    COSTCO_SEARCH_URL_TEMPLATE,
    _key,
    parse_costco_search_page,
    resolve_by_search,
)

GATE_ENV = "BRIGHTDATA_COSTCO_DETAIL_ENABLED"


def _search_html(*candidates):
    """Synthetic Costco search results page with optional (href, anchor) pairs."""
    parts = [
        "<html><head><title>Costco Search</title></head><body>",
        '<div class="product-list">',
    ]
    for href, anchor in candidates:
        parts.append(
            f'<a href="{href}" class="product-title">{anchor}</a>'
        )
    parts.append("</div></body></html>")
    return "".join(parts)


def _anchor(pid, title, slug="kirkland-signature-product"):
    return (
        f"https://www.costco.com/{slug}.product.{pid}.html",
        title,
    )


class ParserTests(unittest.TestCase):
    def test_ranks_correct_candidate_first(self):
        html = _search_html(
            _anchor("50001", "Kirkland Signature Smoked Salmon, 12 oz"),
            _anchor("30055", "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Rolls",
                    slug="kirkland-signature-paper-towels"),
        )
        out = parse_costco_search_page(
            html,
            "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Individually Wrapped Rolls",
        )
        self.assertEqual(out["status"], "lookup_candidate")
        self.assertEqual(out["best"]["item_id"], "30055")
        self.assertGreaterEqual(out["best"]["score"], 0.50)
        self.assertGreater(
            out["candidates"][0]["score"], out["candidates"][1]["score"]
        )

    def test_item_id_regex_captures_numeric_ids(self):
        html = _search_html(
            _anchor("30055", "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Rolls",
                    slug="kirkland-signature-paper-towels"),
        ) + '<a href="https://www.costco.com/.product.284601.html">Whole Almonds 3 lbs</a>'
        out = parse_costco_search_page(html, "Kirkland Signature Whole Almonds, 3 lbs")
        ids = [c["item_id"] for c in out["candidates"]]
        self.assertIn("284601", ids)
        self.assertIn("30055", ids)

    def test_no_results_when_no_product_links(self):
        html = '<html><body><div id="no-results">Sorry, we could not find any matches.</div></body></html>'
        out = parse_costco_search_page(html, "Kirkland Signature Mattress")
        self.assertEqual(out["status"], "lookup_no_results")
        self.assertEqual(out["candidates"], [])
        self.assertIsNone(out["best"])

    def test_weak_match_when_best_below_threshold(self):
        html = _search_html(
            _anchor("70001", "Kirkland Signature Women's Lightweight Hoodie"),
        )
        # Unrelated query -> hoodie anchor scores far below 0.50.
        out = parse_costco_search_page(html, "Kirkland Signature Organic Quinoa, 4.5 lbs")
        self.assertEqual(out["status"], "lookup_weak_match")
        self.assertEqual(out["best"]["item_id"], "70001")
        self.assertLess(out["best"]["score"], 0.5)

    def test_bare_product_links_without_anchor_text(self):
        html = '<html><body><a href="https://www.costco.com/.product.424976.html"> </a></body></html>'
        out = parse_costco_search_page(html, "Kirkland Signature Multi Vitamins")
        self.assertEqual(out["status"], "lookup_weak_match")
        self.assertEqual(out["candidates"][0]["item_id"], "424976")
        self.assertEqual(out["candidates"][0]["score"], 0.0)

    def test_key_produces_safe_filename_component(self):
        self.assertEqual(_key("Kirkland Signature Paper Towels!"), "kirkland-signature-paper-towels")
        long_q = "kirkland-signature-" + ("x" * 120)
        self.assertLessEqual(len(_key(long_q)), 60)

    def test_page_not_found_is_its_own_lookup_status(self):
        # A Costco content-404 (title "Page Not Found!") must never be parsed as
        # an empty search page or scored as a weak match from stray links.
        html = (
            "<html><head><title>Page Not Found!</title></head><body>"
            '<a href="https://www.costco.com/.product.10024438.html"> </a>'
            "</body></html>"
        )
        out = parse_costco_search_page(
            html, "Kirkland Signature Dishwasher Detergent Pacs 115 Count"
        )
        self.assertEqual(out["status"], "lookup_page_not_found")
        self.assertEqual(out["candidates"], [])
        self.assertIsNone(out["best"])
        self.assertIn("Page Not Found", out["notes"])

    def test_search_url_default_and_override(self):
        self.assertIn(
            "costco.com/search",
            lookup._search_url("Kirkland Signature Coffee"),
        )
        self.assertIn(
            "query=",
            lookup._search_url("Kirkland Signature Coffee"),
        )
        with mock.patch.dict(
            os.environ,
            {"BRIGHTDATA_COSTCO_SEARCH_URL": "https://www.costco.com/search?keyword={query}"},
        ):
            url = lookup._search_url("Kirkland Signature Coffee K-Cup")
        self.assertIn("keyword=", url)
        self.assertIn("Kirkland%20Signature%20Coffee%20K-Cup", url)
        self.assertNotIn("query=", url)

    def test_search_url_override_is_honored_in_resolve(self):
        seen = {}

        def _f(url):
            seen["url"] = url
            return "<html><body>ok</body></html>"

        with mock.patch.dict(
            os.environ,
            {"BRIGHTDATA_COSTCO_SEARCH_URL": "https://www.costco.com/search?keyword={query}"},
        ):
            with mock.patch.object(bright_data_client, "_fetch", _f):
                resolve_by_search(
                    ["Kirkland Signature Coffee"], run_dir="tmp-probe", delay=0.0
                )
        self.assertIn("keyword=", seen["url"])


def setUpModule():
    os.environ[GATE_ENV] = "1"


def tearDownModule():
    os.environ.pop(GATE_ENV, None)
    bright_data_client.LAST_ERROR = None
    bright_data_client.LAST_HTTP_STATUS = None
    bright_data_client.LAST_RESPONSE_HEADERS = None


class GateTests(unittest.TestCase):
    def test_lookup_blocked_by_default_and_fails_closed(self):
        calls = []

        def _f(url):
            calls.append(url)
            return "<html/>"

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop(GATE_ENV, None)
            with mock.patch.object(bright_data_client, "_fetch", new=_f):
                summary = resolve_by_search(["Kirkland Signature Coffee"], "tmp")
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["items_requested"], 1)
        self.assertEqual(len(calls), 0)


class LivePathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_lookup_candidate_persists_evidence_and_resolves(self):
        html = _search_html(
            _anchor("44114", "Kirkland Signature Bath Tissue, 2-Ply, 380 Sheets, 30 Rolls",
                    slug="kirkland-signature-bath-tissue"),
        )
        calls = []

        def _f(url):
            calls.append(url)
            return html

        with mock.patch.object(bright_data_client, "_fetch", new=_f):
            summary = resolve_by_search(
                ["Kirkland Signature Bath Tissue, 2-Ply, 380 Sheets, 30 Individually Wrapped Rolls"],
                run_dir=self.tmp.name,
                delay=0.0,
            )
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_resolved"], 1)
        self.assertEqual(
            summary["items"][0]["identity_match_status"], "lookup_candidate"
        )
        self.assertEqual(summary["items"][0]["best_candidate"]["item_id"], "44114")
        self.assertEqual(len(calls), 1)

        # evidence files persisted (raw + normalized)
        files = os.listdir(os.path.join(self.tmp.name, "raw"))
        self.assertEqual(len(files), 1)
        with open(os.path.join(self.tmp.name, "raw", files[0]), encoding="utf-8") as fh:
            raw = json.load(fh)
        self.assertEqual(raw["auth_header"], "Bearer <redacted>")
        self.assertTrue(raw["scrubbed"])
        self.assertIn("response_headers", raw)
        self.assertIn("response_body_diagnostic", raw)
        self.assertNotIn("last_error", raw)  # clean_path has none

    def test_no_results_is_soft_failure_and_batch_continues(self):
        html_empty = "<html><body>no results</body></html>"
        html_ok = _search_html(
            _anchor("30055", "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Rolls",
                    slug="kirkland-signature-paper-towels"),
        )
        calls = {"n": 0}

        def _f(url):
            calls["n"] += 1
            return html_empty if calls["n"] == 1 else html_ok

        with mock.patch.object(bright_data_client, "_fetch", _f):
            summary = resolve_by_search(
                ["Kirkland Signature Coffee Organic Pacific Bold K-Cup Pod, 120-count",
                 "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Rolls"],
                run_dir=self.tmp.name,
                delay=0.0,
            )
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(len(summary["items"]), 2)
        self.assertEqual(
            summary["items"][0]["identity_match_status"], "lookup_no_results"
        )
        self.assertEqual(
            summary["items"][1]["identity_match_status"], "lookup_candidate"
        )

    def test_transport_error_halts_batch_circuit_breaker(self):
        html_ok = _search_html(
            _anchor("30055", "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Rolls",
                    slug="kirkland-signature-paper-towels"),
        )
        calls = {"n": 0}

        def _f(url):
            calls["n"] += 1
            if calls["n"] == 1:
                bright_data_client.LAST_HTTP_STATUS = None
                bright_data_client.LAST_ERROR = "transport_error: mocked down"
                return None
            return html_ok

        with mock.patch.object(bright_data_client, "_fetch", _f):
            summary = resolve_by_search(
                ["Kirkland Signature Coffee", "Kirkland Signature Paper Towels"],
                run_dir=self.tmp.name,
                delay=0.0,
            )
        self.assertEqual(summary["status"], "halted")
        self.assertEqual(len(summary["items"]), 0)
        self.assertEqual(len(summary["failures"]), 1)
        self.assertEqual(calls["n"], 1)  # zero retries
        self.assertEqual(summary["failures"][0]["failure_type"], "transport_error")
        # failure evidence persisted
        files = os.listdir(os.path.join(self.tmp.name, "raw"))
        self.assertEqual(len(files), 1)

    def test_page_not_found_is_soft_failure_keeps_going(self):
        html_404 = (
            "<html><head><title>Page Not Found!</title></head><body>"
            '<a href="/.product.10024438.html"> </a></body></html>'
        )
        html_ok = _search_html(
            _anchor("30055", "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Rolls",
                    slug="kirkland-signature-paper-towels"),
        )
        calls = {"n": 0}

        def _f(url):
            calls["n"] += 1
            return html_404 if calls["n"] == 1 else html_ok

        with mock.patch.object(bright_data_client, "_fetch", _f):
            summary = resolve_by_search(
                ["Kirkland Signature Coffee",
                 "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Individually Wrapped Rolls"],
                run_dir=self.tmp.name,
                delay=0.0,
            )
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(
            summary["items"][0]["identity_match_status"], "lookup_page_not_found"
        )
        self.assertEqual(
            summary["items"][1]["identity_match_status"], "lookup_candidate"
        )
        self.assertEqual(calls["n"], 2)  # soft failure did not halt batch

    def test_url_is_query_encoded_search_endpoint(self):
        seen = {}

        def _f(url):
            seen["url"] = url
            return _search_html()

        with mock.patch.object(bright_data_client, "_fetch", _f):
            resolve_by_search(["Kirkland Signature Coffee K-Cup Pod"], run_dir=self.tmp.name, delay=0.0)
        self.assertIn("costco.com/search", seen["url"])
        self.assertIn("query=", seen["url"])


class UnresolvedFromManifestTests(unittest.TestCase):
    def test_loads_unresolved_titles(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "prepared.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "items": [
                        {"requested_title": "A", "resolution": "unresolved_needs_lookup"},
                        {"requested_title": "B", "resolution": "resolved_catalog_exact"},
                    ]
                },
                fh,
            )
        rows = lookup._load_unresolved_titles(path)
        self.assertEqual([r["requested_title"] for r in rows], ["A"])

    def test_loads_pending_lookup_fallback_from_build_manifest(self):
        """build-manifest emits unresolved rows under pending_lookup (from the
        master capture CSV), not as items[] with a resolution flag — the
        --unresolved-from path must treat those as needing a live lookup."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "built.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "items": [
                        {"item_id": "424976", "requested_title": "Already Resolved"}
                    ],
                    "pending_lookup": [
                        {"asin": "B00U6I4YLM", "amazon_title": "Kirkland B-12 300 ct",
                         "reason": "no_costco_item_number"},
                        {"asin": "B00UP99X1I", "amazon_title": "Kirkland Vitamin E 500",
                         "reason": "no_costco_item_number"},
                    ],
                },
                fh,
            )
        rows = lookup._load_unresolved_titles(path)
        self.assertEqual(
            [r["requested_title"] for r in rows],
            ["Kirkland B-12 300 ct", "Kirkland Vitamin E 500"],
        )

    def test_cli_limit_caps_unresolved_expansion(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "prepared.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "items": [
                        {"requested_title": f"T{i}", "resolution": "unresolved_needs_lookup"}
                        for i in range(1, 6)
                    ]
                },
                fh,
            )
        seen = {}

        def fake_resolve(queries, run_dir=None, delay=None):
            seen["queries"] = queries
            seen["run_dir"] = run_dir
            return {
                "status": "completed",
                "items_requested": len(queries),
                "items_resolved": 0,
                "items": [],
                "failures": [],
            }

        with mock.patch.object(lookup, "resolve_by_search", side_effect=fake_resolve):
            rc = lookup._cli(
                ["resolve", "--unresolved-from", path, "--limit", "3",
                 "--run-dir", tmp.name]
            )
        self.assertEqual(rc, 0)
        self.assertEqual(seen["queries"], ["T1", "T2", "T3"])
        self.assertEqual(seen["run_dir"], tmp.name)

    def test_limit_never_caps_explicit_titles(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        seen = {}

        def fake_resolve(queries, run_dir=None, delay=None):
            seen["queries"] = queries
            return {
                "status": "completed",
                "items_requested": len(queries),
                "items_resolved": 0,
                "items": [],
                "failures": [],
            }

        with mock.patch.object(lookup, "resolve_by_search", side_effect=fake_resolve):
            rc = lookup._cli(
                ["resolve", "--title", "T7", "--limit", "0", "--run-dir", tmp.name]
            )
        self.assertEqual(rc, 0)
        self.assertEqual(seen["queries"], ["T7"])


if __name__ == "__main__":
    unittest.main()