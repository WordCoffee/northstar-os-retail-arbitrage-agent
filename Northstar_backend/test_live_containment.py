"""Live-call containment tests (offline, zero network).

Proves the default-off SCANNER_LIVE_ALLOWED gate: every path a browser
page load can reach — GET /, GET /?ui_debug=1, GET /health,
GET /api/kirkland/scanner, GET /api/kirkland/live, static assets, and
the on-demand GET product routes — makes ZERO provider calls when the
gate is off, even with the most permissive provider env forced on
(SCANNER_OFFER_ENRICHMENT=BRIGHTDATA, SCANNER_SEARCH_SOURCE=BRIGHTDATA,
SCANNER_SEARCH_FALLBACK=SCAVIO, PAGES_TO_SEARCH=10).

Every outbound provider client is patched to raise AssertionError, so
any regression in the gate fails loudly instead of hitting the network.
Caches are pointed at a temp dir; production data files are never
touched. The explicit live refresh path is only asserted to be refused
(403) while the gate is off — it is never executed.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import json
import os
import tempfile
import unittest
from unittest import mock
from unittest.mock import patch

import amazon_search
import bright_data_client
import canopy_client
import costco_api_client
import easyparser_client
import main
import offer_enrichment
import product_analysis
import scavio_client
import live_gate

_TMP = tempfile.mkdtemp(prefix="live-containment-")

_PROVIDER_CALLED = AssertionError("a live provider client was called")


def _boom(*args, **kwargs):
    raise _PROVIDER_CALLED


def _worst_case_env():
    """Most permissive provider env, with the live gate forced OFF."""
    return {
        "SCANNER_LIVE_ALLOWED": "0",
        "SCANNER_SEARCH_SOURCE": "BRIGHTDATA",
        "SCANNER_SEARCH_FALLBACK": "SCAVIO",
        "SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA",
        "SCANNER_LOCAL_SNAPSHOT_MERGE": "0",
        "PAGES_TO_SEARCH": "10",
        "SEARCH_KEYWORDS": "kirkland",
        "SCANNER_SEARCH_CACHE_PATH": os.path.join(_TMP, "search-cache.json"),
        "SCANNER_OFFER_CACHE_PATH": os.path.join(_TMP, "offer-cache.json"),
        "SCANNER_SELLER_CACHE_PATH": os.path.join(_TMP, "seller-cache.json"),
        "SCANNER_ENRICH_RUN_REPORT_PATH": os.path.join(_TMP, "enrich-report.json"),
        "COSTCO_CATALOG_SOURCE": "OFF",
    }


def _provider_patches():
    """Every outbound provider entry point the web app can reach."""
    return [
        patch.object(bright_data_client, "search_products", side_effect=_boom),
        patch.object(bright_data_client, "get_product_detail", side_effect=_boom),
        patch.object(scavio_client, "search_kirkland_products", side_effect=_boom),
        patch.object(amazon_search, "_search_brightdata", side_effect=_boom),
        patch.object(amazon_search, "_search_chocodata", side_effect=_boom),
        patch.object(offer_enrichment, "get_easyparser_offers", side_effect=_boom),
        patch.object(offer_enrichment, "get_product_detail", side_effect=_boom),
        patch.object(offer_enrichment, "enrich_product", side_effect=_boom),
        patch.object(offer_enrichment, "get_offer_data", side_effect=_boom),
        patch.object(canopy_client.requests, "get", side_effect=_boom),
        patch.object(costco_api_client.requests, "get", side_effect=_boom),
        patch.object(easyparser_client.requests, "get", side_effect=_boom),
    ]


class LiveContainmentTests(unittest.TestCase):
    """Gate OFF (default): zero provider calls from every GET/UI/static path."""

    def setUp(self):
        self._env = patch.dict(os.environ, _worst_case_env(), clear=True)
        self._env.start()
        self._patches = _provider_patches()
        for p in self._patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in reversed(self._patches):
            p.stop()
        self._env.stop()

    def assert_zero_provider_calls(self):
        for p in self._patches:
            m = p.target if hasattr(p.target, "side_effect") else None
            if m is not None:
                m.assert_not_called()

    # --- browser page load: GET / and GET /?ui_debug=1 ---

    def test_root_serves_ui_with_zero_provider_calls(self):
        resp = main.serve_scout()
        self.assertTrue(os.path.basename(resp.path) == "index.html")
        with open(resp.path, "r", encoding="utf-8") as f:
            html = f.read()
        # Root now serves the landing page (unified design)
        self.assertIn("Northstar", html)
        self.assertIn("Northstar OS", html)
        self.assert_zero_provider_calls()

    def test_root_ui_debug_serves_ui_with_zero_provider_calls(self):
        resp = main.serve_scout()
        self.assertTrue(os.path.basename(resp.path) == "index.html")
        self.assert_zero_provider_calls()

    # --- the exact endpoint the UI fetches on page load ---

    def test_scanner_endpoint_zero_provider_calls(self):
        body = main.get_kirkland_scanner()
        self.assertEqual(body["summary"]["live_allowed"], False)
        self.assertEqual(body["summary"]["scanner_mode"], "cache_only")
        self.assertEqual(body["status"], "no_candidates")
        self.assert_zero_provider_calls()

    # --- health and static assets ---

    def test_health_zero_provider_calls(self):
        result = main.health()
        self.assertEqual(result["status"], "ok")
        self.assert_zero_provider_calls()

    def test_static_mount_serves_disk_only_zero_provider_calls(self):
        static_mounts = [
            r for r in main.app.routes if getattr(r, "path", None) == "/static"
        ]
        self.assertEqual(len(static_mounts), 1)
        mount = static_mounts[0]
        self.assertEqual(mount.app.directory, str(main.STATIC_DIR))
        path, stat = mount.app.lookup_path("index.html")
        self.assertTrue(stat is not None)
        self.assertTrue(os.path.isfile(path))
        self.assert_zero_provider_calls()

    # --- other GET routes ---

    def test_live_route_zero_provider_calls_when_gate_off(self):
        analysis = main.get_kirkland_live()
        self.assertIn("all_results", analysis)
        self.assert_zero_provider_calls()

    def test_canopy_route_zero_provider_calls_when_gate_off(self):
        payload = main.get_product_canopy("B0TEST0001")
        self.assertEqual(payload["enrichment_source"], "canopy")
        self.assertEqual(payload["amazon_price"], None)
        self.assertTrue(
            any("disabled" in g for g in payload["data_gaps"]),
            payload["data_gaps"],
        )
        self.assert_zero_provider_calls()

    def test_offers_route_zero_provider_calls_when_gate_off(self):
        payload = main.get_product_offers("B00GYZWNY6")
        self.assertEqual(payload["offer_data_status"], "unavailable")
        self.assertTrue("disabled" in (payload.get("offer_data_note") or ""))
        self.assert_zero_provider_calls()

    # --- explicit refresh is refused while the gate is off ---

    def test_refresh_post_refused_when_gate_off(self):
        with self.assertRaises(Exception) as ctx:
            main.refresh_kirkland_scan()
        self.assertEqual(getattr(ctx.exception, "status_code", None), 403)
        self.assert_zero_provider_calls()

    # --- direct module-level boundaries ---

    def test_search_function_returns_empty_when_gate_off(self):
        self.assertEqual(amazon_search.search_kirkland_products(["kirkland"], 10), [])
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)
        self.assert_zero_provider_calls()

    def test_enrichment_mode_forced_off_when_gate_off(self):
        self.assertEqual(offer_enrichment._enrichment_mode(), "OFF")
        self.assert_zero_provider_calls()

    def test_canopy_client_offline_shape_when_gate_off(self):
        result = canopy_client.get_canopy_product("B0TEST0001")
        self.assertIsNone(result["amazon_price"])
        self.assertTrue(
            any("disabled" in g for g in result["data_gaps"]), result["data_gaps"]
        )
        self.assert_zero_provider_calls()


class LiveGateOptInTests(unittest.TestCase):
    """Gate ON (explicit opt-in): the live path is reachable but only
    through the named refresh endpoint / direct provider calls. All
    providers stay patched, so nothing touches the network."""

    def setUp(self):
        env = _worst_case_env()
        env["SCANNER_LIVE_ALLOWED"] = "1"
        self._env = patch.dict(os.environ, env, clear=True)
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_gate_flips_with_explicit_opt_in(self):
        self.assertTrue(live_gate.live_enabled())

    def test_enrichment_mode_respects_opt_in(self):
        self.assertEqual(offer_enrichment._enrichment_mode(), "BRIGHTDATA")

    def test_search_dispatches_when_opt_in(self):
        candidate = {"asin": "B0TEST0001", "name": "Kirkland K-Cups", "amazon_price": 48.87}
        with patch.object(bright_data_client, "search_products", return_value=[candidate]):
            got = amazon_search.search_kirkland_products(["kirkland"], 1)
        self.assertEqual([c["asin"] for c in got], ["B0TEST0001"])
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)


class LiveGateDisabledValuesTests(unittest.TestCase):
    """Every non-opt-in value keeps the gate off (env_flag semantics)."""

    def test_non_opt_in_values_are_off(self):
        for value in ("", "0", "false", "no", "off", "OFF", "garbage", "0x1"):
            with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": value}, clear=False):
                self.assertFalse(live_gate.live_enabled(), value)

    def test_opt_in_values_are_on(self):
        for value in ("1", "true", "TRUE", "True", "yes", "on", " YES "):
            with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": value}, clear=False):
                self.assertTrue(live_gate.live_enabled(), value)


if __name__ == "__main__":
    unittest.main()