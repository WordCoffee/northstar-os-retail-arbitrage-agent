"""Rate limiting is configured, enforced, and cannot throttle a probe.

Three claims, three tests: the buckets exist, the bucket actually throttles a
caller that exceeds it (with the response headers a client needs), and the four
probe paths bypass the bucket so readiness can never be reported as a 429.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import rate_limiter
from rate_limiter import RateLimitMiddleware


@pytest.fixture(autouse=True)
def _limiter_enabled(monkeypatch):
    """The harness opt-out must not be set for these tests."""
    monkeypatch.delenv("NORTHSTAR_DISABLE_RATE_LIMIT", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


def _app(paths=("/probe",)) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, window_seconds=60)
    for path in paths:
        def handler():  # pragma: no cover - exercised over HTTP
            return {"ok": True}
        app.add_api_route(path, handler, methods=["GET"])
    return app


def test_plan_limits_are_configured_and_anonymous_is_the_tightest():
    limits = RateLimitMiddleware.PLAN_LIMITS
    assert limits["foundation"] == min(limits.values())
    assert all(isinstance(value, int) and value > 0 for value in limits.values())


def test_the_anonymous_bucket_throttles_with_headers():
    client = TestClient(_app())
    limit = RateLimitMiddleware.PLAN_LIMITS["foundation"]
    codes = [client.get("/probe").status_code for _ in range(limit + 1)]
    assert codes[:limit] == [200] * limit
    assert codes[-1] == 429

    response = client.get("/probe")
    assert response.status_code == 429
    assert response.headers["X-RateLimit-Limit"] == str(limit)
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert int(response.headers["Retry-After"]) >= 1
    assert response.json()["error"] == "Rate limit exceeded"


def test_probe_paths_are_exempt_from_the_bucket():
    probes = ("/health", "/health/detailed", "/health/readyz", "/readyz")
    client = TestClient(_app(paths=probes))
    limit = RateLimitMiddleware.PLAN_LIMITS["foundation"]
    for path in probes:
        codes = [client.get(path).status_code for _ in range(limit + 10)]
        assert set(codes) == {200}, (path, set(codes))


def test_the_real_app_mounts_the_limiter():
    import pathlib

    source = (pathlib.Path(__file__).resolve().parent / "main.py").read_text(
        encoding="utf-8", errors="replace")
    assert "app.add_middleware(RateLimitMiddleware" in source


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_the_opt_out_is_refused_in_production_like_environments(monkeypatch, environment):
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("ENVIRONMENT", environment)
    assert rate_limiter.prod_posture_ok() is False
    with pytest.raises(RuntimeError, match="PROD POSTURE"):
        rate_limiter.assert_prod_posture()


def test_the_opt_out_is_honoured_only_outside_production(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert rate_limiter.prod_posture_ok() is True
    client = TestClient(_app())
    codes = [client.get("/probe").status_code for _ in range(40)]
    assert set(codes) == {200}
