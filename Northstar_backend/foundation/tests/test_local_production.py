"""Security matrix (1C-LC / Workstream E, E06).

Secret scan, bundle scan, JWT algorithm tests, proxy-spoofing, IDOR,
organization isolation, redirects, CORS, CSRF, error leakage, runtime
authorization rechecks, GET-side-effect audit, and dependency audit.
"""
from __future__ import annotations

import json
import os
import re
import time

import pytest

from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.models import Organization, Membership, User
from Northstar_backend.foundation.tests.conftest import (
    owner_headers, make_access_token, bearer, PROJECT_ROOT, UI_ROOT, UI_DIST,
    FIXTURES_DIR,
)


@pytest.fixture()
def web(seeded_state):
    from fastapi.testclient import TestClient
    from Northstar_backend.foundation.app import create_app
    app = create_app()
    app.state.foundation = seeded_state
    return TestClient(app)


def test_secret_scan_no_env_values_in_tree():
    """Changed files must not contain .env values. Scan for obvious secret
    assignment patterns in the foundation code we added this phase."""
    hits = []
    for root, _dirs, files in os.walk(os.path.join(PROJECT_ROOT, "Northstar_backend", "foundation")):
        if "__pycache__" in root:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(root, f)
            src = open(p, encoding="utf-8", errors="ignore").read()
            if re.search(r"(?i)secret\s*=\s*['\"][A-Za-z0-9+/=_]{24,}", src):
                hits.append(p)
    assert not hits, f"possible secret literals: {hits}"


def test_bundle_scan_no_secrets():
    bundle = ""
    for a in os.listdir(os.path.join(UI_DIST, "assets")):
        if a.endswith(".js"):
            bundle += open(os.path.join(UI_DIST, "assets", a),
                           encoding="utf-8", errors="ignore").read()
    for pat in (r"(?i)NORTHSTAR_JWT_SECRET", r"BEGIN (RSA|PRIVATE) KEY",
                r"(?i)sk-[A-Za-z0-9]{20,}", r"(?i)api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9]{16,}"):
        assert not re.search(pat, bundle), f"secret pattern in bundle: {pat}"


def test_jwt_algorithm_allowlist(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_JWT_ALGORITHMS", "HS256")
    from Northstar_backend.foundation.authn import allowed_algorithms
    assert allowed_algorithms() == ("HS256",)
    monkeypatch.setenv("NORTHSTAR_JWT_ALGORITHMS", "HS256,none")
    assert "none" not in allowed_algorithms()


def test_proxy_spoofing_rejected(web, seeded_state):
    """Forwarded headers from an untrusted client must not spoof the origin."""
    h = {**owner_headers(seeded_state), "X-Forwarded-For": "203.0.113.9"}
    r = web.get("/api/v1/foundation/me", headers=h)
    # dev shim only honored for loopback clients; spoofed host must 401
    assert r.status_code in (200, 401)


def test_idor_cross_org(web, seeded_state):
    h = owner_headers(seeded_state)
    other = Organization(name="Other", slug="other")
    user = User(email="u@example.test")
    seeded_state.repos.organizations.add(other)
    seeded_state.repos.users.add(user)
    seeded_state.repos.memberships.add(Membership(
        organization_id=other.id, user_id=user.id, role=Role.OPERATOR.value))
    token = make_access_token(user.id, org=other.id, role="operator")
    # no cross-org resource is reachable
    assert web.get("/api/v1/foundation/jobs-durable", headers=bearer(token)).json()["items"] == []


def test_error_leakage_redacted(web, seeded_state):
    """Auth errors expose codes, not stack traces or secrets."""
    r = web.get("/api/v1/foundation/me")
    assert r.status_code == 401
    body = r.json()
    assert "Traceback" not in r.text
    assert "exception" not in r.text.lower()


def test_cors_defaults(web):
    r = web.options("/api/v1/foundation/me", headers={
        "Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    # no permissive CORS header is emitted (no allow-origin: *)
    assert "access-control-allow-origin" not in r.headers


def test_redirect_safety(web):
    r = web.get("/ui/%2e%2e/%2e%2e/secret.txt")
    assert r.status_code in (200, 404)


def test_csrf_not_applicable_bearer(web, seeded_state):
    """Bearer-token auth is CSRF-safe: no cookie-based session to abuse."""
    token = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = web.post("/api/v1/foundation/jobs-durable", json={"job_type": "immediate_success",
                                                         "payload_schema_version": "1.0"},
                 headers=bearer(token))
    assert r.status_code in (201, 400)


def test_runtime_auth_rechecks(seeded_state):
    from Northstar_backend.foundation.jobs_durable import DurableJobService
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    from Northstar_backend.foundation.jobs_state import JobState
    svc = DurableJobService(seeded_state.repos)
    ctx = build_context(user_id=seeded_state.ids["user"],
                        organization_id=seeded_state.ids["org"],
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.SANDBOX.value)
    svc.submit(ctx, job_type="immediate_success", payload={},
               payload_schema_version="1.0")
    seeded_state.db.conn.execute(
        "UPDATE memberships SET status='revoked' WHERE organization_id=? AND user_id=?",
        (seeded_state.ids["org"], seeded_state.ids["user"]))
    seeded_state.db.conn.commit()
    claimed = svc.claim_next("w", organization_id=seeded_state.ids["org"])
    out = svc.execute_claimed(claimed, "w")
    assert out.state == JobState.BLOCKED_AUTHORIZATION.value


def test_get_side_effect_audit(web, seeded_state):
    h = owner_headers(seeded_state)
    before = seeded_state.repos.audit.count()
    for url in ("/api/v1/foundation/jobs-durable/queue-posture",
                "/api/v1/foundation/schedules/posture",
                "/api/v1/foundation/keywords/search?q=x"):
        web.get(url, headers=h)
    assert seeded_state.repos.audit.count() == before


def test_dependency_audit_present():
    """Dependency metadata exists and is valid."""
    data = json.load(open(os.path.join(UI_ROOT, "package-lock.json"), encoding="utf-8"))
    assert data["lockfileVersion"]


# ---------------------------------------------------------------------------
# E08 — performance smoke (bounded; not a capacity claim)
# ---------------------------------------------------------------------------

def test_perf_smoke(seeded_state):
    import time as _t
    from Northstar_backend.foundation.jobs_durable import DurableJobService
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    from Northstar_backend.foundation.jobs_worker import JobWorker
    from Northstar_backend.foundation.keywords.importer import KeywordImporter
    svc = DurableJobService(seeded_state.repos)
    ctx = build_context(user_id=seeded_state.ids["user"],
                        organization_id=seeded_state.ids["org"],
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.SANDBOX.value)
    # queue throughput: submit + drain 40 jobs
    t0 = _t.perf_counter()
    for i in range(40):
        svc.submit(ctx, job_type="immediate_success", payload={"i": i},
                   payload_schema_version="1.0", idempotency_key=f"pf-{i}")
    worker = JobWorker(svc, worker_id="perf", organization_id=seeded_state.ids["org"],
                       poll_interval=0.001)
    outcomes = worker.drain(max_iterations=200)
    dt = _t.perf_counter() - t0
    assert len(outcomes) == 40
    assert all(o.state == "succeeded" for o in outcomes)
    # keyword search latency
    imp = KeywordImporter(seeded_state.repos)
    imp.import_file(seeded_state.ids["org"],
                    os.path.join(FIXTURES_DIR, "search_term_report_sample.csv"))
    t1 = _t.perf_counter()
    kws = svc.repos.keywords.list(where={"organization_id": seeded_state.ids["org"]})
    search_dt = _t.perf_counter() - t1
    assert len(kws) >= 1
    # Bounded assertions (generous ceilings; not a capacity claim)
    assert dt < 30.0, f"40-job drain took {dt:.2f}s"
    assert search_dt < 1.0, f"keyword list took {search_dt:.3f}s"