"""Scanner completeness contract tests (null-first semantics).

Scope (per the implementation report):
  - absent completeness data -> null score + not_computable status
    (nothing evaluated); the server never fabricates a score
  - partial row -> a real partial score only when canonical inputs
    support it (score_max < 100, null categories stay null)
  - genuine-zero scenario -> explicitly constructed and tested separately
  - backward compatibility: existing scanner keys keep exact values; the
    contract is additive only
  - containment: GET scanner/live routes, debug mode, and static routes
    make zero provider calls (all outbound clients patched to raise)
"""

import os
import tempfile
import unittest
from unittest.mock import patch

import amazon_search
import bright_data_client
import canopy_client
import costco_api_client
import completeness_score
import easyparser_client
import main
import offer_enrichment
import scavio_client

_TMP = os.path.join(tempfile.gettempdir(), "opencode", "scanner-completeness-tests")
os.makedirs(_TMP, exist_ok=True)


def _worst_case_env():
    return {
        "SCANNER_LIVE_ALLOWED": "0",
        "SCANNER_SEARCH_SOURCE": "BRIGHTDATA",
        "SCANNER_SEARCH_FALLBACK": "SCAVIO",
        "SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA",
        "SCANNER_LOCAL_SNAPSHOT_MERGE": "0",
        "SCANNER_SEARCH_CACHE_PATH": os.path.join(_TMP, "search-cache.json"),
        "SCANNER_OFFER_CACHE_PATH": os.path.join(_TMP, "offer-cache.json"),
        "SCANNER_SELLER_CACHE_PATH": os.path.join(_TMP, "seller-cache.json"),
        "SCANNER_ENRICH_RUN_REPORT_PATH": os.path.join(_TMP, "enrich-report.json"),
        "SCANNER_MARKET_SNAPSHOT_PATH": os.path.join(_TMP, "snapshots.json"),
        "COSTCO_CSV_PATH": os.path.join(_TMP, "costco-items.csv"),
    }


def _boom(*args, **kwargs):
    raise AssertionError("provider call leaked")


def _provider_patches():
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


# --- fixture rows -----------------------------------------------------------

PARTIAL_ROW = {
    "name": "Kirkland Signature Example Product",
    "asin": "B0PLACEH01",
    "amazon_price": 24.99,
    "costco_cost": 12.99,
    "costco_cost_basis": "estimated",
    "referral_fee": 1.95,
    "fba_fee": 4.75,
    "fba_fee_status": "estimated",
    "economics_confidence": "estimated",
    "net_profit": 2.54,
    "roi_pct": 19.5,
    "monthly_sales_estimate": None,
    "sales_estimation_method": None,
    "economics_status": "estimated_fee_stack",
}

GENUINE_ZERO_ROW = {
    "name": None,
    "asin": "B0PLACEH02",
    "pack_match": "mismatch",
    "amazon_price": None,
    "costco_cost": None,
    "costco_cost_basis": "unavailable",
    "observed_buy_box_available": False,
    "economics_confidence": "unavailable",
    "monthly_sales_estimate": None,
    "sales_estimation_method": "unknown",
    "economics_status": "unavailable",
}

EMPTY_ROW = {"asin": "B0PLACEH03"}

CONTRACT_KEYS = (
    "score",
    "score_max",
    "status",
    "status_reason",
    "category_scores",
    "category_reasons",
    "missing_inputs",
    "roi_readiness",
    "next_action",
    "purchase_authorized",
)


class ScannerContractTests(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, _worst_case_env(), clear=True)
        self._env.start()
        self._analysis = patch.object(
            main,
            "analyze_kirkland_products",
            return_value={"all_results": [PARTIAL_ROW, GENUINE_ZERO_ROW, EMPTY_ROW], "tier_found": None},
        )
        self._analysis.start()
        amazon_search.LAST_SEARCH_ERROR = None

    def tearDown(self):
        self._analysis.stop()
        self._env.stop()

    def test_response_carries_contract_and_version(self):
        body = main.get_kirkland_scanner()
        self.assertEqual(body["summary"]["completeness_contract_version"], 1)
        self.assertEqual(len(body["products"]), 3)
        for p in body["products"]:
            self.assertIn("completeness", p)
            for key in CONTRACT_KEYS:
                self.assertIn(key, p["completeness"])

    def test_absent_data_null_score_not_computable(self):
        body = main.get_kirkland_scanner()
        empty = next(p for p in body["products"] if p["asin"] == "B0PLACEH03")
        comp = empty["completeness"]
        self.assertIsNone(comp["score"])
        self.assertEqual(comp["status"], "not_computable")
        self.assertEqual(comp["score_max"], 0)
        for cat, value in comp["category_scores"].items():
            self.assertIsNone(value)
        self.assertFalse(comp["purchase_authorized"])

    def test_partial_row_real_partial_score(self):
        body = main.get_kirkland_scanner()
        partial = next(p for p in body["products"] if p["asin"] == "B0PLACEH01")
        comp = partial["completeness"]
        self.assertIsNotNone(comp["score"])
        self.assertGreater(comp["score"], 0)
        self.assertLess(comp["score_max"], 100)
        self.assertIsNone(comp["category_scores"]["demand"])
        self.assertIn("demand", comp["missing_inputs"])
        self.assertEqual(comp["status"], "needs_mapping")
        self.assertFalse(comp["purchase_authorized"])

    def test_genuine_zero_separately_proven(self):
        body = main.get_kirkland_scanner()
        zero = next(p for p in body["products"] if p["asin"] == "B0PLACEH02")
        comp = zero["completeness"]
        self.assertEqual(comp["score"], 0)
        self.assertEqual(comp["score_max"], 100)
        self.assertNotEqual(comp["status"], "not_computable")
        self.assertEqual(comp["status"], "blocked")
        self.assertFalse(comp["purchase_authorized"])

    def test_server_matches_canonical_logic(self):
        for row in (PARTIAL_ROW, GENUINE_ZERO_ROW, EMPTY_ROW):
            expected = completeness_score.compute_scanner_completeness(row)
            body = main.get_kirkland_scanner()
            p = next(x for x in body["products"] if x["asin"] == row["asin"])
            self.assertEqual(p["completeness"], expected)

    def test_backward_compatible_existing_keys_unchanged(self):
        body = main.get_kirkland_scanner()
        partial = next(p for p in body["products"] if p["asin"] == "B0PLACEH01")
        for key in ("name", "asin", "amazon_price", "costco_cost", "net_profit", "roi_pct"):
            self.assertEqual(partial[key], PARTIAL_ROW[key])
        self.assertEqual(set(partial.keys()) & set(main.SCANNER_ALLOWED_KEYS), set(partial.keys()))
        self.assertIn("completeness", partial)


class ContainmentReassertTests(unittest.TestCase):
    """GET routes, debug mode, and static routes stay cache-only."""

    def setUp(self):
        self._env = patch.dict(os.environ, _worst_case_env(), clear=True)
        self._env.start()
        self._patches = _provider_patches()
        for p in self._patches:
            p.start()
        amazon_search.LAST_SEARCH_ERROR = None

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._env.stop()

    def test_scanner_get_zero_provider_calls(self):
        body = main.get_kirkland_scanner()
        self.assertFalse(body["summary"]["live_allowed"])
        self.assertEqual(body["summary"]["scanner_mode"], "cache_only")

    def test_live_get_zero_provider_calls(self):
        body = main.get_kirkland_live()
        self.assertIsNotNone(body)

    def test_root_debug_zero_provider_calls(self):
        resp = main.serve_scout()
        self.assertTrue(os.path.basename(resp.path) == "index.html")
        with open(resp.path, "r", encoding="utf-8") as f:
            html = f.read()
        # Root now serves the landing page (unified design system)
        self.assertIn("Northstar", html)
        self.assertIn("Northstar OS", html)

    def test_static_asset_lookup_offline(self):
        static_mounts = [
            r for r in main.app.routes if getattr(r, "path", None) == "/static"
        ]
        self.assertEqual(len(static_mounts), 1)
        mount = static_mounts[0]
        path, stat = mount.app.lookup_path("index.html")
        self.assertTrue(path.endswith("index.html"))
        self.assertIsNotNone(stat)


if __name__ == "__main__":
    unittest.main()