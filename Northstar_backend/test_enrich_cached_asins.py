"""Offline tests for the controlled batch enrichment CLI.

Zero network: every live path is exercised through a mocked
rapidapi_client.get_rapidapi_offers, and cache/store/report paths are pointed
at temp locations. Covers dry-run/status zero-network guarantees, live
cap refusals (--live / --limit / --max-requests / --max-credits),
preflight one-request rules, mocked batch runs (10 and 234 ASINs),
resume/skip-fresh, bounded retry eligibility, budget stop reasons,
per-ASIN atomic saves, and 500-ASIN / 5,000-offer scale.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import io
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import amazon_search
import rapidapi_client
import market_snapshot_store as store
import enrich_cached_asins as cli

_TMP = tempfile.mkdtemp(prefix="enrich-cli-test-")
CACHE_PATH = os.path.join(_TMP, "cache.json")
STORE_PATH = os.path.join(_TMP, "store.json")
REPORT_PATH = os.path.join(_TMP, "report.json")


def _result(asin, offer_count=12, offers=None, gaps=None, credits_used=1,
            credits_remaining=999, observed_at="2026-08-17T06:59:33+00:00",
            buy_box_price=None, buy_box_seller=None):
    offers = offers if offers is not None else []
    return {
        "source": "rapidapi",
        "asin": asin,
        "title": "Kirkland Test Item " + asin,
        "offer_count": offer_count,
        "offers_returned_count": len(offers),
        "buy_box_price": buy_box_price,
        "buy_box_price_raw": buy_box_price,
        "buy_box_seller": buy_box_seller,
        "buy_box_seller_id": "A1" if buy_box_seller else None,
        "buy_box_is_fba": True if buy_box_seller else None,
        "buy_box_is_fbm": None,
        "buy_box_is_prime": None,
        "buy_box_condition": None,
        "observed_fba_offer_count": 1 if offers else 0,
        "observed_fbm_offer_count": max(0, len(offers) - (1 if offers else 0)),
        "observed_amazon_offer_count": 1 if buy_box_seller == "Amazon.com" else 0,
        "offers": offers,
        "request_zip_code": "75201",
        "observed_at": observed_at,
        "credits_used": credits_used,
        "credits_remaining": credits_remaining,
        "data_gaps": list(gaps or []),
    }


def _offer(price, fba=False, fbm=False, buybox=False):
    return {
        "position": 1,
        "buybox_winner": buybox,
        "price": {"value": price, "raw": "$%.2f" % price, "currency": "USD"},
        "condition": {"is_new": True, "title": "New"},
        "seller_id": "A1" if buybox else "S1",
        "seller_name": "Amazon.com" if buybox else "Seller Co",
        "seller_rating": 4.5,
        "seller_positive_percentage": 90,
        "seller_ratings_total": 200,
        "is_prime": True,
        "is_fba": fba,
        "is_fbm": fbm,
        "is_sba": False,
        "fulfilled_by_amazon": fba,
        "shipping_text": "FREE Shipping" if fba else "Shipping",
        "shipping_is_free": fba,
        "ships_from": "US",
        "minimum_order_quantity": 1,
        "maximum_order_quantity": 10,
    }


def _ok_response(asin, offer_count=1, offers=None, credits_used=1, credits_remaining=999):
    """Return a normalized rapidapi offer dict (mock boundary output)."""
    offers = offers if offers is not None else []
    d = _result(asin, offer_count=offer_count, offers=offers,
                credits_used=credits_used, credits_remaining=credits_remaining)
    d["source"] = "rapidapi"
    d["provider_endpoint"] = "/products/%s/offers" % asin
    # Mirror get_rapidapi_offers buy-box extraction: pick the flagged winner.
    buy_box = next((o for o in offers if o.get("buybox_winner") is True),
                   offers[0] if offers else None)
    if buy_box is not None:
        price = buy_box.get("price")
        if isinstance(price, dict):
            price = price.get("value")
        d["buy_box_price"] = price
        d["buy_box_price_raw"] = buy_box.get("price")
        d["buy_box_seller"] = buy_box.get("seller_name")
        d["buy_box_seller_id"] = buy_box.get("seller_id")
        d["buy_box_is_fba"] = buy_box.get("is_fba")
        d["buy_box_is_fbm"] = buy_box.get("is_fbm")
        d["buy_box_condition"] = buy_box.get("condition")
    return d


def _http_error_response(status_code=500):
    """Return a normalized error dict: no offers + an HTTP error gap."""
    return {
        "source": "rapidapi",
        "asin": None,
        "provider_asin": None,
        "request_id": None,
        "title": None,
        "offer_count": None,
        "offers_returned_count": 0,
        "buy_box_price": None,
        "buy_box_price_raw": None,
        "buy_box_seller": None,
        "buy_box_seller_id": None,
        "buy_box_is_fba": None,
        "buy_box_is_fbm": None,
        "buy_box_is_prime": None,
        "buy_box_condition": None,
        "observed_fba_offer_count": 0,
        "observed_fbm_offer_count": 0,
        "observed_amazon_offer_count": 0,
        "offers": [],
        "request_zip_code": None,
        "observed_at": None,
        "credits_used": None,
        "credits_remaining": None,
        "cost_usd": None,
        "provider_endpoint": None,
        "data_gaps": ["RapidAPI offers API returned HTTP %s." % status_code],
    }


class CliEnvTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "SCANNER_SEARCH_CACHE_PATH": CACHE_PATH,
                "SCANNER_MARKET_SNAPSHOT_PATH": STORE_PATH,
                "SCANNER_ENRICH_RUN_REPORT_PATH": REPORT_PATH,
            },
            clear=False,
        )
        self.env.start()
        for path in (CACHE_PATH, STORE_PATH, REPORT_PATH):
            if os.path.exists(path):
                os.remove(path)

    def tearDown(self):
        self.env.stop()

    def write_cache(self, n, price=48.87):
        products = []
        for i in range(n):
            asin = "B0%08d" % i
            products.append({
                "asin": asin,
                "name": "Kirkland Test Item %d" % i,
                "amazon_price": price,
                "product_url": "https://www.amazon.com/dp/%s" % asin,
                "brand": "Kirkland Signature",
                "sales_volume": None,
                "monthly_sales_estimate": None,
                "monthly_sales_estimated": False,
                "rating": None,
                "reviews_count": None,
            })
        amazon_search.save_cached_candidates(products, search_terms=["kirkland"], source="brightdata")
        return [p["asin"] for p in products]

    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(argv)
        return code, out.getvalue()

    def mock_get(self, response_fn):
        calls = []

        def fake_get(asin):
            calls.append(asin)
            return response_fn(asin)

        patcher = patch.object(rapidapi_client, "get_rapidapi_offers", side_effect=fake_get)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls


class ZeroNetworkTests(CliEnvTests):
    def test_dry_run_zero_network(self):
        self.write_cache(10)
        with patch.object(rapidapi_client.requests, "get",
                          side_effect=AssertionError("network call in dry-run")):
            code, out = self.run_cli(["--mode", "dry-run", "--limit", "10"])
        self.assertEqual(code, 0)
        self.assertIn("zero network calls", out)
        self.assertIn("planned:               10", out)
        self.assertIn("requests projected:    10", out)
        report = store.read_run_report()
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(report["counts"]["planned"], 10)
        self.assertFalse(os.path.exists(STORE_PATH))

    def test_dry_run_limit_scoping(self):
        self.write_cache(10)
        code, out = self.run_cli(["--mode", "dry-run", "--limit", "3"])
        self.assertEqual(code, 0)
        self.assertIn("planned:               3", out)
        self.assertIn("requests projected:    3", out)

    def test_dry_run_skips_fresh_snapshots_in_plan(self):
        asins = self.write_cache(3)
        snap = store.build_snapshot(asins[0], _result(asins[0], offer_count=1, offers=[_offer(10)]))
        ok, err = store.save_snapshot(asins[0], snap)
        self.assertTrue(ok, err)
        code, out = self.run_cli(["--mode", "dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("fresh (skip):        1", out)
        self.assertIn("requests projected:    2", out)

    def test_status_zero_network(self):
        self.write_cache(3)
        snap = store.build_snapshot("B000000000", _result("B000000000", offer_count=1, offers=[_offer(10)]))
        store.save_snapshot("B000000000", snap)
        with patch.object(rapidapi_client.requests, "get",
                          side_effect=AssertionError("network call in status")):
            code, out = self.run_cli(["--mode", "status"])
        self.assertEqual(code, 0)
        self.assertIn("snapshots:             1", out)
        self.assertIn("available", out)

    def test_dry_run_refuses_no_cache(self):
        code, out = self.run_cli(["--mode", "dry-run"])
        self.assertEqual(code, 4)
        self.assertIn("missing or empty", out)


class CapGateTests(CliEnvTests):
    def test_batch_refused_without_live(self):
        self.write_cache(5)
        code, out = self.run_cli(["--mode", "batch", "--limit", "5",
                                  "--max-requests", "5", "--max-credits", "50"])
        self.assertEqual(code, 2)
        self.assertIn("--live", out)
        self.assertFalse(os.path.exists(STORE_PATH))

    def test_batch_refused_without_limit(self):
        self.write_cache(5)
        code, out = self.run_cli(["--mode", "batch", "--live",
                                  "--max-requests", "5", "--max-credits", "50"])
        self.assertEqual(code, 2)
        self.assertIn("--limit", out)

    def test_batch_refused_without_max_requests(self):
        self.write_cache(5)
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "5",
                                  "--max-credits", "50"])
        self.assertEqual(code, 2)
        self.assertIn("--max-requests", out)

    def test_batch_refused_without_max_credits(self):
        self.write_cache(5)
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "5",
                                  "--max-requests", "5"])
        self.assertEqual(code, 2)
        self.assertIn("--max-credits", out)

    def test_batch_refused_zero_limit(self):
        self.write_cache(5)
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "0",
                                  "--max-requests", "5", "--max-credits", "50"])
        self.assertEqual(code, 2)

    def test_batch_refused_asin_flag(self):
        self.write_cache(5)
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "1",
                                  "--max-requests", "1", "--max-credits", "5",
                                  "--asin", "B0AAAAAAAA"])
        self.assertEqual(code, 2)
        self.assertIn("preflight", out)

    def test_preflight_refused_without_asin(self):
        code, out = self.run_cli(["--mode", "preflight", "--live",
                                  "--limit", "1", "--max-requests", "1", "--max-credits", "5"])
        self.assertEqual(code, 2)
        self.assertIn("--asin", out)

    def test_preflight_refused_invalid_asin(self):
        code, out = self.run_cli(["--mode", "preflight", "--live", "--asin", "bad",
                                  "--limit", "1", "--max-requests", "1", "--max-credits", "5"])
        self.assertEqual(code, 2)
        self.assertIn("Invalid ASIN", out)

    def test_preflight_refused_limit_not_one(self):
        code, out = self.run_cli(["--mode", "preflight", "--live", "--asin", "B00GYZWNY6",
                                  "--limit", "2", "--max-requests", "1", "--max-credits", "5"])
        self.assertEqual(code, 2)
        self.assertIn("--limit 1", out)

    def test_preflight_refused_max_requests_not_one(self):
        code, out = self.run_cli(["--mode", "preflight", "--live", "--asin", "B00GYZWNY6",
                                  "--limit", "1", "--max-requests", "2", "--max-credits", "5"])
        self.assertEqual(code, 2)
        self.assertIn("--max-requests 1", out)


class PreflightTests(CliEnvTests):
    def test_preflight_exactly_one_request_and_saves(self):
        self.write_cache(2)
        calls = self.mock_get(
            lambda asin: _ok_response(
                asin, offer_count=2,
                offers=[_offer(56.66, fba=True, buybox=True), _offer(49.99)],
            )
        )
        code, out = self.run_cli(["--mode", "preflight", "--live", "--asin", "B0AAAAAAAA",
                                  "--limit", "1", "--max-requests", "1", "--max-credits", "5"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], "B0AAAAAAAA")
        snap = store.get_snapshot("B0AAAAAAAA")
        self.assertIsNotNone(snap)
        self.assertEqual(snap["data_status"], store.DATA_STATUS_AVAILABLE)
        self.assertEqual(snap["buy_box"]["price"], 56.66)
        self.assertEqual(snap["credits_used"], 1)
        report = store.read_run_report()
        self.assertEqual(report["mode"], "preflight")
        self.assertEqual(report["counts"]["succeeded"], 1)
        self.assertEqual(report["counts"]["attempted"], 1)
        self.assertEqual(report["stop_reason"], "completed")

    def test_preflight_failure_preserves_prior_valid_snapshot(self):
        prior = store.build_snapshot(
            "B0AAAAAAAA", _result("B0AAAAAAAA", offer_count=2,
                                  offers=[_offer(10)], buy_box_price=10)
        )
        ok, err = store.save_snapshot("B0AAAAAAAA", prior)
        self.assertTrue(ok, err)
        with open(STORE_PATH, "rb") as f:
            before = f.read()

        def timeout_response(asin):
            # get_rapidapi_offers never raises on a timeout; it returns a
            # normalized dict with a "timed out" error gap.
            return {
                "source": "rapidapi", "asin": asin, "provider_asin": asin,
                "request_id": None, "title": None, "offer_count": None,
                "offers_returned_count": 0, "buy_box_price": None,
                "buy_box_price_raw": None, "buy_box_seller": None,
                "buy_box_seller_id": None, "buy_box_is_fba": None,
                "buy_box_is_fbm": None, "buy_box_is_prime": None,
                "buy_box_condition": None, "observed_fba_offer_count": 0,
                "observed_fbm_offer_count": 0, "observed_amazon_offer_count": 0,
                "offers": [], "request_zip_code": None, "observed_at": None,
                "credits_used": None, "credits_remaining": None,
                "cost_usd": None, "provider_endpoint": None,
                "data_gaps": ["RapidAPI offers request timed out."],
            }

        calls = self.mock_get(timeout_response)
        code, out = self.run_cli(["--mode", "preflight", "--live", "--asin", "B0AAAAAAAA",
                                  "--limit", "1", "--max-requests", "1", "--max-credits", "5"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 1)
        with open(STORE_PATH, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(store.get_snapshot("B0AAAAAAAA"), prior)
        report = store.read_run_report()
        self.assertEqual(report["counts"]["failed"], 1)
        self.assertEqual(len(report["errors"]), 1)


class BatchTests(CliEnvTests):
    def test_batch_mocked_10(self):
        self.write_cache(10)
        calls = self.mock_get(
            lambda asin: _ok_response(asin, offer_count=1, offers=[_offer(10)])
        )
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "10",
                                  "--max-requests", "10", "--max-credits", "100"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 10)
        self.assertIn("succeeded:             10", out)
        self.assertIn("stop_reason:           completed", out)
        self.assertEqual(len(store.load_snapshots()), 10)
        report = store.read_run_report()
        self.assertEqual(report["counts"]["succeeded"], 10)
        self.assertEqual(report["credits"]["reported_used"], 10)

    def test_batch_resume_skips_fresh(self):
        asins = self.write_cache(10)
        for asin in asins[:5]:
            snap = store.build_snapshot(asin, _result(asin, offer_count=1, offers=[_offer(10)]))
            store.save_snapshot(asin, snap)
        calls = self.mock_get(
            lambda asin: _ok_response(asin, offer_count=1, offers=[_offer(10)])
        )
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "10",
                                  "--max-requests", "10", "--max-credits", "100"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 5)
        self.assertIn("skipped_fresh:         5", out)
        self.assertIn("succeeded:             5", out)
        self.assertEqual(len(store.load_snapshots()), 10)

    def test_batch_resume_retries_eligible_failed(self):
        asins = self.write_cache(3)
        failed = store.build_snapshot(
            asins[0], _result(asins[0], offers=[], gaps=["HTTP 500."])
        )
        store.save_snapshot(asins[0], failed)
        calls = self.mock_get(
            lambda asin: _ok_response(asin, offer_count=1, offers=[_offer(10)])
        )
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "3",
                                  "--max-requests", "5", "--max-credits", "50"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 3)
        self.assertIn("succeeded:             3", out)
        snap = store.get_snapshot(asins[0])
        self.assertEqual(snap["data_status"], store.DATA_STATUS_AVAILABLE)
        self.assertEqual(snap["attempts"], 2)

    def test_batch_skips_retry_ineligible(self):
        asins = self.write_cache(3)
        exhausted = store.build_snapshot(
            asins[0], _result(asins[0], offers=[], gaps=["HTTP 500."]),
            prior_attempts=store.MAX_ATTEMPTS - 1,
        )
        store.save_snapshot(asins[0], exhausted)
        calls = self.mock_get(
            lambda asin: _ok_response(asin, offer_count=1, offers=[_offer(10)])
        )
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "3",
                                  "--max-requests", "5", "--max-credits", "50"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 2)
        self.assertIn("skipped_retry_inelig:  1", out)
        self.assertIn("succeeded:             2", out)

    def test_batch_max_requests_stop(self):
        self.write_cache(10)
        calls = self.mock_get(
            lambda asin: _ok_response(asin, offer_count=1, offers=[_offer(10)])
        )
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "10",
                                  "--max-requests", "3", "--max-credits", "100"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 3)
        self.assertIn("stop_reason:           max_requests", out)
        self.assertIn("skipped_cap:           7", out)
        self.assertEqual(len(store.load_snapshots()), 3)
        report = store.read_run_report()
        self.assertEqual(report["counts"]["attempted"], 3)
        self.assertEqual(report["counts"]["skipped_cap"], 7)

    def test_batch_max_credits_stop(self):
        self.write_cache(10)
        calls = self.mock_get(
            lambda asin: _ok_response(asin, offer_count=1, offers=[_offer(10)],
                                      credits_used=40, credits_remaining=960)
        )
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "10",
                                  "--max-requests", "10", "--max-credits", "100"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 3)
        self.assertIn("stop_reason:           max_credits", out)
        self.assertIn("skipped_cap:           7", out)

    def test_batch_opt_in_retries_are_finite(self):
        self.write_cache(3)
        calls = []

        def fake_get(asin):
            calls.append(asin)
            if asin == "B000000000" and len([c for c in calls if c == asin]) == 1:
                return _http_error_response(500)
            return _ok_response(asin, offer_count=1, offers=[_offer(10)])

        with patch.object(rapidapi_client, "get_rapidapi_offers", side_effect=fake_get):
            code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "3",
                                      "--max-requests", "10", "--max-credits", "50",
                                      "--retries", "1"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 4)
        self.assertIn("succeeded:             3", out)
        snap = store.get_snapshot("B000000000")
        self.assertEqual(snap["data_status"], store.DATA_STATUS_AVAILABLE)
        self.assertEqual(snap["attempts"], 2)

    def test_batch_failed_records_error_and_saves_failed_snapshot(self):
        self.write_cache(3)
        calls = self.mock_get(lambda asin: _http_error_response(500))
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "3",
                                  "--max-requests", "3", "--max-credits", "50"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 3)
        self.assertIn("failed:                3", out)
        self.assertEqual(len(store.load_snapshots()), 3)
        snap = store.get_snapshot("B000000000")
        self.assertEqual(snap["data_status"], store.DATA_STATUS_FAILED)
        self.assertIn("HTTP 500", snap["last_error"])
        report = store.read_run_report()
        self.assertEqual(len(report["errors"]), 3)


class ScaleTests(CliEnvTests):
    def test_batch_234_mocked_performance(self):
        self.write_cache(234)
        calls = self.mock_get(
            lambda asin: _ok_response(asin, offer_count=1, offers=[_offer(10)])
        )
        started = time.monotonic()
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "234",
                                  "--max-requests", "234", "--max-credits", "1300"])
        elapsed = time.monotonic() - started
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 234)
        self.assertIn("succeeded:             234", out)
        self.assertEqual(len(store.load_snapshots()), 234)
        self.assertLess(elapsed, 60.0, "234-ASIN mocked batch took %.1fs" % elapsed)

    def test_500_asin_5000_offer_fixture_performance(self):
        self.write_cache(500)
        offers = [_offer(10 + i, fba=(i % 2 == 0)) for i in range(10)]
        calls = self.mock_get(
            lambda asin: _ok_response(asin, offer_count=10, offers=offers)
        )
        started = time.monotonic()
        code, out = self.run_cli(["--mode", "batch", "--live", "--limit", "500",
                                  "--max-requests", "500", "--max-credits", "2500"])
        elapsed = time.monotonic() - started
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 500)
        self.assertIn("succeeded:             500", out)
        self.assertLess(elapsed, 60.0, "500-ASIN mocked batch took %.1fs" % elapsed)

        snapshots = store.load_snapshots()
        self.assertEqual(len(snapshots), 500)
        total_offers = sum(len(s.get("offers") or []) for s in snapshots.values())
        self.assertEqual(total_offers, 5000)


if __name__ == "__main__":
    unittest.main(verbosity=2)