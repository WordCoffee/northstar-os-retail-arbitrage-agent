"""Structural network guard for test runs + proof it is active.

Every other test module imports this module first: importing it activates
the shared ``network_guard`` module, which patches the real ``requests``
client so any unmocked call raises ``NetworkGuardViolation``. This closes the
gap where ``python -m unittest`` starts before the working directory is on
``sys.path`` (so the ``sitecustomize.py`` startup guard cannot load) — no
.env fallback misconfiguration (SCANNER_SEARCH_FALLBACK,
SCANNER_OFFER_ENRICHMENT, live keys) can ever trigger a real network call
that burns credits or leaks secrets from the suite. Tests must mock HTTP;
the guard only blocks the real client. Set NS_ALLOW_NETWORK=1 to bypass.

If the guard tests fail (real requests succeed), stop and fix the
``network_guard`` module before running any other test.
"""

import os
import sys
import tempfile

# Hermetic search-candidate cache: every test process reads/writes a temp
# cache instead of the real data/scanner-search-cache.json, so enabled-mode
# tests that run a mocked live search can never touch real data files.
os.environ.setdefault(
    "SCANNER_SEARCH_CACHE_PATH",
    os.path.join(tempfile.mkdtemp(prefix="ns-search-cache-"), "scanner-search-cache.json"),
)

# Single source of truth for the offline guard. Importing this activates the
# import-time install() unless NS_ALLOW_NETWORK=1 bypasses it. Re-export the
# typed exception for callers that want to catch the specific type.
import requests
import network_guard
from network_guard import NetworkGuardViolation  # noqa: F401  (public API)

import unittest


class NetworkGuardTests(unittest.TestCase):
    def test_real_requests_are_blocked_under_test_run(self):
        with self.assertRaises(NetworkGuardViolation):
            requests.get("https://example.com")

    def test_real_post_is_blocked_under_test_run(self):
        with self.assertRaises(NetworkGuardViolation):
            requests.post("https://example.com")

    def test_session_request_is_blocked_under_test_run(self):
        with self.assertRaises(NetworkGuardViolation):
            requests.sessions.Session().request("GET", "https://example.com")

    def test_guard_is_idempotent(self):
        # install() twice must not error and must keep blocking.
        network_guard.install()
        network_guard.install()
        with self.assertRaises(NetworkGuardViolation):
            requests.get("https://example.com")

    def test_block_network_context_restores_client(self):
        # A scoped block must tear down only its own guard; the process-wide
        # guard already installed at import stays active afterwards.
        network_guard.uninstall()
        # Real requests work now (guard removed).
        network_guard.install()
        with network_guard.block_network():
            with self.assertRaises(NetworkGuardViolation):
                requests.get("https://example.com")
        # Process-wide guard (re-installed above) still blocks:
        with self.assertRaises(NetworkGuardViolation):
            requests.get("https://example.com")


if __name__ == "__main__":
    unittest.main(verbosity=2)