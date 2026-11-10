"""T1-amazon-auth-gate: the token refresh refuses INSIDE the auth classes.

Before the fix, `SPAPIAuth._refresh` / `AdsAPIAuth._refresh` POSTed to
api.amazon.com/auth/o2/token with no gate of their own; the Amazon-linkage
gate existed only on the importers' public methods, so any caller holding a
bare auth instance (or any future importer that forgot the check) reached
Amazon. These tests construct the auth classes DIRECTLY, with credentials
present, and prove:

  * with the linkage gate off the refresh raises before any request
    (httpx.post is never called and no socket is opened), and
  * with the gate explicitly on the refresh still works (no over-blocking).
"""
from __future__ import annotations

import os
import socket
import unittest
from unittest import mock

from amazon_linkage_gate import LINKAGE_ENV
from importers.ads_api_importer import AmazonLinkageDisabled as AdsLinkageDisabled
from importers.ads_api_importer import AdsAPIAuth
from importers.sp_api_importer import AmazonLinkageDisabled as SpLinkageDisabled
from importers.sp_api_importer import SPAPIAuth

# Placeholder values only - never a real credential. The conftest keeps
# "test-*" values (they are recognised as placeholders).
_SP_CREDS = {
    "SP_API_CLIENT_ID": "test-key-client",
    "SP_API_CLIENT_SECRET": "test-key-secret",
    "SP_API_REFRESH_TOKEN": "test-key-refresh",
}
_ADS_CREDS = {
    "ADS_CLIENT_ID": "test-key-client",
    "ADS_CLIENT_SECRET": "test-key-secret",
    "ADS_REFRESH_TOKEN": "test-key-refresh",
}


class _NoRequestAllowed:
    """httpx.post and socket creation both explode: the gate must beat them."""

    def __init__(self, test: unittest.TestCase):
        self._test = test

    def __enter__(self):
        self.post = mock.patch(
            "httpx.post", side_effect=AssertionError("request attempted - gate ran too late"))
        self.socket = mock.patch.object(
            socket, "socket", side_effect=AssertionError("socket opened - gate ran too late"))
        self.conn = mock.patch.object(
            socket, "create_connection",
            side_effect=AssertionError("connection opened - gate ran too late"))
        self.post_mock = self.post.start()
        self.socket.start()
        self.conn.start()
        return self.post_mock

    def __exit__(self, *exc_info):
        self.conn.stop()
        self.socket.stop()
        self.post.stop()
        return False


class _AuthGateTestBase:
    AUTH_CLS = None
    CREDS = {}
    REFUSAL = None

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in (LINKAGE_ENV, "ENVIRONMENT")}
        os.environ["ENVIRONMENT"] = "development"
        os.environ.pop(LINKAGE_ENV, None)  # gate OFF (default)
        self.addCleanup(self._restore)

    def _restore(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _auth(self):
        with mock.patch.dict(os.environ, self.CREDS, clear=False):
            return self.AUTH_CLS()

    def test_refresh_refused_before_any_request(self):
        auth = self._auth()
        self.assertTrue(auth.is_configured)
        with _NoRequestAllowed(self) as post:
            with self.assertRaises(self.REFUSAL) as ctx:
                auth._refresh()
        post.assert_not_called()
        self.assertIn("file-only", str(ctx.exception))
        self.assertIsNone(auth._access_token)

    def test_public_get_access_token_refused_too(self):
        # The public entry point is gated by the same check, so a caller that
        # never touches _refresh directly is stopped as well.
        auth = self._auth()
        with _NoRequestAllowed(self) as post:
            with self.assertRaises(self.REFUSAL):
                auth.get_access_token()
        post.assert_not_called()

    def test_gate_on_still_refreshes(self):
        os.environ[LINKAGE_ENV] = "1"
        auth = self._auth()
        fake = mock.MagicMock()
        fake.json.return_value = {"access_token": "token-from-test", "expires_in": 3600}
        with mock.patch("httpx.post", return_value=fake) as post:
            auth._refresh()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(auth._access_token, "token-from-test")


class SPAPIAuthGateTests(_AuthGateTestBase, unittest.TestCase):
    AUTH_CLS = SPAPIAuth
    CREDS = _SP_CREDS
    REFUSAL = SpLinkageDisabled


class AdsAPIAuthGateTests(_AuthGateTestBase, unittest.TestCase):
    AUTH_CLS = AdsAPIAuth
    CREDS = _ADS_CREDS
    REFUSAL = AdsLinkageDisabled


if __name__ == "__main__":
    unittest.main()
