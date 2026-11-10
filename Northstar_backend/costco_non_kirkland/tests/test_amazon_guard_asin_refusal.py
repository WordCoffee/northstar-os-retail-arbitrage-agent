"""T1-amazon-guard: `assert_no_amazon_direct_scan` must fire on the `asin=` path.

Both production callers pass `asin=` and never `url=`:

  * `costco_non_kirkland/pipeline.py:383`  - manifest items -> `adapter.fetch(asin)`
  * `provider_imports/selleramp_importer.py:67` - rows of an approved export

so the pre-fix guard (which inspected `url=` only) was dead code at every real
call site. These tests prove the guard now refuses a direct-scan *locator* that
arrives through `asin=`, that the refusal happens BEFORE any socket is opened,
and that a bare ASIN from an authorized export still passes (the sanctioned
path must not be broken to block the prohibited one).
"""
from __future__ import annotations

import socket
import unittest
from unittest import mock

import test_network_guard  # noqa: F401  (activates the offline network guard)

from costco_non_kirkland.amazon_guard import (
    AmazonDirectScanProhibited,
    assert_no_amazon_direct_scan,
    is_amazon_direct_url,
)


class _NoSocketAllowed:
    """Any socket creation fails the test: proof the refusal beats the request."""

    def __enter__(self):
        self._socket = mock.patch.object(
            socket, "socket", side_effect=AssertionError("socket opened - the guard ran too late"))
        self._create = mock.patch.object(
            socket, "create_connection",
            side_effect=AssertionError("connection opened - the guard ran too late"))
        self._socket.start()
        self._create.start()
        return self

    def __exit__(self, *exc_info):
        self._create.stop()
        self._socket.stop()
        return False


class AmazonGuardAsinRefusalTests(unittest.TestCase):
    HOSTILE_ASINS = (
        "https://www.amazon.com/dp/B0TEST1234",
        "http://amazon.co.uk/dp/B0TEST1234",
        "www.amazon.com/dp/B0TEST1234",
        "/dp/B0TEST1234",
        "amazon.com",
        "https://amzn.to/3xyz",
        "B0TEST1234?ref=sr_1",
        "B0 TEST 1234",
        "https://sas.selleramp.com/r/sas/lookup?search_term=B0TEST1234",
    )

    def test_locator_in_asin_is_refused_before_any_socket(self):
        for value in self.HOSTILE_ASINS:
            with self.subTest(asin=value), _NoSocketAllowed():
                with self.assertRaises(AmazonDirectScanProhibited) as ctx:
                    assert_no_amazon_direct_scan(asin=value)
                self.assertIn("asin=", str(ctx.exception))

    def test_amazon_url_in_url_argument_still_refused_before_any_socket(self):
        with _NoSocketAllowed():
            with self.assertRaises(AmazonDirectScanProhibited):
                assert_no_amazon_direct_scan("https://www.amazon.com/dp/B0TEST1234")

    def test_bare_asin_from_authorized_export_still_allowed(self):
        # The sanctioned path: identity keys only, no fetch target.
        with _NoSocketAllowed():
            self.assertIsNone(assert_no_amazon_direct_scan(asin="B0TEST"))
            self.assertIsNone(assert_no_amazon_direct_scan(asin="B0TEST1234"))
            self.assertIsNone(assert_no_amazon_direct_scan(asin="b0test1234"))
            self.assertIsNone(assert_no_amazon_direct_scan(asin=None))
            self.assertIsNone(assert_no_amazon_direct_scan(asin="   "))

    def test_provider_deep_link_and_bare_asin_together_allowed(self):
        with _NoSocketAllowed():
            assert_no_amazon_direct_scan(
                "https://sas.selleramp.com/r/sas/lookup?search_term=B0TEST1234",
                asin="B0TEST1234")

    def test_real_amazon_url_is_still_detected_by_helper(self):
        # Guards against a repair that weakens the original url= check.
        self.assertTrue(is_amazon_direct_url("https://www.amazon.com/dp/B0TEST"))
        self.assertFalse(is_amazon_direct_url("https://sas.selleramp.com/r/sas/lookup"))


if __name__ == "__main__":
    unittest.main()
