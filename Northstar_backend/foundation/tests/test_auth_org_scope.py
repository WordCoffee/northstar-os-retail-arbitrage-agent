"""Organization resolution, role-from-DB, cross-org denial, and preview
authorization (Phase 1C-01)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from Northstar_backend.foundation.models import Organization, Membership
from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.tests.conftest import make_access_token, bearer, owner_headers


def _two_orgs(seeded_state):
    other = Organization(name="Other Co", slug="other")
    seeded_state.repos.organizations.add(other)
    seeded_state.ids["other_org"] = other.id
    return other


def test_role_resolved_from_membership_not_header(client, seeded_state):
    # Dev shim sends X-Role: internal_platform_admin, but the DB membership is
    # organization_owner -> role must be organization_owner (header ignored).
    headers = owner_headers(seeded_state)
    headers["X-Role"] = "internal_platform_admin"
    r = client.get("/api/v1/foundation/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "organization_owner"
    assert "platform_admin" not in r.json()["permissions"]


def test_cross_org_access_denied(client, seeded_state):
    other = _two_orgs(seeded_state)
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = client.get("/api/v1/foundation/organizations",
                   headers=bearer(tok, **{"X-Org-Id": other.id}))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "cross_organization_access_denied"


def test_member_org_access_allowed(client, seeded_state):
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = client.get("/api/v1/foundation/me", headers=bearer(tok))
    assert r.status_code == 200
    assert r.json()["active_organization_id"] == seeded_state.ids["org"]


def test_token_org_claim_used_when_no_header(client, seeded_state):
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = client.get("/api/v1/foundation/me", headers=bearer(tok))
    assert r.json()["active_organization_id"] == seeded_state.ids["org"]


def test_platform_admin_can_access_other_org(state):
    # A platform admin (membership in their own org with admin role) may select
    # another org.
    from Northstar_backend.foundation.models import User
    from Northstar_backend.foundation.app import create_app
    home = Organization(name="Home", slug="home")
    other = Organization(name="Other", slug="other")
    user = User(email="admin@example.test")
    for o in (home, other):
        state.repos.organizations.add(o)
    state.repos.users.add(user)
    state.repos.memberships.add(Membership(
        organization_id=home.id, user_id=user.id,
        role=Role.INTERNAL_PLATFORM_ADMIN.value))
    app = create_app()
    app.state.foundation = state
    c = TestClient(app)
    tok = make_access_token(user.id, org=home.id)
    r = c.get("/api/v1/foundation/organizations",
              headers=bearer(tok, **{"X-Org-Id": other.id}))
    assert r.status_code == 200


def test_preview_target_org_must_be_authorized(client, seeded_state):
    other = _two_orgs(seeded_state)
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = client.post("/api/v1/foundation/preview/start",
                    headers=bearer(tok),
                    json={"target_organization_id": other.id, "reason": "support"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "preview_org_denied"


def test_preview_authorized_org_and_read_only(client, seeded_state):
    tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = client.post("/api/v1/foundation/preview/start",
                    headers=bearer(tok),
                    json={"target_organization_id": seeded_state.ids["org"],
                          "reason": "support"})
    assert r.status_code == 200
    pid = r.json()["preview_id"]
    h = bearer(tok, **{"X-Preview-Id": pid})
    env = client.get("/api/v1/foundation/environment", headers=h).json()
    assert env["is_preview"] is True
    assert env["writes_allowed"] is False


def test_preview_not_owned_by_other_operator(client, seeded_state):
    from Northstar_backend.foundation.models import User
    other_user = User(email="other@example.test")
    seeded_state.repos.users.add(other_user)
    seeded_state.repos.memberships.add(Membership(
        organization_id=seeded_state.ids["org"], user_id=other_user.id,
        role=Role.OPERATOR.value))
    owner_tok = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    pid = client.post("/api/v1/foundation/preview/start", headers=bearer(owner_tok),
                      json={"target_organization_id": seeded_state.ids["org"],
                            "reason": "x"}).json()["preview_id"]
    other_tok = make_access_token(other_user.id, org=seeded_state.ids["org"])
    r = client.get("/api/v1/foundation/environment",
                   headers=bearer(other_tok, **{"X-Preview-Id": pid}))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "preview_not_owned"