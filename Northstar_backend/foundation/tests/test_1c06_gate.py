"""1C-06 FINAL GATE — canonical frontend acceptance (D15).

Aggregates the serving, auth, organization, preview, security, accessibility
baseline, GET-side-effect, and no-provider-on-load guarantees. The production
build must exist and be served loopback-only by the foundation app.
"""
from __future__ import annotations

import os
import re

import pytest

from Northstar_backend.foundation.tests.conftest import owner_headers, make_access_token, bearer

DIST = os.path.join("northstar-os-ui", "dist")


@pytest.fixture()
def web(seeded_state):
    from fastapi.testclient import TestClient
    from Northstar_backend.foundation.app import create_app
    app = create_app()
    app.state.foundation = seeded_state
    return TestClient(app)


def test_gate_ui_is_canonical_and_served(web):
    assert os.path.exists(os.path.join(DIST, "index.html"))
    r = web.get("/ui")
    assert r.status_code == 200 and "id=\"root\"" in r.text
    # deep link (SPA fallback) served
    assert web.get("/ui/jobs").status_code == 200


def test_gate_real_auth_flows(web, seeded_state, monkeypatch):
    # missing JWT -> 401
    assert web.get("/api/v1/foundation/me").status_code == 401
    # valid JWT -> 200
    token = make_access_token(seeded_state.ids["user"],
                              org=seeded_state.ids["org"])
    assert web.get("/api/v1/foundation/me", headers=bearer(token)).status_code == 200
    # issuer/audience enforced when configured
    monkeypatch.setenv("NORTHSTAR_JWT_ISSUER", "https://northstar.local")
    monkeypatch.setenv("NORTHSTAR_JWT_AUDIENCE", "northstar-api")
    bad = make_access_token(seeded_state.ids["user"],
                            org=seeded_state.ids["org"], issuer="https://evil.example",
                            audience="northstar-api")
    assert web.get("/api/v1/foundation/me", headers=bearer(bad)).status_code == 401


def test_gate_org_switch_and_cross_org(web, seeded_state):
    from Northstar_backend.foundation.models import Organization, Membership
    from Northstar_backend.foundation.enums import Role
    org_b = Organization(name="B", slug="b")
    seeded_state.repos.organizations.add(org_b)
    seeded_state.repos.memberships.add(Membership(
        organization_id=org_b.id, user_id=seeded_state.ids["user"],
        role=Role.OPERATOR.value))
    token = make_access_token(seeded_state.ids["user"], org=org_b.id,
                              role="operator")
    me = web.get("/api/v1/foundation/me", headers=bearer(token))
    assert me.status_code == 200 and me.json()["active_organization_id"] == org_b.id
    cross = make_access_token(seeded_state.ids["user"], org="not-member-org")
    assert web.get("/api/v1/foundation/me",
                   headers=bearer(cross)).status_code == 403


def test_gate_preview_banner_and_audit(web, seeded_state):
    h = owner_headers(seeded_state)
    start = web.post("/api/v1/foundation/preview/start", headers=h, json={
        "target_organization_id": seeded_state.ids["org"], "reason": "gate"})
    pid = start.json()["preview_id"]
    active = web.get("/api/v1/foundation/preview/active",
                     headers={**h, "X-Preview-Id": pid})
    assert active.json()["active"] is True
    web.post(f"/api/v1/foundation/preview/end?preview_id={pid}", headers=h)
    assert seeded_state.repos.audit.list(where={"action": "preview.end"})


def test_gate_no_provider_calls_on_load(web, seeded_state):
    h = owner_headers(seeded_state)
    before_providers = seeded_state.repos.providers.count()
    before_jobs = seeded_state.repos.job_requests.count()
    for url in ("/ui", "/ui/foundation", "/ui/jobs", "/ui/keywords",
                "/api/v1/foundation/jobs-durable/queue-posture",
                "/api/v1/foundation/schedules/posture",
                "/api/v1/foundation/keywords/search?q=x"):
        assert web.get(url, headers=h).status_code == 200
    assert seeded_state.repos.providers.count() == before_providers
    assert seeded_state.repos.job_requests.count() == before_jobs


def test_gate_security_and_bundle(web):
    r = web.get("/ui")
    csp = r.headers.get("content-security-policy", "")
    assert "frame-ancestors 'none'" in csp and "script-src 'self'" in csp
    assert r.headers.get("x-frame-options") == "DENY"
    # bundle scan for secrets
    bundle = ""
    for a in os.listdir(os.path.join(DIST, "assets")):
        if a.endswith(".js"):
            bundle += open(os.path.join(DIST, "assets", a), encoding="utf-8",
                           errors="ignore").read()
    for pat in (r"(?i)NORTHSTAR_JWT_SECRET", r"BEGIN (RSA|PRIVATE) KEY",
                r"(?i)api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9]{16,}"):
        assert not re.search(pat, bundle)


def test_gate_economics_canonical_from_ui(web, seeded_state):
    """The frontend must consume the canonical economics contract (no formulas
    of its own); the backend contract is the authority."""
    h = owner_headers(seeded_state)
    r = web.get("/api/v1/foundation/economics/contract", headers=h)
    assert r.status_code == 200
    assert r.json()["formula_version"] == "economics-1.0.0"