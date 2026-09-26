"""PostgreSQL integration tests (Phase 1C-02 Stage E).

Runs ONLY when FOUNDATION_DB_URL points at a reachable PostgreSQL (the disposable
ephemeral instance). Skipped otherwise, so it never affects the offline SQLite
suite. Asserts the foundation really uses PostgreSQL (no silent SQLite fallback).
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import pytest

PG_URL = os.environ.get("FOUNDATION_DB_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="FOUNDATION_DB_URL not set (PostgreSQL integration)")

DISPOSABLE_DB = "northstar_phase1c02_ephemeral"
DISPOSABLE_USER = "northstar_phase1c02_test"


def _assert_disposable_target():
    u = urlparse(PG_URL)
    assert u.hostname == "127.0.0.1", f"host must be loopback, got {u.hostname}"
    assert u.username == DISPOSABLE_USER
    assert (u.path or "").lstrip("/") == DISPOSABLE_DB
    assert u.port == 55432


@pytest.fixture(scope="module")
def pg_state():
    _assert_disposable_target()
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.db import SCHEMA
    st = FoundationState.build()
    # clean disposable DB for a deterministic repository run
    tables = ", ".join(SCHEMA.keys())
    st.db.conn.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
    st.db.conn.commit()
    st.seed()
    yield st
    st.close()


def test_backend_is_postgres_not_sqlite(pg_state):
    assert type(pg_state.db).__name__ == "PostgresFoundationDB"
    assert pg_state.db.backend == "postgresql"


def test_server_is_postgres15_and_disposable(pg_state):
    info = pg_state.db.server_info()
    assert info["version"].startswith("PostgreSQL 15")
    assert info["database"] == DISPOSABLE_DB
    assert info["user"] == DISPOSABLE_USER


def test_repositories_roundtrip(pg_state):
    from Northstar_backend.foundation.models import Organization, User, Membership
    from Northstar_backend.foundation.enums import Role
    org = Organization(name="PG Org", slug="pg-org")
    user = User(email="pg@example.test")
    pg_state.repos.organizations.add(org)
    pg_state.repos.users.add(user)
    pg_state.repos.memberships.add(Membership(
        organization_id=org.id, user_id=user.id,
        role=Role.ORGANIZATION_OWNER.value, status="active"))
    assert pg_state.repos.organizations.get(org.id)["name"] == "PG Org"
    mem = pg_state.repos.memberships.for_user(user.id)
    assert mem and mem[0]["role"] == Role.ORGANIZATION_OWNER.value
    pg_state.ids = {"org": org.id, "user": user.id}


def test_audit_insert_on_postgres(pg_state):
    row = pg_state.audit.record(action="pg.test", organization_id=pg_state.ids["org"],
                                after_meta={"step": 1, "nested": {"a": 2}})
    got = pg_state.repos.audit.get(row["id"])
    assert got is not None
    # jsonb normalized back to a JSON string for repository parity
    assert json.loads(got["after_meta"])["nested"]["a"] == 2


def test_ui_preference_roundtrip_postgres(pg_state):
    pg_state.repos.ui_prefs.set_pref("pu", pg_state.ids["org"], "pinned_open", {"open": True})
    val = pg_state.repos.ui_prefs.get_pref("pu", pg_state.ids["org"], "pinned_open")
    parsed = json.loads(val) if isinstance(val, str) else val
    assert parsed == {"open": True}


def test_usage_shadow_postgres(pg_state):
    led = pg_state.usage
    row = led.record_local_free(organization_id=pg_state.ids["org"], service="autothink")
    assert row["credits_debited_shadow"] == 0.0
    bal = led.derived_balance(pg_state.ids["org"], granted=100.0)
    assert bal["debits_applied"] is False and bal["label"] == "SHADOW ESTIMATE"


def test_provider_registry_postgres(pg_state):
    row = pg_state.providers.execute_read("fixture_price", {"fixture_key": "x"})
    assert row.ok is False and row.error_class == "provider_disabled"


def test_observation_jsonb_roundtrip_postgres(pg_state):
    from Northstar_backend.foundation.provenance import make_observation
    from Northstar_backend.foundation.enums import ObservationType, ProvenanceClass
    obs = make_observation(observation_type=ObservationType.PRICE,
                           observed_value={"amount": 9.99, "tags": ["a", "b"], "u": "café"},
                           provenance_class=ProvenanceClass.CACHED)
    pg_state.repos.observations.add(obs)
    got = pg_state.repos.observations.get(obs.id)
    parsed = json.loads(got["observed_value"])
    assert parsed["tags"] == ["a", "b"] and parsed["u"] == "café"


# --- authentication against PostgreSQL ---------------------------------------

def _client_and_headers(pg_state):
    from fastapi.testclient import TestClient
    from Northstar_backend.foundation.app import create_app
    from Northstar_backend.foundation.tests.conftest import make_access_token, bearer
    app = create_app()
    app.state.foundation = pg_state
    token = make_access_token(pg_state.ids["user"], org=pg_state.ids["org"])
    return TestClient(app), bearer(token), token


def test_auth_me_resolves_role_from_postgres(pg_state):
    client, h, _ = _client_and_headers(pg_state)
    r = client.get("/api/v1/foundation/me", headers=h)
    assert r.status_code == 200
    assert r.json()["role"] == "organization_owner"


def test_membership_resolution_and_cross_org_postgres(pg_state):
    from Northstar_backend.foundation.models import Organization
    client, h, tok = _client_and_headers(pg_state)
    other = Organization(name="Other", slug="other"); pg_state.repos.organizations.add(other)
    r = client.get("/api/v1/foundation/organizations", headers={**h, "X-Org-Id": other.id})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "cross_organization_access_denied"


def test_suspended_membership_denied_postgres(pg_state):
    client, h, _ = _client_and_headers(pg_state)
    rows = pg_state.repos.memberships.for_user(pg_state.ids["user"])
    pg_state.db.conn.execute("UPDATE memberships SET status='suspended' WHERE id=%s",
                             (rows[0]["id"],))
    pg_state.db.conn.commit()
    r = client.get("/api/v1/foundation/me", headers=h)
    assert r.status_code == 403
    pg_state.db.conn.execute("UPDATE memberships SET status='active' WHERE id=%s",
                             (rows[0]["id"],))
    pg_state.db.conn.commit()


def test_session_revocation_postgres(pg_state):
    from fastapi.testclient import TestClient
    from Northstar_backend.foundation.app import create_app
    from Northstar_backend.foundation.tests.conftest import make_access_token, bearer
    app = create_app(); app.state.foundation = pg_state
    c = TestClient(app)
    tok = make_access_token(pg_state.ids["user"], org=pg_state.ids["org"], jti="pg_revoke_1")
    h = bearer(tok)
    assert c.get("/api/v1/foundation/me", headers=h).status_code == 200
    assert c.post("/api/v1/foundation/session/revoke?jti=pg_revoke_1", headers=h).status_code == 200
    r = c.get("/api/v1/foundation/me", headers=h)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "session_revoked"


def test_owner_bootstrap_postgres(pg_state):
    from Northstar_backend.foundation.bootstrap import bootstrap_owner
    res = bootstrap_owner(pg_state, org_name="Boot Org", user_email="boot@example.test")
    assert res["role"] == "organization_owner"
    events = pg_state.repos.audit.list(where={"action": "bootstrap.owner"})
    assert events