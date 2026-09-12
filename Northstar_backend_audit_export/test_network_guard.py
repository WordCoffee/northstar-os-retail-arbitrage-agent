"""Structural network guard for test runs + proof it is active.

Every other test module imports this module first: importing it patches
the real ``requests`` client so any unmocked call raises
``NetworkDisabledError``. This closes the gap where ``python -m unittest``
starts before the working directory is on ``sys.path`` (so the
``sitecustomize.py`` startup guard cannot load) — no .env fallback
misconfiguration (SCANNER_SEARCH_FALLBACK, SCANNER_OFFER_ENRICHMENT,
live keys) can ever trigger a real network call that burns credits or
leaks secrets from the suite. Tests must mock HTTP; the guard only
blocks the real client. Set NS_ALLOW_NETWORK=1 to bypass.

If the guard tests fail (real requests succeed), stop and fix this
module before running any other test.
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

import requests

if os.environ.get("NS_ALLOW_NETWORK") != "1":

    class NetworkDisabledError(RuntimeError):
        pass

    def _blocked(*args, **kwargs):
        raise NetworkDisabledError(
            "Real network calls are disabled during test runs. Mock all "
            "HTTP clients (requests) in tests; check .env fallback "
            "settings (SCANNER_SEARCH_FALLBACK etc.)."
        )

    for _name in ("get", "post", "put", "delete", "patch", "head", "options", "request"):
        setattr(requests.api, _name, _blocked)
    requests.sessions.Session.request = _blocked

import unittest


class NetworkGuardTests(unittest.TestCase):
    def test_real_requests_are_blocked_under_test_run(self):
        with self.assertRaises(RuntimeError):
            requests.get("https://example.com")

    def test_real_post_is_blocked_under_test_run(self):
        with self.assertRaises(RuntimeError):
            requests.post("https://example.com")

    def test_session_request_is_blocked_under_test_run(self):
        with self.assertRaises(RuntimeError):
            requests.sessions.Session().request("GET", "https://example.com")


if __name__ == "__main__":
    unittest.main(verbosity=2)