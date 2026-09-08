"""Unit tests for the Firecrawl Costco parallel adapter (free-tier redundancy).

Never makes live calls: requests.post is fully mocked and the parser runs
against the real Bright Data fixtures (the parser is shared). Covers the
adapter's contract:
  (1) env gate fail-closed (FIRECRAWL_COSTCO_DETAIL_ENABLED default 0)
  (2) shared parser + normalized contract (byte-compatible evidence)
  (3) typed hard-failure HALT for config/auth/http/transport/rate_limited/
      credits_exhausted/malformed_response
  (4) HTTP 402 -> credits_exhausted (free allowance spent), never auth
  (5) SOFT failures (url_not_found / no_data_found) continue the batch
  (6) zero retries, scrubbed evidence (no API key), per-item persistence
"""

import json
import os
import tempfile
import unittest
from unittest import mock

import test_network_guard  # noqa: F401  (blocks real network calls)

import firecrawl_costco
from firecrawl_costco import (
    _classify_hard_failure,
    _fetch_item_page,
    _gate_enabled,
    refresh_product_details,
)

GATE_ENV = firecrawl_costco.GATE_ENV
KEY_ENV = firecrawl_costco.KEY_ENV
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
    return {
        "item_id": item_id,
        "requested_title": title,
        "requested_brand": "Kirkland Signature",
        "requested_pack": pack,
    }


class FakeFirecrawlResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


def _scrape_payload(html, page_status=200, success=True, error=None):
    data = {
        "rawHtml": html,
        "metadata": {"statusCode": page_status, "sourceURL": "https://www.costco.com/"},
    }
    payload = {"success": success, "data": data}
    if error is not None:
        payload["error"] = error
        payload.pop("data", None)
    return payload


def _patch_post(html=None, status_code=200, success=True, page_status=200,
                error=None, raise_exc=None, bad_json=False):
    """Return a context handler for a single Firecrawl POST call."""

    def fake_post(url, json=None, headers=None, timeout=None):
        if raise_exc is not None:
            raise raise_exc
        if bad_json:
            http_code = status_code
            class BadJson:
                status_code = http_code

                def json(self):
                    raise ValueError("not json")
            return BadJson()
        return FakeFirecrawlResponse(
            _scrape_payload(html, page_status=page_status, success=success,
                            error=error),
            status_code=status_code,
        )

    return mock.patch("firecrawl_costco.requests.post", side_effect=fake_post)


def setUpModule():
    os.environ[GATE_ENV] = "1"
    # Redirect evidence writes out of the repo run dir (the adapter defaults
    # to the frozen DISCOVERY run dir; tests must never pollute it).
    firecrawl_costco.DEFAULT_RUN_DIR = tempfile.mkdtemp(prefix="fc-test-run-")


def tearDownModule():
    os.environ.pop(GATE_ENV, None)
    firecrawl_costco.LAST_ERROR = None
    firecrawl_costco.LAST_HTTP_STATUS = None
    firecrawl_costco.LAST_PAGE_STATUS = None


class GateTests(unittest.TestCase):
    def test_blocked_when_gate_off(self):
        with mock.patch.dict("os.environ", {GATE_ENV: "0"}):
            summary = refresh_product_details(["424976"])
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["items_fetched"], 0)
        self.assertEqual(summary["provider"], "FIRECRAWL")
        self.assertTrue(any("not enabled" in (summary.get("reason") or "") for _ in [0]))

    def test_cli_gate_off_exits_2(self):
        with mock.patch.dict("os.environ", {GATE_ENV: "0"}):
            rc = firecrawl_costco._cli(
                ["details", "refresh", "--item-ids", "424976"]
            )
        self.assertEqual(rc, 2)


class SuccessFlowTests(unittest.TestCase):
    def _run_ok(self):
        with mock.patch.dict("os.environ", {KEY_ENV: "fc-test-key"}):
            with _patch_post(html=_fixture("424976"), page_status=200):
                summary = refresh_product_details(
                    ["424976"],
                    manifest_path=None,
                )
        return summary

    def test_success_flow_normalized(self):
        summary = self._run_ok()
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_fetched"], 1)
        self.assertEqual(summary["items_failed"], 0)
        item = summary["items"][0]
        self.assertEqual(item["requested_item_id"], "424976")
        self.assertEqual(item["listed_price"], 17.99)
        self.assertEqual(item["currency"], "USD")
        self.assertEqual(item["brand"], "Kirkland Signature")
        self.assertEqual(
            item["exact_title"],
            "Kirkland Signature Adult 50+ Mature Multi Vitamins & Minerals, 400 Tablets",
        )

    def test_evidence_persisted_scrubbed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {KEY_ENV: "fc-test-key"}):
                with _patch_post(html=_fixture("424976")):
                    summary = refresh_product_details(["424976"], run_dir=tmp)
            self.assertEqual(len(summary["evidence_paths"]), 2)
            raw_path, norm_path = summary["evidence_paths"]
            self.assertTrue(os.path.basename(raw_path).startswith("firecrawl_424976_"))
            self.assertTrue(
                os.path.basename(norm_path).startswith("items_424976_firecrawl_")
            )
            with open(raw_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self.assertEqual(raw["provider"], "FIRECRAWL")
            self.assertEqual(raw["auth_header"], "Bearer <redacted>")
            self.assertNotIn("fc-test-key", json.dumps(raw))
            self.assertEqual(raw["page_status"], 200)
            with open(norm_path, "r", encoding="utf-8") as fh:
                norm = json.load(fh)
            self.assertEqual(norm["item"]["listed_price"], 17.99)


class SoftFailureTests(unittest.TestCase):
    def test_url_not_found_is_soft_continues(self):
        with mock.patch.dict("os.environ", {KEY_ENV: "fc-test-key"}):
            with _patch_post(html=_fixture("1493188"), page_status=200):
                summary = refresh_product_details(["1493188"])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_soft_failed"], 1)
        self.assertEqual(
            summary["items"][0]["identity_match_status"], "url_not_found"
        )
        # SOFT never fabricates fields.
        self.assertIsNone(summary["items"][0]["listed_price"])
        self.assertIsNone(summary["items"][0]["exact_title"])

    def test_empty_body_is_no_data_found_soft(self):
        with mock.patch.dict("os.environ", {KEY_ENV: "fc-test-key"}):
            with _patch_post(html="", page_status=200):
                summary = refresh_product_details(["99999"])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["items_soft_failed"], 1)
        self.assertEqual(
            summary["items"][0]["identity_match_status"], "no_data_found"
        )


class HardFailureTests(unittest.TestCase):
    def _expect_halt(self, **kwargs):
        with mock.patch.dict("os.environ", {KEY_ENV: "fc-test-key"}):
            with _patch_post(**kwargs):
                summary = refresh_product_details(["424976"])
        self.assertEqual(summary["status"], "halted")
        self.assertEqual(summary["items_failed"], 1)
        self.assertEqual(summary["items_fetched"], 0)
        return summary["failures"][0]

    def test_http_402_is_credits_exhausted(self):
        fail = self._expect_halt(status_code=402, html=None)
        self.assertEqual(fail["failure_type"], "credits_exhausted")
        self.assertEqual(fail["http_status"], 402)

    def test_http_401_is_auth_error(self):
        fail = self._expect_halt(status_code=401, html=None)
        self.assertEqual(fail["failure_type"], "auth_error")
        self.assertEqual(fail["http_status"], 401)

    def test_http_429_is_rate_limited(self):
        fail = self._expect_halt(status_code=429, html=None)
        self.assertEqual(fail["failure_type"], "rate_limited")
        self.assertEqual(fail["http_status"], 429)

    def test_http_500_is_http_error(self):
        fail = self._expect_halt(status_code=500, html=None)
        self.assertEqual(fail["failure_type"], "http_error")

    def test_timeout_is_transport_error(self):
        fail = self._expect_halt(
            raise_exc=firecrawl_costco.requests.exceptions.Timeout("t"),
            html=None,
        )
        self.assertEqual(fail["failure_type"], "transport_error")

    def test_success_false_body_is_http_error(self):
        fail = self._expect_halt(success=False, error="boom", html=None)
        self.assertEqual(fail["failure_type"], "http_error")

    def test_success_false_payment_error_is_credits_exhausted(self):
        fail = self._expect_halt(
            success=False, error="Payment required to access this resource",
            html=None,
        )
        self.assertEqual(fail["failure_type"], "credits_exhausted")

    def test_malformed_json_is_malformed_response(self):
        fail = self._expect_halt(bad_json=True, html=None)
        self.assertEqual(fail["failure_type"], "malformed_response")

    def test_missing_key_is_config_error(self):
        with mock.patch.dict("os.environ", {KEY_ENV: ""}):
            with mock.patch("firecrawl_costco.requests.post") as mock_post:
                summary = refresh_product_details(["424976"])
        mock_post.assert_not_called()
        self.assertEqual(summary["status"], "halted")
        self.assertEqual(summary["failures"][0]["failure_type"], "config_error")


class TransportTests(unittest.TestCase):
    def test_last_page_status_shared_on_success(self):
        with mock.patch.dict("os.environ", {KEY_ENV: "fc-test-key"}):
            with _patch_post(html=_fixture("424976"), page_status=200):
                html = _fetch_item_page("https://www.costco.com/.product.424976.html")
        self.assertEqual(html, _fixture("424976"))
        self.assertEqual(firecrawl_costco.LAST_HTTP_STATUS, 200)
        self.assertEqual(firecrawl_costco.LAST_PAGE_STATUS, 200)
        self.assertIsNone(firecrawl_costco.LAST_ERROR)

    def test_classify_hard_failure_typed(self):
        self.assertEqual(
            _classify_hard_failure("credits_exhausted: x", None), "credits_exhausted"
        )
        self.assertEqual(
            _classify_hard_failure("rate_limited: HTTP 429", None), "rate_limited"
        )
        self.assertEqual(
            _classify_hard_failure("auth_error: HTTP 401", None), "auth_error"
        )
        self.assertEqual(
            _classify_hard_failure(
                None, ValueError("FIRECRAWL_API_KEY not configured")
            ),
            "config_error",
        )

    def test_gate_enabled_reflects_env(self):
        with mock.patch.dict("os.environ", {GATE_ENV: "1"}):
            self.assertTrue(_gate_enabled())
        with mock.patch.dict("os.environ", {GATE_ENV: "0"}):
            self.assertFalse(_gate_enabled())


if __name__ == "__main__":
    unittest.main()