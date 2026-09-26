"""Initial-owner bootstrap tests (Phase 1C-01F)."""
from __future__ import annotations

import pytest

from Northstar_backend.foundation.bootstrap import bootstrap_owner, BootstrapError
from Northstar_backend.foundation.enums import Role


def test_bootstrap_creates_org_user_membership(state):
    res = bootstrap_owner(state, org_name="Acme", user_email="owner@acme.test")
    assert res["role"] == Role.ORGANIZATION_OWNER.value
    assert res["created"] is True
    assert state.repos.organizations.count() == 1
    assert state.repos.memberships.count() == 1


def test_bootstrap_is_audited(state):
    bootstrap_owner(state, org_name="Acme", user_email="owner@acme.test")
    events = state.repos.audit.list()
    assert any(e["action"] == "bootstrap.owner" for e in events)


def test_bootstrap_replay_refused_without_recover(state):
    bootstrap_owner(state, org_name="Acme", user_email="owner@acme.test")
    with pytest.raises(BootstrapError):
        bootstrap_owner(state, org_name="Acme", user_email="owner2@acme.test")


def test_bootstrap_recover_allows_explicit_add(state):
    bootstrap_owner(state, org_name="Acme", user_email="owner@acme.test")
    res = bootstrap_owner(state, org_name="Acme", user_email="owner2@acme.test",
                          recover=True)
    assert res["created"] is True


def test_bootstrap_idempotent_same_user(state):
    r1 = bootstrap_owner(state, org_name="Acme", user_email="owner@acme.test")
    r2 = bootstrap_owner(state, org_name="Acme", user_email="owner@acme.test",
                         recover=True)
    assert r1["user_id"] == r2["user_id"]
    assert r2["created"] is False
    assert state.repos.memberships.count() == 1


def test_bootstrap_requires_inputs(state):
    with pytest.raises(BootstrapError):
        bootstrap_owner(state, org_name="", user_email="x@y.test")
    with pytest.raises(BootstrapError):
        bootstrap_owner(state, org_name="Acme", user_email="")


def test_bootstrap_audit_masks_email(state):
    bootstrap_owner(state, org_name="Acme", user_email="secretperson@acme.test")
    ev = [e for e in state.repos.audit.list() if e["action"] == "bootstrap.owner"][0]
    assert "secretperson@" not in (ev["after_meta"] or "")