"""Unit tests for the Bright Data Web Unlocker Costco parallel adapter.

Never makes live calls: _fetch is fully mocked and the parser runs against
the 6 real captured fixtures in fixtures/brightdata_costco/ (424976 is a
reconstructed fixture derived from operator-authorized probe evidence). Covers
the four baked-in design inputs:
  (1) typed url_not_found for content-level 404s with no fabricated fields
  (2) hyphen-tolerant pack/count token matching ("200-count" == "200 count")
  (3) price extraction from offers.price (dict OR list) with top-level fallback
  (4) item-number flat-URL lookup only (alternate slug/search deferred)
plus the env gate (fail-closed), the Batch 10 normalization contract
(null-first), hard-failure circuit breaker (halt), soft-failure continuation
(url_not_found does NOT halt a batch), zero retries, evidence persistence,
and CLI parsing.
"""

import json
import os
import tempfile
import unittest
from unittest import mock
from unittest.mock import patch

import test_network_guard  # noqa: F401  (blocks real network calls)

import bright_data_client
import bright_data_costco
from bright_data_costco import (
    _build_costco_url,
    _extract_count_pack,
    _identity_status,
    _is_url_not_found,
    _load_expected,
    _normalize_pack,
    _parse_jsonld_product,
    parse_costco_item_page,
    refresh_product_details,
)

GATE_ENV = bright_data_costco.GATE_ENV
FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), "fixtures", "brightdata_costco"
)

_fixture_cache = {}


def _fixture(item_id):
    if item_id not in _fixture_cache:
        path = os.path.join(FIXTURE_DIR, f"{item_id}.html")
        with open(path, "r", encoding="utf-8-sig") as fh:
            _fixture_cache[item_id] = fh.read()
    return _fixture_cache[item_id]


def _expected(item_id, title, pack):
    """Expected-identity dict in the frozen manifest's item shape."""
    return {
        "item_id": item_id,
        "requested_title": title,
        "requested_brand": "Kirkland Signature",
        "requested_pack": pack,
    }


def _mock_fetch(html, status=200, last_error=None, raise_err=None,
                last_headers=None):
    """A _fetch replacement that updates the live globals like the real one."""

    def _call(url):
        bright_data_client.LAST_HTTP_STATUS = status
        bright_data_client.LAST_ERROR = last_error
        bright_data_client.LAST_RESPONSE_HEADERS = last_headers
        if raise_err is not None:
            raise raise_err
        return html

    return _call


def setUpModule():
    """Live-path tests: opt into the adapter gate (fail-closed by default)."""
    os.environ[GATE_ENV] = "1"


def tearDownModule():
    os.environ.pop(GATE_ENV, None)
    # Never leak simulated transport state into later modules: the scanner /
    # amazon_search / product_analysis read bright_data_client.LAST_ERROR and
    # LAST_HTTP_STATUS to decide provider health.
    bright_data_client.LAST_ERROR = None
    bright_data_client.LAST_HTTP_STATUS = None
    bright_data_client.LAST_RESPONSE_HEADERS = None


# ---------------------------------------------------------------------------
# Parser: real fixtures
# ---------------------------------------------------------------------------
class ParserFixtureTests(unittest.TestCase):
    def test_parse_424976_reconstructed_supplement(self):
        item = parse_costco_item_page(
            _fixture("424976"),
            "424976",
            _expected("424976",
                      "Adult 50+ Mature Multi Vitamins & Minerals, 400 Tablets",
                      "400 Tablets"),
        )
        self.assertEqual(item["requested_item_id"], "424976")
        self.assertEqual(item["returned_costco_item_id"], "424976")
        self.assertEqual(
            item["exact_title"],
            "Kirkland Signature Adult 50+ Mature Multi Vitamins & Minerals, 400 Tablets",
        )
        self.assertEqual(item["brand"], "Kirkland Signature")
        self.assertEqual(item["listed_price"], 17.99)
        self.assertEqual(item["currency"], "USD")
        self.assertEqual(item["quantity_or_pack"], "400 tablets")
        self.assertEqual(item["product_url"], "https://www.costco.com/.product.424976.html")
        self.assertEqual(item["identity_match_status"], "probable_match")

    def test_parse_926628_fish_oil(self):
        item = parse_costco_item_page(
            _fixture("926628"),
            "926628",
            _expected("926628", "Fish Oil 1000 mg, 400 Softgels", "400 Softgels"),
        )
        self.assertEqual(
            item["exact_title"],
            "Kirkland Signature Fish Oil 1000 mg, 400 Softgels",
        )
        self.assertEqual(item["listed_price"], 20.99)
        self.assertEqual(item["quantity_or_pack"], "400 softgels")
        self.assertEqual(item["identity_match_status"], "probable_match")

    def test_parse_98501_vitamin_c(self):
        item = parse_costco_item_page(
            _fixture("98501"),
            "98501",
            _expected("98501", "Chewable Vitamin C 500 mg, 500 Tablets", "500 Tablets"),
        )
        self.assertEqual(item["listed_price"], 17.99)
        self.assertEqual(item["quantity_or_pack"], "500 tablets")
        self.assertEqual(item["identity_match_status"], "probable_match")

    def test_parse_690843_b12(self):
        item = parse_costco_item_page(
            _fixture("690843"),
            "690843",
            _expected("690843", "Quick Dissolve B-12 5000 mcg, 300 Tablets", "300 Tablets"),
        )
        self.assertEqual(item["listed_price"], 21.99)
        self.assertEqual(item["quantity_or_pack"], "300 tablets")
        self.assertEqual(item["identity_match_status"], "probable_match")

    def test_parse_1089787_hyphen_tolerant_pack(self):
        """Design input (2): '200-count' (hyphen) must normalize to '200 count'."""
        item = parse_costco_item_page(
            _fixture("1089787"),
            "1089787",
            _expected("1089787", "Flex-Tech 13-Gallon Kitchen Trash Bag, 200-count",
                      "200 count"),
        )
        self.assertEqual(
            item["exact_title"],
            "Kirkland Signature Flex-Tech 13-Gallon Kitchen Trash Bag, 200-count",
        )
        self.assertEqual(item["listed_price"], 22.49)
        self.assertEqual(item["quantity_or_pack"], "200 count")
        self.assertEqual(item["identity_match_status"], "probable_match")

    def test_parse_1493188_content_404_typed_url_not_found(self):
        """Design input (1): content-level 'Page Not Found!' -> url_not_found."""
        item = parse_costco_item_page(
            _fixture("1493188"),
            "1493188",
            _expected("1493188", "Baby Wipes Fragrance Free, 900-count",
                      "900-count (9x100ct)"),
        )
        self.assertEqual(item["requested_item_id"], "1493188")
        self.assertEqual(item["identity_match_status"], "url_not_found")
        self.assertEqual(item["product_url"], "https://www.costco.com/.product.1493188.html")

    def test_url_not_found_record_has_no_fabricated_fields(self):
        item = parse_costco_item_page(_fixture("1493188"), "1493188", None)
        for field in ("returned_costco_item_id", "exact_title", "brand",
                      "listed_price", "currency", "unit_price", "quantity_or_pack",
                      "size_or_weight", "UPC_GTIN_EAN", "availability"):
            self.assertIsNone(item[field], field)

    def test_missing_fields_null_first_contract(self):
        item = parse_costco_item_page(_fixture("926628"), "926628", None)
        self.assertEqual(
            item["missing_fields"],
            ["unit_price", "size_or_weight", "UPC_GTIN_EAN", "availability"],
        )
        for field in item["missing_fields"]:
            self.assertIsNone(item[field])


# ---------------------------------------------------------------------------
# Pack extraction (hyphen-tolerant)
# ---------------------------------------------------------------------------
class PackExtractionTests(unittest.TestCase):
    def test_hyphen_count(self):
        self.assertEqual(_extract_count_pack("Kitchen Trash Bag, 200-count"), "200 count")

    def test_space_count(self):
        self.assertEqual(_extract_count_pack("Kitchen Trash Bag, 200 count"), "200 count")

    def test_tablets_preserved_plural(self):
        self.assertEqual(_extract_count_pack("Multi Vitamins, 400 Tablets"), "400 tablets")

    def test_softgels(self):
        self.assertEqual(_extract_count_pack("Fish Oil, 400 Softgels"), "400 softgels")

    def test_no_count_returns_none(self):
        self.assertIsNone(_extract_count_pack("Kirkland Signature Adult 50+ Mature Multi"))
        self.assertIsNone(_extract_count_pack(""))
        self.assertIsNone(_extract_count_pack(None))

    def test_normalize_pack_ignores_punctuation(self):
        self.assertEqual(_normalize_pack("200-count"), _normalize_pack("200 count"))
        self.assertEqual(_normalize_pack("400 Tablets"), _normalize_pack("400 tablets"))


# ---------------------------------------------------------------------------
# Price extraction (offers dict / list / top-level fallback)
# ---------------------------------------------------------------------------
class PriceExtractionTests(unittest.TestCase):
    def _product_html(self, product_json):
        return (
            '<script type="application/ld+json">' + json.dumps(product_json)
            + "</script>"
        )

    def test_offers_dict_price(self):
        ld = _parse_jsonld_product(self._product_html({
            "@type": "Product",
            "name": "Kirkland Signature Test Item",
            "offers": {"@type": "Offer", "price": 17.99, "priceCurrency": "USD"},
        }))
        self.assertEqual(ld["price"], 17.99)

    def test_offers_list_price(self):
        ld = _parse_jsonld_product(self._product_html({
            "@type": "Product",
            "name": "Kirkland Signature Test Item",
            "offers": [
                {"@type": "Offer", "price": 21.99, "priceCurrency": "USD"},
                {"@type": "Offer", "price": 24.99, "priceCurrency": "USD"},
            ],
        }))
        self.assertEqual(ld["price"], 21.99)

    def test_top_level_price_fallback(self):
        ld = _parse_jsonld_product(self._product_html({
            "@type": "Product",
            "name": "Kirkland Signature Test Item",
            "price": 9.99,
        }))
        self.assertEqual(ld["price"], 9.99)

    def test_no_price_returns_none(self):
        ld = _parse_jsonld_product(self._product_html({
            "@type": "Product",
            "name": "Kirkland Signature Test Item",
        }))
        self.assertIsNone(ld["price"])

    def test_non_product_or_malformed_returns_none(self):
        self.assertIsNone(_parse_jsonld_product(
            '<script type="application/ld+json">{"@type":"BreadcrumbList"}</script>'
        ))
        self.assertIsNone(_parse_jsonld_product(
            '<script type="application/ld+json">not json</script>'
        ))
        self.assertIsNone(_parse_jsonld_product("<html><body>no scripts</body></html>"))

    def test_list_wrapper_product(self):
        ld = _parse_jsonld_product(self._product_html([
            {"@type": "Product", "name": "Kirkland Signature Test Item",
             "offers": {"price": 12.5}},
        ]))
        self.assertEqual(ld["price"], 12.5)


# ---------------------------------------------------------------------------
# URL-not-found detection
# ---------------------------------------------------------------------------
class UrlNotFoundTests(unittest.TestCase):
    def test_page_not_found_title(self):
        self.assertTrue(_is_url_not_found("<title>Page Not Found!</title>"))

    def test_normal_page_false(self):
        self.assertFalse(_is_url_not_found(
            "<html><head><title>Kirkland Signature Fish Oil 1000 mg, 400 Softgels | Costco</title></head></html>"
        ))

    def test_no_title_false(self):
        self.assertFalse(_is_url_not_found("<html><body>nothing</body></html>"))


# ---------------------------------------------------------------------------
# Identity matching
# ---------------------------------------------------------------------------
class IdentityMatchTests(unittest.TestCase):
    def test_probable_match(self):
        item = parse_costco_item_page(
            _fixture("926628"), "926628",
            _expected("926628", "Fish Oil 1000 mg, 400 Softgels", "400 Softgels"),
        )
        self.assertEqual(item["identity_match_status"], "probable_match")

    def test_unverified_without_expected(self):
        item = parse_costco_item_page(_fixture("926628"), "926628", None)
        self.assertEqual(item["identity_match_status"], "unverified")

    def test_url_not_found_beats_expected(self):
        item = parse_costco_item_page(
            _fixture("1493188"), "1493188",
            _expected("1493188", "Baby Wipes Fragrance Free, 900-count", "900-count (9x100ct)"),
        )
        self.assertEqual(item["identity_match_status"], "url_not_found")

    def test_identity_direct_function(self):
        self.assertEqual(
            _identity_status(
                "Kirkland Signature Fish Oil 1000 mg, 400 Softgels",
                "400 softgels",
                _expected("926628", "Fish Oil 1000 mg, 400 Softgels", "400 Softgels"),
            ),
            "probable_match",
        )
        self.assertEqual(_identity_status("Kirkland Signature Item", None, None), "unverified")


# ---------------------------------------------------------------------------
# Expected-identity loader (BOM-tolerant)
# ---------------------------------------------------------------------------
class ExpectedLoaderTests(unittest.TestCase):
    def test_loads_manifest_style_items(self):
        loaded = None
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "expected.json")
            data = {"items": [
                {"item_id": "926628",
                 "requested_title": "Fish Oil 1000 mg, 400 Softgels",
                 "requested_pack": "400 Softgels"},
                {"item_id": "98501", "requested_title": "Chewable Vitamin C 500 mg, 500 Tablets",
                 "requested_pack": "500 Tablets"},
            ]}
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\ufeff" + json.dumps(data))
            loaded = _load_expected(path)
        self.assertEqual(loaded["926628"]["requested_pack"], "400 Softgels")
        self.assertEqual(loaded["98501"]["requested_title"],
                         "Chewable Vitamin C 500 mg, 500 Tablets")

    def test_missing_file_raises(self):
        with self.assertRaises(OSError):
            _load_expected(os.path.join(tempfile.gettempdir(), "nope-expected.json"))


# ---------------------------------------------------------------------------
# URL builder
# ---------------------------------------------------------------------------
class UrlBuilderTests(unittest.TestCase):
    def test_flat_item_number_url(self):
        self.assertEqual(
            _build_costco_url("424976"),
            "https://www.costco.com/.product.424976.html",
        )


# ---------------------------------------------------------------------------
# Gate (fail-closed)
# ---------------------------------------------------------------------------
class GateTests(unittest.TestCase):
    def _run_with_gate(self, value=None, unset=False):
        summary = None
        with mock.patch.dict(os.environ, {}, clear=False):
            if unset:
                os.environ.pop(GATE_ENV, None)
            elif value is not None:
                os.environ[GATE_ENV] = value
            summary = refresh_product_details(["424976"], delay=0)
        return summary

    def test_gate_disabled_blocks(self):
        summary = self._run_with_gate(value="0")
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["items_requested"], 1)
        self.assertEqual(summary["items_fetched"], 0)

    def test_gate_custom_value_blocks(self):
        for bad in ("true", "TRUE", "yes", "on", "2"):
            summary = self._run_with_gate(value=bad)
            self.assertEqual(summary["status"], "blocked", bad)

    def test_gate_unset_defaults_blocked(self):
        summary = self._run_with_gate(unset=True)
        self.assertEqual(summary["status"], "blocked")

    def test_gate_enabled_runs_with_mocked_fetch(self):
        with patch.object(
            bright_data_client,
            "_fetch",
            new=_mock_fetch(_fixture("926628"), 200, None),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(["926628"], run_dir=tmp, delay=0)
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_fetched"], 1)


# ---------------------------------------------------------------------------
# Refresh flow (mocked transport)
# ---------------------------------------------------------------------------
class RefreshFlowTests(unittest.TestCase):
    def test_multi_item_success_and_evidence(self):
        with patch.object(
            bright_data_client,
            "_fetch",
            new=_mock_fetch(_fixture("926628"), 200, None),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(
                    ["926628", "98501"], run_dir=tmp, delay=0
                )
                self.assertEqual(len(summary["evidence_paths"]), 4)
                for path in summary["evidence_paths"]:
                    self.assertTrue(os.path.exists(path), path)
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_requested"], 2)
        self.assertEqual(summary["items_fetched"], 2)
        self.assertEqual(summary["items_failed"], 0)
        self.assertEqual(summary["items_soft_failed"], 0)
        for item in summary["items"]:
            self.assertEqual(item["identity_match_status"], "unverified")
            self.assertEqual(item["requested_item_id"] in ("926628", "98501"), True)

    def test_transport_error_halts_batch_circuit_breaker(self):
        calls = []

        def flaky(url):
            calls.append(url)
            if len(calls) == 1:
                bright_data_client.LAST_HTTP_STATUS = None
                bright_data_client.LAST_ERROR = "transport_error: mocked down"
                return None
            return _fixture("98501")

        with patch.object(bright_data_client, "_fetch", new=flaky):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(["926628", "98501"], run_dir=tmp, delay=0)
        self.assertEqual(summary["status"], "halted")
        self.assertEqual(len(calls), 1, "second item must NOT be fetched after a halt")
        self.assertEqual(summary["items_fetched"], 0)
        self.assertEqual(summary["items_failed"], 1)
        self.assertEqual(summary["failures"][0]["failure_type"], "transport_error")
        self.assertEqual(summary["failures"][0]["http_status"], 0)

    def test_auth_error_halts_batch_with_status(self):
        with patch.object(
            bright_data_client,
            "_fetch",
            new=_mock_fetch(None, status=403, last_error="auth_error: HTTP 403"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(["424976"], run_dir=tmp, delay=0)
        self.assertEqual(summary["status"], "halted")
        self.assertEqual(summary["failures"][0]["failure_type"], "auth_error")
        self.assertEqual(summary["failures"][0]["http_status"], 403)

    def test_http_error_halts_batch_with_status(self):
        with patch.object(
            bright_data_client,
            "_fetch",
            new=_mock_fetch(None, status=429, last_error="http_error: HTTP 429"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(["424976"], run_dir=tmp, delay=0)
        self.assertEqual(summary["status"], "halted")
        self.assertEqual(summary["failures"][0]["failure_type"], "http_error")
        self.assertEqual(summary["failures"][0]["http_status"], 429)

    def test_config_error_halts_batch(self):
        with patch.object(
            bright_data_client,
            "_fetch",
            new=_mock_fetch(
                None, status=None, last_error=None,
                raise_err=ValueError("BRIGHTDATA_UNLOCKER_API_KEY not set"),
            ),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(["424976"], run_dir=tmp, delay=0)
        self.assertEqual(summary["status"], "halted")
        self.assertEqual(summary["failures"][0]["failure_type"], "config_error")

    def test_url_not_found_is_soft_failure_batch_continues(self):
        """1493188 (content-404) must NOT halt; later items still processed."""
        def route(url):
            if url.endswith("1493188.html"):
                bright_data_client.LAST_HTTP_STATUS = 200
                bright_data_client.LAST_ERROR = None
                return _fixture("1493188")
            bright_data_client.LAST_HTTP_STATUS = 200
            bright_data_client.LAST_ERROR = None
            return _fixture("926628")

        with patch.object(bright_data_client, "_fetch", new=route):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(
                    ["1493188", "926628"], run_dir=tmp, delay=0
                )
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_fetched"], 2)
        self.assertEqual(summary["items_soft_failed"], 1)
        self.assertEqual(summary["items_failed"], 0)
        statuses = [it["identity_match_status"] for it in summary["items"]]
        self.assertIn("url_not_found", statuses)
        self.assertIn("unverified", statuses)

    def test_pacing_delay_applied_between_items(self):
        with patch.object(
            bright_data_client,
            "_fetch",
            new=_mock_fetch(_fixture("926628"), 200, None),
        ), patch.object(bright_data_costco.time, "sleep") as sleep_mock:
            with tempfile.TemporaryDirectory() as tmp:
                refresh_product_details(["926628", "98501"], run_dir=tmp, delay=2.0)
        sleep_mock.assert_called_once_with(2.0)

    def test_zero_retries_no_repeat_after_failure(self):
        with patch.object(
            bright_data_client,
            "_fetch",
            new=_mock_fetch(None, status=403, last_error="auth_error: HTTP 403"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(["424976"], run_dir=tmp, delay=0)
        self.assertEqual(summary["failures"][0]["retries"], 0)


# ---------------------------------------------------------------------------
# Persistence: scrubbed evidence
# ---------------------------------------------------------------------------
class PersistenceTests(unittest.TestCase):
    def test_evidence_scrubbed_no_auth_header_leak(self):
        with patch.object(
            bright_data_client,
            "_fetch",
            new=_mock_fetch(_fixture("98501"), 200, None),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(["98501"], run_dir=tmp, delay=0)
                raw_path = [p for p in summary["evidence_paths"] if "raw" in p][0]
                norm_path = [p for p in summary["evidence_paths"] if "normalized" in p][0]
                with open(raw_path, encoding="utf-8") as fh:
                    raw = json.load(fh)
                with open(norm_path, encoding="utf-8") as fh:
                    norm = json.load(fh)
                self.assertEqual(raw["auth_header"], "Bearer <redacted>")
                self.assertEqual(raw["http_status"], 200)
                self.assertEqual(raw["scrubbed"], True)
                self.assertEqual(norm["item"]["exact_title"],
                                 "Kirkland Signature Chewable Vitamin C 500 mg., 500 Tablets")
                self.assertEqual(norm["item"]["listed_price"], 17.99)


# ---------------------------------------------------------------------------
# Empty-body diagnostics (fixture-backed from live run 20260906T015531Z)
# ---------------------------------------------------------------------------
class EmptyBodyDiagnosticTests(unittest.TestCase):
    """Live run 20260906T015531Z returned HTTP 200 with a ZERO-BYTE body for
    98501 and 1493188 (raw evidence recorded response_html_head_capped: "").
    The parser must keep emitting a null-first no_data_found record, and raw
    evidence must now carry body-bytes + a diagnostic (empty | short | normal)
    + a scrubbed header snapshot so blocked vs genuinely-absent is
    distinguish-able instead of just 'zero bytes'.

    The empty fixture mirror (empty_body_98501_1493188_20260906T015531Z.html)
    is intentionally a zero-byte file — that is exactly what the unlocker
    delivered; the short fixture mimics an anti-bot/consent interstitial.
    """

    def _run(self, html, last_headers=None, item_ids=("98501",), status=200):
        with patch.object(
            bright_data_client,
            "_fetch",
            new=_mock_fetch(html, status=status, last_error=None,
                            last_headers=last_headers),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                summary = refresh_product_details(
                    list(item_ids), run_dir=tmp, delay=0
                )
                raw_path = [p for p in summary["evidence_paths"] if "raw" in p][0]
                norm_path = [p for p in summary["evidence_paths"]
                             if "normalized" in p][0]
                with open(raw_path, encoding="utf-8") as fh:
                    raw = json.load(fh)
                with open(norm_path, encoding="utf-8") as fh:
                    norm = json.load(fh)
        return summary, raw, norm

    def test_empty_body_stays_no_data_found_null_first(self):
        """The 98501/1493188 empty-body capture must NOT fabricate anything."""
        summary, raw, norm = self._run(
            _fixture("empty_body_98501_1493188_20260906T015531Z")
        )
        self.assertEqual(summary["status"], "completed")
        item = norm["item"]
        self.assertEqual(item["identity_match_status"], "no_data_found")
        for field in ("returned_costco_item_id", "exact_title", "brand",
                      "listed_price", "currency", "unit_price",
                      "quantity_or_pack", "size_or_weight", "UPC_GTIN_EAN",
                      "availability"):
            self.assertIsNone(item[field], field)

    def test_empty_body_raw_evidence_diagnostic_fields(self):
        summary, raw, norm = self._run(
            _fixture("empty_body_98501_1493188_20260906T015531Z")
        )
        self.assertEqual(raw["http_status"], 200)
        self.assertEqual(raw["response_html_head_capped"], "")
        self.assertEqual(raw["response_body_bytes"], 0)
        self.assertEqual(raw["response_body_diagnostic"], "empty")
        self.assertEqual(raw["scrubbed"], True)
        self.assertIsNone(raw["response_headers"])

    def test_empty_body_evidence_shape_matches_live_run(self):
        """Same shape/facts as raw/brightdata_1493188_20260906T015531Z.json
        (http 200, zero-byte body) — now with the diagnosable fields added."""
        summary, raw, norm = self._run(
            _fixture("empty_body_98501_1493188_20260906T015531Z")
        )
        self.assertEqual(raw["run_id"], bright_data_costco.RUN_ID)
        self.assertEqual(raw["http_status"], 200)
        self.assertEqual(raw["response_html_head_capped"], "")
        self.assertEqual(raw["response_body_bytes"], 0)
        self.assertEqual(raw["response_body_diagnostic"], "empty")
        self.assertEqual(raw["auth_header"], "Bearer <redacted>")

    def test_response_headers_captured_from_transport_scrubbed(self):
        """set-cookie must never survive into evidence."""
        headers = {
            "content-type": "text/html",
            "content-length": "0",
            "set-cookie": "sessionid=secret",
        }
        summary, raw, norm = self._run(
            _fixture("empty_body_98501_1493188_20260906T015531Z"),
            last_headers=headers,
        )
        self.assertEqual(
            raw["response_headers"],
            {"content-type": "text/html", "content-length": "0"},
        )

    def test_short_body_blocked_like_head_excerpt_persisted(self):
        """A short interstitial must keep its full head excerpt so an operator
        can tell 'blocked/challenged' from genuinely-absent content."""
        body = _fixture("short_body_blocked_like")
        self.assertTrue(0 < len(body) < bright_data_costco.SHORT_BODY_CHARS)
        summary, raw, norm = self._run(body)
        item = norm["item"]
        self.assertEqual(item["identity_match_status"], "no_data_found")
        self.assertEqual(raw["response_body_diagnostic"], "short")
        self.assertEqual(raw["response_html_head_capped"], body)
        self.assertEqual(raw["response_body_bytes"], len(body.encode("utf-8")))

    def test_normal_body_diagnostic_normal(self):
        summary, raw, norm = self._run(_fixture("926628"))
        self.assertEqual(raw["response_body_diagnostic"], "normal")
        html = _fixture("926628")
        self.assertEqual(raw["response_body_bytes"], len(html.encode("utf-8")))
        self.assertEqual(raw["response_html_head_capped"],
                         html[:bright_data_costco.HEAD_CAP_CHARS])

    def test_empty_body_is_soft_failure_batch_continues(self):
        def route(url):
            bright_data_client.LAST_HTTP_STATUS = 200
            bright_data_client.LAST_ERROR = None
            bright_data_client.LAST_RESPONSE_HEADERS = None
            if url.endswith("98501.html"):
                return _fixture("empty_body_98501_1493188_20260906T015531Z")
            return _fixture("926628")

        with patch.object(bright_data_client, "_fetch", new=route), \
             tempfile.TemporaryDirectory() as tmp:
            summary = refresh_product_details(
                ["98501", "926628"], run_dir=tmp, delay=0
            )
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_fetched"], 2)
        self.assertEqual(summary["items_soft_failed"], 1)
        self.assertEqual(summary["items_failed"], 0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
class CliTests(unittest.TestCase):
    def test_cli_gate_blocked_returns_2(self):
        with mock.patch.dict(os.environ, {GATE_ENV: "0"}, clear=False):
            code = bright_data_costco._cli(["details", "refresh", "--item-ids", "424976"])
        self.assertEqual(code, 2)

    def test_cli_requires_item_ids(self):
        with self.assertRaises(SystemExit):
            bright_data_costco._cli(["details", "refresh"])

    def test_cli_unknown_subcommand_rejected(self):
        with self.assertRaises(SystemExit):
            bright_data_costco._cli(["details", "podcast"])

    def test_cli_refresh_success_returns_0(self):
        canned = {
            "status": "completed",
            "provider": "BRIGHTDATA_WEB_UNLOCKER",
            "run_id": "20260828T021658Z",
            "items_requested": 1,
            "items_fetched": 1,
            "items_failed": 0,
            "items": [{"requested_item_id": "424976"}],
            "failures": [],
            "evidence_paths": [],
        }
        with patch.object(bright_data_costco, "_gate_enabled", return_value=True), \
             patch.object(bright_data_costco, "refresh_product_details",
                          return_value=canned) as mock_refresh:
            code = bright_data_costco._cli(
                ["details", "refresh", "--item-ids", "424976",
                 "--expected-json", "manifest.json", "--delay", "2.5"]
            )
        self.assertEqual(code, 0)
        _, kwargs = mock_refresh.call_args
        self.assertEqual(kwargs["item_ids"], ["424976"])
        self.assertEqual(kwargs["manifest_path"], "manifest.json")
        self.assertEqual(kwargs["delay"], 2.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)