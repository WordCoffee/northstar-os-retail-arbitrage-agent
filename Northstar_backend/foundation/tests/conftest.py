"""Foundation test fixtures — fully offline, DB-isolated, provider-isolated.

Authentication (Phase 1C-01):
- Tests run in ENVIRONMENT=development so BOTH real JWT auth and the local dev
  shim are exercised, without weakening staging/production behavior.
- A placeholder JWT secret ("test-...") is used; the ancestor conftest preserves
  placeholder values, so it is never scrubbed and is never a real credential.

Each test gets a disposable temp SQLite DB. No network, no secrets, no writes to
any production-like database.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

# --- test environment (set at import, before fixtures) -----------------------
os.environ["ENVIRONMENT"] = "development"
os.environ.setdefault("NS_FOUNDATION_BIND_HOST", "127.0.0.1")
os.environ.setdefault("NORTHSTAR_JWT_SECRET", "test-foundation-jwt-secret-not-real")


def make_access_token(user_id: str, *, org: str | None = None,
                      role: str = "organization_owner", ttl_seconds: int = 3600,
                      secret: str | None = None, algorithm: str = "HS256",
                      issuer: str | None = None, audience: str | None = None,
                      jti: str | None = None, token_type: str = "access",
                      extra: dict | None = None) -> str:
    from Northstar_backend.foundation.authn import jwt_secret
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "jti": jti or f"sess_test_{user_id}",
    }
    if org:
        payload["tenant_id"] = org
    if role:
        payload["role"] = role
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, secret or jwt_secret(), algorithm=algorithm)


@pytest.fixture()
def state():
    fd, path = tempfile.mkstemp(prefix="ns_found_test_", suffix=".db")
    os.close(fd)
    from Northstar_backend.foundation.api.state import FoundationState
    st = FoundationState.build(path)
    try:
        yield st
    finally:
        st.close()
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture()
def seeded_state(state):
    """State with a user, an org, and a membership (owner role)."""
    from Northstar_backend.foundation.models import Organization, User, Membership
    from Northstar_backend.foundation.enums import Role
    org = Organization(name="Acme Retail", slug="acme")
    user = User(email="owner@example.test", display_name="Owner")
    state.repos.organizations.add(org)
    state.repos.users.add(user)
    state.repos.memberships.add(Membership(organization_id=org.id, user_id=user.id,
                                           role=Role.ORGANIZATION_OWNER.value))
    state.ids = {"org": org.id, "user": user.id}
    return state


@pytest.fixture()
def client(seeded_state):
    from fastapi.testclient import TestClient
    from Northstar_backend.foundation.app import create_app
    app = create_app()
    app.state.foundation = seeded_state
    return TestClient(app)


def owner_headers(seeded_state, env="production"):
    """Legacy dev-shim headers (valid only in local development)."""
    return {
        "X-User-Id": seeded_state.ids["user"],
        "X-Org-Id": seeded_state.ids["org"],
        "X-Role": "organization_owner",
        "X-Env": env,
    }


def bearer(token: str, **extra) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    h.update(extra)
    return h