"""Approval foundation tests (owner decision 7)."""
from __future__ import annotations

import pytest

from Northstar_backend.foundation.approvals import ApprovalService
from Northstar_backend.foundation.audit import AuditService
from Northstar_backend.foundation.enums import (
    ApprovalState, CapabilitySafetyClass, RiskLevel, Role,
)


def _svc(state):
    return ApprovalService(state.repos, AuditService(state.repos))


def test_request_approval_records(seeded_state):
    svc = _svc(seeded_state)
    row = svc.request(organization_id=seeded_state.ids["org"],
                      requested_by_user_id=seeded_state.ids["user"],
                      capability="listing.publish",
                      safety_class=CapabilitySafetyClass.WRITE_EXTERNAL.value)
    assert row["state"] == ApprovalState.REQUESTED.value
    assert row["required_approver_role"] == Role.ORGANIZATION_OWNER.value


def test_request_idempotency(seeded_state):
    svc = _svc(seeded_state)
    a = svc.request(organization_id=seeded_state.ids["org"],
                    requested_by_user_id="u", capability="c", idempotency_key="k")
    b = svc.request(organization_id=seeded_state.ids["org"],
                    requested_by_user_id="u", capability="c", idempotency_key="k")
    assert a["id"] == b["id"]


def test_decide_requires_authorized_role(seeded_state):
    svc = _svc(seeded_state)
    row = svc.request(organization_id=seeded_state.ids["org"],
                      requested_by_user_id="u", capability="listing.publish",
                      safety_class=CapabilitySafetyClass.WRITE_EXTERNAL.value)
    with pytest.raises(PermissionError):
        svc.decide(approval_request_id=row["id"], decided_by_user_id="u2",
                   decided_by_role=Role.VIEWER.value)


def test_owner_can_grant(seeded_state):
    svc = _svc(seeded_state)
    row = svc.request(organization_id=seeded_state.ids["org"],
                      requested_by_user_id="u", capability="listing.publish")
    out = svc.decide(approval_request_id=row["id"], decided_by_user_id="u2",
                     decided_by_role=Role.ORGANIZATION_OWNER.value)
    assert out["state"] == ApprovalState.GRANTED.value


def test_grant_does_not_execute_write(seeded_state):
    """Approving must not perform any external write."""
    svc = _svc(seeded_state)
    row = svc.request(organization_id=seeded_state.ids["org"],
                      requested_by_user_id="u", capability="listing.publish")
    out = svc.decide(approval_request_id=row["id"], decided_by_user_id="u2",
                     decided_by_role=Role.ORGANIZATION_OWNER.value)
    assert "execution_ref" not in out or out.get("execution_ref") is None


def test_cancel_approval(seeded_state):
    svc = _svc(seeded_state)
    row = svc.request(organization_id=seeded_state.ids["org"],
                      requested_by_user_id="u", capability="c")
    out = svc.cancel(row["id"], "u")
    assert out["state"] == ApprovalState.CANCELLED.value


def test_double_decide_rejected(seeded_state):
    svc = _svc(seeded_state)
    row = svc.request(organization_id=seeded_state.ids["org"],
                      requested_by_user_id="u", capability="c")
    svc.decide(approval_request_id=row["id"], decided_by_user_id="u2",
               decided_by_role=Role.ORGANIZATION_OWNER.value)
    with pytest.raises(ValueError):
        svc.decide(approval_request_id=row["id"], decided_by_user_id="u2",
                   decided_by_role=Role.ORGANIZATION_OWNER.value)