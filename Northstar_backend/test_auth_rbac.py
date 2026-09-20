"""B2 tests — auth roles, tenancy, and least-privilege admin (auth-rbac/v1)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402


# ---------- roles ----------

def test_valid_roles():
    for r in ("member", "operator", "owner", "admin"):
        assert auth.is_valid_role(r)
    assert not auth.is_valid_role("superuser")
    assert not auth.is_valid_role(None)


def test_role_rank_and_unknown_fail_closed():
    assert auth.role_rank("member") == 0
    assert auth.role_rank("owner") == 2
    assert auth.role_rank("admin") == -1        # separate axis
    assert auth.role_rank("nope") == -1         # unknown fails closed


def test_has_role_hierarchy():
    assert auth.has_role({"role": "owner"}, "owner")
    assert auth.has_role({"role": "owner"}, "member")
    assert not auth.has_role({"role": "member"}, "operator")
    assert not auth.has_role({"role": "member"}, "owner")


def test_has_role_fails_closed_on_unknown():
    assert not auth.has_role({"role": "wizard"}, "member")     # unknown user role
    assert not auth.has_role({"role": "owner"}, "emperor")     # unknown minimum
    assert not auth.has_role({}, "member")
    assert not auth.has_role(None, "member")


def test_admin_does_not_satisfy_tenant_roles():
    # least privilege: admin is not owner/operator of a tenant
    assert auth.is_admin({"role": "admin"})
    assert not auth.has_role({"role": "admin"}, "owner")
    assert not auth.has_role({"role": "admin"}, "member")


# ---------- tenancy ----------

def test_tenant_id_single_tenant_per_account():
    assert auth.tenant_id_of({"id": "acct1"}) == "acct1"
    assert auth.tenant_id_of({"id": "acct1", "tenant_id": "t9"}) == "t9"
    assert auth.tenant_id_of({}) is None       # fail closed
    assert auth.tenant_id_of(None) is None


def test_plan_rank():
    assert auth.plan_rank("foundation") == 0
    assert auth.plan_rank("autothink") == 3
    assert auth.plan_rank("enterprise") == -1


# ---------- least-privilege admin view ----------

def test_admin_account_view_whitelists_only_basic_fields():
    user = {
        "id": "acct1", "email": "o@x.com", "plan": "scout", "created_at": "2026-09-19",
        "password_hash": "$2b$secret", "is_active": 1, "last_login_at": "2026-09-19",
        "access_token": "jwt", "role": "admin", "tenant_id": "acct1",
    }
    view = auth.admin_account_view(user)
    assert set(view) == {"id", "email", "plan", "created_at"}
    for forbidden in ("password_hash", "is_active", "last_login_at", "access_token", "role", "tenant_id"):
        assert forbidden not in view
    assert auth.admin_account_view(None) == {}


# ---------- token claims (additive) ----------

def test_access_token_carries_role_tenant_and_jti():
    tok = auth.create_access_token("acct1", "o@x.com", "mover", role="operator", tenant_id="acct1")
    payload = auth.decode_token(tok)
    assert payload["role"] == "operator"
    assert payload["tenant_id"] == "acct1"
    assert payload["plan"] == "mover"
    assert payload["type"] == "access"
    assert payload["jti"].startswith("sess_")


def test_access_token_unknown_role_fails_closed_to_member():
    tok = auth.create_access_token("acct1", "o@x.com", "scout", role="root")
    assert auth.decode_token(tok)["role"] == "member"


def test_access_token_defaults_preserve_prior_behavior():
    tok = auth.create_access_token("acct1", "o@x.com", "foundation")
    payload = auth.decode_token(tok)
    assert payload["sub"] == "acct1" and payload["email"] == "o@x.com"
    assert payload["tenant_id"] == "acct1"   # defaults to account id
    assert payload["role"] == auth.ROLE_OWNER