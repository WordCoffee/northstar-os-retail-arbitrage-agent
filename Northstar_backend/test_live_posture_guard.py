"""Live-posture guard tests (offline, zero network, zero provider calls).

Phase 1 safety (2026-10-09): ``SCANNER_LIVE_ALLOWED`` alone must never be
enough to arm live providers for the web app. Arming additionally requires an
explicit per-run arm flag (``NS_LIVE_PER_RUN_ARMED``) and a positive per-run
cost cap (``NS_LIVE_PER_RUN_CAP_CENTS``). These tests prove:

  1. the posture check classifies every env combination correctly,
  2. app startup REFUSES an unbounded live mode,
  3. app startup ACCEPTS a cache-only deployment and a bounded live run,
  4. no GET route opens a non-loopback provider connection while the app is
     running with the gate disarmed (socket-level instrumentation).

Provider clients are patched to raise, so any regression fails loudly instead
of hitting the network.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import os
import socket
import tempfile
import unittest
from unittest import mock
from unittest.mock import patch

import amazon_search
import bright_data_client
import live_gate
import main

_TMP = tempfile.mkdtemp(prefix="live-posture-")

_PROVIDER_CALLED = AssertionError("a live provider client was called")


def _boom(*args, **kwargs):
    raise _PROVIDER_CALLED


def _provider_patches():
    return [
        patch.object(bright_data_client, "search_products", side_effect=_boom),
        patch.object(bright_data_client, "get_product_detail", side_effect=_boom),
        patch.object(amazon_search, "_search_brightdata", side_effect=_boom),
        patch.object(amazon_search, "_search_chocodata", side_effect=_boom),
    ]


def _off_env():
    return {
        "SCANNER_LIVE_ALLOWED": "0",
        "SCANNER_SEARCH_SOURCE": "BRIGHTDATA",
        "SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA",
        "SCANNER_LOCAL_SNAPSHOT_MERGE": "0",
        "PAGES_TO_SEARCH": "10",
        "SEARCH_KEYWORDS": "kirkland",
        "SCANNER_SEARCH_CACHE_PATH": os.path.join(_TMP, "search-cache.json"),
        "SCANNER_OFFER_CACHE_PATH": os.path.join(_TMP, "offer-cache.json"),
        "SCANNER_SELLER_CACHE_PATH": os.path.join(_TMP, "seller-cache.json"),
        "COSTCO_CATALOG_SOURCE": "OFF",
        "NORTHSTAR_DISABLE_RATE_LIMIT": "1",
        "ENVIRONMENT": "test",
    }


class LivePostureClassificationTests(unittest.TestCase):
    """live_posture_problems() names exactly what is missing."""

    def test_disarmed_gate_has_no_problems(self):
        with patch.dict(os.environ, _off_env(), clear=True):
            self.assertEqual(live_gate.live_posture_problems(), [])

    def test_armed_without_per_run_bounds_is_refused(self):
        env = _off_env()
        env["SCANNER_LIVE_ALLOWED"] = "1"
        with patch.dict(os.environ, env, clear=True):
            problems = live_gate.live_posture_problems()
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any("NS_LIVE_PER_RUN_ARMED" in p for p in problems), problems)
        self.assertTrue(any("NS_LIVE_PER_RUN_CAP_CENTS" in p for p in problems), problems)

    def test_armed_with_arm_flag_but_no_cap_is_refused(self):
        env = _off_env()
        env.update({"SCANNER_LIVE_ALLOWED": "1", "NS_LIVE_PER_RUN_ARMED": "1"})
        with patch.dict(os.environ, env, clear=True):
            problems = live_gate.live_posture_problems()
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("NS_LIVE_PER_RUN_CAP_CENTS", problems[0])

    def test_armed_with_cap_but_no_arm_flag_is_refused(self):
        env = _off_env()
        env.update({"SCANNER_LIVE_ALLOWED": "1", "NS_LIVE_PER_RUN_CAP_CENTS": "50"})
        with patch.dict(os.environ, env, clear=True):
            problems = live_gate.live_posture_problems()
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("NS_LIVE_PER_RUN_ARMED", problems[0])

    def test_bounded_per_run_arming_is_allowed(self):
        env = _off_env()
        env.update({
            "SCANNER_LIVE_ALLOWED": "1",
            "NS_LIVE_PER_RUN_ARMED": "1",
            "NS_LIVE_PER_RUN_CAP_CENTS": "50",
        })
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(live_gate.live_posture_problems(), [])
            live_gate.assert_live_posture()  # must not raise

    def test_non_positive_or_garbage_caps_are_refused(self):
        for cap in ("0", "-1", "abc", "1.5", " "):
            env = _off_env()
            env.update({
                "SCANNER_LIVE_ALLOWED": "1",
                "NS_LIVE_PER_RUN_ARMED": "1",
                "NS_LIVE_PER_RUN_CAP_CENTS": cap,
            })
            with patch.dict(os.environ, env, clear=True):
                self.assertTrue(
                    live_gate.live_posture_problems(),
                    f"cap {cap!r} must be refused",
                )

    def test_per_run_cap_parses_positive_int(self):
        with patch.dict(os.environ, {"NS_LIVE_PER_RUN_CAP_CENTS": "250"}, clear=True):
            self.assertEqual(live_gate.per_run_cap_cents(), 250)
        with patch.dict(os.environ, {"NS_LIVE_PER_RUN_CAP_CENTS": "0"}, clear=True):
            self.assertIsNone(live_gate.per_run_cap_cents())


class LivePostureStartupTests(unittest.TestCase):
    """The app refuses to boot an unbounded live mode and boots otherwise.

    The lifespan is exercised through a real ASGI request so the guard runs
    inside the same startup path production uses.
    """

    def _get_health_with_env(self, env):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, env, clear=True):
            providers = _provider_patches()
            for p in providers:
                p.start()
            try:
                with TestClient(main.app) as client:
                    return client.get("/health")
            finally:
                for p in reversed(providers):
                    p.stop()

    def test_startup_refuses_unbounded_live_mode(self):
        env = _off_env()
        env["SCANNER_LIVE_ALLOWED"] = "1"
        with self.assertRaises(RuntimeError) as ctx:
            self._get_health_with_env(env)
        message = str(ctx.exception)
        self.assertIn("LIVE POSTURE VIOLATION", message)
        self.assertIn("NS_LIVE_PER_RUN_ARMED", message)

    def test_startup_accepts_cache_only_deployment(self):
        resp = self._get_health_with_env(_off_env())
        self.assertEqual(resp.status_code, 200)

    def test_startup_accepts_bounded_live_run(self):
        env = _off_env()
        env.update({
            "SCANNER_LIVE_ALLOWED": "1",
            "NS_LIVE_PER_RUN_ARMED": "1",
            "NS_LIVE_PER_RUN_CAP_CENTS": "25",
        })
        resp = self._get_health_with_env(env)
        self.assertEqual(resp.status_code, 200)


class GetRoutesOpenNoProviderConnectionTests(unittest.TestCase):
    """Socket-level proof: with the gate disarmed, every GET route the UI
    calls opens ZERO non-loopback connections.

    This is the regression guard for the 2026-10-08 incident, where a plain
    GET /api/kirkland/scanner opened 19 Bright Data connections.
    """

    def _non_loopback_connects_during(self, fn):
        seen = []

        real_connect = socket.socket.connect

        def spy(self, address):  # pragma: no cover - only runs on a regression
            host = address[0] if isinstance(address, tuple) else str(address)
            if host in ("127.0.0.1", "::1", "localhost", ""):
                return real_connect(self, address)
            seen.append(host)
            raise _PROVIDER_CALLED

        with patch.object(socket.socket, "connect", spy):
            fn()
        return seen

    def test_every_ui_get_route_opens_zero_provider_connections(self):
        from fastapi.testclient import TestClient

        env = _off_env()
        with patch.dict(os.environ, env, clear=True):
            providers = _provider_patches()
            for p in providers:
                p.start()
            try:
                with TestClient(main.app) as client:
                    def hit_every_get():
                        client.get("/health")
                        client.get("/api/v1/status")
                        client.get("/api/kirkland/scanner")
                        client.get("/api/kirkland/live")
                        client.get("/api/sourcescout")
                        client.get("/api/products/finder")
                        client.get("/api/autothink/models")
                        client.get("/api/v1/reasoning/models")

                    seen = self._non_loopback_connects_during(hit_every_get)
            finally:
                for p in reversed(providers):
                    p.stop()
        self.assertEqual(seen, [], f"GET routes opened provider connections: {seen}")

    def test_scanner_endpoint_reports_live_disabled(self):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, _off_env(), clear=True):
            providers = _provider_patches()
            for p in providers:
                p.start()
            try:
                with TestClient(main.app) as client:
                    resp = client.get("/api/kirkland/scanner")
            finally:
                for p in reversed(providers):
                    p.stop()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["data"]["summary"]["live_allowed"])
        self.assertEqual(body["data"]["summary"]["scanner_mode"], "cache_only")


if __name__ == "__main__":
    unittest.main()
