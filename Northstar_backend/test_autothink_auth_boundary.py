"""Route-level auth boundary for /api/autothink/* (P0-04, closed 2026-10-09).

Proves the exact failure the audit found: an unauthenticated caller could
drive model runs and read every tenant's history. Now every route on that
surface refuses with 401 until a real session is presented.

The user lookup is patched so no operator database is touched and no
credential is read; the token itself is minted with the real signer.
"""

import test_network_guard  # noqa: F401
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import main

_TMP = tempfile.mkdtemp(prefix="autothink-auth-")

_OFF_ENV = {
    "SCANNER_LIVE_ALLOWED": "0",
    "NORTHSTAR_DISABLE_RATE_LIMIT": "1",
    "ENVIRONMENT": "test",
    "NORTHSTAR_JWT_SECRET": "unit-test-signing-key-not-a-real-secret",
}


def _off_env():
    env = dict(_OFF_ENV)
    env["SCANNER_SEARCH_CACHE_PATH"] = os.path.join(_TMP, "s.json")
    env["COSTCO_CATALOG_SOURCE"] = "OFF"
    return env


class AutothinkAuthBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = _off_env()
        cls._env = patch.dict(os.environ, env, clear=True)
        cls._env.start()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        cls._env.stop()

    ROUTES_NO_SESSION = [
        ("get", "/api/autothink/history"),
        ("get", "/api/autothink/models"),
        ("get", "/api/autothink/usage"),
        ("get", "/api/autothink/jobs/atrun_fake"),
        ("post", "/api/autothink/run"),
        ("post", "/api/autothink/cancel"),
    ]

    def test_every_route_refuses_without_a_session(self):
        for method, path in self.ROUTES_NO_SESSION:
            with self.subTest(route=path):
                if method == "get":
                    response = self.client.get(path)
                else:
                    response = self.client.post(
                        path, json={"query": "x", "run_id": "atrun_fake"})
                self.assertEqual(response.status_code, 401, path)

    def test_garbage_bearer_token_is_refused(self):
        response = self.client.get(
            "/api/autothink/history",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        self.assertEqual(response.status_code, 401)

    @staticmethod
    def _token(user: str, tenant: str) -> str:
        return auth.create_access_token(
            user, user + "@test.local", "autothink",
            role="owner", tenant_id=tenant,
        )

    def _as_tenant(self, user: str, tenant: str):
        """Patch user lookup for the whole request (token mint AND call)."""
        return patch.object(auth, "get_user", return_value={
            "id": user, "email": user + "@test.local", "plan": "autothink",
            "role": "owner", "tenant_id": tenant,
        })

    def test_valid_session_reaches_the_route(self):
        with self._as_tenant("user-a", "tenant-a"):
            response = self.client.get(
                "/api/autothink/history",
                headers={"Authorization": "Bearer " + self._token("user-a", "tenant-a")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["org_id"], "tenant-a")

    def test_models_route_requires_a_session_too(self):
        with self._as_tenant("user-a", "tenant-a"):
            response = self.client.get(
                "/api/autothink/models",
                headers={"Authorization": "Bearer " + self._token("user-a", "tenant-a")},
            )
        self.assertEqual(response.status_code, 200)

    def test_two_tenants_have_isolated_usage(self):
        with self._as_tenant("user-a", "tenant-a"):
            usage_a = self.client.get(
                "/api/autothink/usage",
                headers={"Authorization": "Bearer " + self._token("user-a", "tenant-a")},
            ).json()
        with self._as_tenant("user-b", "tenant-b"):
            usage_b = self.client.get(
                "/api/autothink/usage",
                headers={"Authorization": "Bearer " + self._token("user-b", "tenant-b")},
            ).json()
        self.assertEqual(usage_a["org_id"], "tenant-a")
        self.assertEqual(usage_b["org_id"], "tenant-b")
        self.assertNotEqual(usage_a["org_id"], usage_b["org_id"])


if __name__ == "__main__":
    unittest.main()
