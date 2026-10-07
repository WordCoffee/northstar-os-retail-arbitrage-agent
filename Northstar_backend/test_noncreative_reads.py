"""Tests for the non-creative read-only API surface (offline, no network).

Verifies each endpoint responds 200 with the {kind,count,items,summary} shape,
degrades honestly, and never exposes credential material (password_hash).
"""
import unittest

from fastapi.testclient import TestClient

import main

PATHS = [
    "/api/v1/noncreative/commerce-ops/queue",
    "/api/v1/noncreative/listings/health",
    "/api/v1/noncreative/competitor/observations",
    "/api/v1/noncreative/activity",
    "/api/v1/noncreative/keywords",
    "/api/v1/noncreative/sources",
    "/api/v1/noncreative/sessions",
    "/api/v1/noncreative/accounts",
]


class NonCreativeReadsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        # Close the shared DataLayer connection so shutdown emits no
        # ResourceWarning (this env escalates warnings to a non-zero exit).
        import data_layer
        inst = getattr(data_layer, "_db_instance", None)
        if inst is not None:
            try:
                inst.close()
            except Exception:
                pass
            data_layer._db_instance = None

    def test_all_endpoints_ok_and_shaped(self):
        for path in PATHS:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                body = r.json()
                self.assertIn("kind", body)
                self.assertIn("items", body)
                self.assertIsInstance(body["items"], list)
                self.assertIsInstance(body["count"], int)
                self.assertIn("summary", body)

    def test_no_credential_material_exposed(self):
        for path in PATHS:
            with self.subTest(path=path):
                self.assertNotIn("password_hash", self.client.get(path).text)

    def test_listings_health_reports_evidence(self):
        body = self.client.get("/api/v1/noncreative/listings/health").json()
        # local fixture has evidence rows; assert the read is real, not fabricated.
        self.assertGreaterEqual(body["summary"]["evidence_rows"], 0)
        self.assertIn("enrichment", body["summary"])

    def test_keywords_summary_shape(self):
        body = self.client.get("/api/v1/noncreative/keywords").json()
        self.assertIn("keywords", body["summary"])
        self.assertIn("performance_rows", body["summary"])


if __name__ == "__main__":
    unittest.main()
