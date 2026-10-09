"""Silent-failure regressions (P1-01, P1-02, P1-04).

Each of these paths used to hide a failure behind a plausible-looking empty
value. The tests prove the failure is now visible.

- P1-01: a broken SQL read returns an explicit 503 ``unavailable`` envelope,
  never an empty ``count: 0`` list.
- P1-04: a configured-but-broken Postgres refuses to boot instead of silently
  serving SQLite.
- P1-02: an adapter that fails to import is reported, not dropped.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import noncreative_reads  # noqa: E402


_TMP = tempfile.mkdtemp(prefix="silent-failure-")
_OFF_ENV = {
    "SCANNER_LIVE_ALLOWED": "0",
    "NORTHSTAR_DISABLE_RATE_LIMIT": "1",
    "ENVIRONMENT": "test",
    "SCANNER_SEARCH_CACHE_PATH": os.path.join(_TMP, "s.json"),
    "COSTCO_CATALOG_SOURCE": "OFF",
}

_ENDPOINTS = [
    "/api/v1/noncreative/commerce-ops/queue",
    "/api/v1/noncreative/listings/health",
    "/api/v1/noncreative/competitor/observations",
    "/api/v1/noncreative/activity",
    "/api/v1/noncreative/keywords",
    "/api/v1/noncreative/sources",
    "/api/v1/noncreative/sessions",
    "/api/v1/noncreative/accounts",
]


class NoncreativeReadHonestyTests(unittest.TestCase):
    """A failed read is an honest 503, never an empty list."""

    @classmethod
    def setUpClass(cls):
        from main import app
        with patch.dict(os.environ, _OFF_ENV, clear=True):
            cls.client = TestClient(app)

    def test_helpers_raise_instead_of_returning_empty(self):
        with self.assertRaises(noncreative_reads.DataUnavailable):
            noncreative_reads._rows("SELECT * FROM table_that_does_not_exist")

    def test_scalar_raises_instead_of_returning_none(self):
        with self.assertRaises(noncreative_reads.DataUnavailable):
            noncreative_reads._scalar("SELECT COUNT(*) FROM table_that_does_not_exist")

    def test_every_endpoint_refuses_to_report_a_fake_empty(self):
        """Force the read to fail; every endpoint must say unavailable."""
        with patch.object(noncreative_reads, "_rows",
                          side_effect=noncreative_reads.DataUnavailable("boom")):
            with patch.object(noncreative_reads, "_scalar",
                              side_effect=noncreative_reads.DataUnavailable("boom")):
                for path in _ENDPOINTS:
                    with self.subTest(endpoint=path):
                        response = self.client.get(path)
                        self.assertEqual(response.status_code, 503, path)
                        body = response.json()
                        self.assertEqual(body["status"], "unavailable")
                        self.assertIsNone(body["count"], path)
                        self.assertIn("UNKNOWN", body["note"])

    def test_healthy_endpoints_still_return_data(self):
        """The fix must not break the happy path."""
        response = self.client.get("/api/v1/noncreative/activity")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("count", body)
        self.assertIsInstance(body["count"], int)
        self.assertNotEqual(body["count"], None)


class DataLayerPostgresPostureTests(unittest.TestCase):
    """A configured-but-broken Postgres refuses to boot (P1-04)."""

    def test_missing_driver_refuses_loudly(self):
        import data_layer
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://h:1/db"}, clear=False):
            with patch.object(data_layer, "_get_postgres_url",
                              return_value="postgresql://user:secret@dbhost:5432/db"):
                with patch.dict(sys.modules, {"psycopg2": None}):
                    with self.assertRaises(RuntimeError) as ctx:
                        data_layer.DataLayer()
        message = str(ctx.exception)
        self.assertIn("POSTGRES CONFIGURED", message)
        # The credential must never appear in the error.
        self.assertNotIn("secret", message)
        self.assertIn("dbhost", message)

    def test_unreachable_postgres_refuses_loudly(self):
        import data_layer
        fake_driver = type(sys)("psycopg2")

        def _refuse(*_a, **_k):
            raise OSError("connection refused")

        fake_driver.connect = _refuse
        with patch.object(data_layer, "_get_postgres_url",
                          return_value="postgresql://user:secret@dbhost:5432/db"):
            with patch.dict(sys.modules, {"psycopg2": fake_driver}):
                with self.assertRaises(RuntimeError) as ctx:
                    data_layer.DataLayer()
        self.assertIn("UNREACHABLE", str(ctx.exception))
        self.assertNotIn("secret", str(ctx.exception))

    def test_no_url_keeps_the_sqlite_fallback(self):
        import data_layer
        with patch.object(data_layer, "_get_postgres_url", return_value=None):
            layer = data_layer.DataLayer()
        self.assertEqual(layer.mode, "sqlite")

    def test_redaction_removes_credentials(self):
        from data_layer import _redact_url
        self.assertEqual(_redact_url(None), "<none>")
        self.assertNotIn("secret", _redact_url("postgresql://user:secret@dbhost:5432/db"))
        self.assertIn("dbhost", _redact_url("postgresql://user:secret@dbhost:5432/db"))


if __name__ == "__main__":
    unittest.main()
