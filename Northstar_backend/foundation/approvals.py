"""Approval foundation.

Phase 1B builds policy/request/decision/gating only. NO external write executes;
approving a request records a grant and an audit event, but execution is out of
scope (owner decision 7).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from .enums import ApprovalState, RiskLevel, CapabilitySafetyClass, Role, Environment
from .models import ApprovalRequest, ApprovalDecision, utcnow
from .repositories import Repositories
from .audit import AuditService

# Which roles may decide an approval for a given safety class.
_APPROVER_RANK = {
    Role.VIEWER.value: 0,
    Role.ANALYST.value: 1,
    Role.OPERATOR.value: 2,
    Role.ORGANIZATION_ADMIN.value: 3,
    Role.ORGANIZATION_OWNER.value: 4,
    Role.INTERNAL_PLATFORM_ADMIN.value: 5,
}

_REQUIRED_APPROVER = {
    CapabilitySafetyClass.WRITE_EXTERNAL.value: Role.ORGANIZATION_OWNER.value,
    CapabilitySafetyClass.PURCHASE.value: Role.ORGANIZATION_OWNER.value,
    CapabilitySafetyClass.DRAFT.value: Role.OPERATOR.value,
    CapabilitySafetyClass.READ.value: Role.OPERATOR.value,
}


class ApprovalService:
    def __init__(self, repos: Repositories, audit: Optional[AuditService] = None) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)

    def request(self, *, organization_id: str, requested_by_user_id: str,
                capability: str,
                safety_class: str = CapabilitySafetyClass.WRITE_EXTERNAL.value,
                resource_type: Optional[str] = None, resource_id: Optional[str] = None,
                change_preview: Optional[dict] = None,
                risk_level: str = RiskLevel.MEDIUM.value,
                cost_estimate: Optional[float] = None,
                idempotency_key: Optional[str] = None,
                environment: str = Environment.PRODUCTION.value,
                ttl_minutes: int = 1440) -> dict:
        if idempotency_key:
            found = self.repos.approvals.find({"idempotency_key": idempotency_key})
            if found:
                return found
        req = ApprovalRequest(
            organization_id=organization_id, requested_by_user_id=requested_by_user_id,
            capability=capability, safety_class=safety_class,
            resource_type=resource_type, resource_id=resource_id,
            change_preview=change_preview, risk_level=risk_level,
            cost_estimate=cost_estimate, idempotency_key=idempotency_key,
            required_approver_role=_REQUIRED_APPROVER.get(
                safety_class, Role.ORGANIZATION_OWNER.value),
            expires_at=utcnow() + timedelta(minutes=ttl_minutes),
            environment=environment,
        )
        return self.repos.approvals.add(req)

    def is_authorized_approver(self, role: str, required_role: str) -> bool:
        return _APPROVER_RANK.get(role, -1) >= _APPROVER_RANK.get(required_role, 99)

    def decide(self, *, approval_request_id: str, decided_by_user_id: str,
               decided_by_role: str, decision: str = ApprovalState.GRANTED.value,
               note: Optional[str] = None) -> dict:
        req = self.repos.approvals.get(approval_request_id)
        if req is None:
            raise ValueError(f"unknown approval request {approval_request_id}")
        if req["state"] != ApprovalState.REQUESTED.value:
            raise ValueError(f"request is not pending (state={req['state']})")
        # Expiry check
        expires_at = req.get("expires_at")
        if expires_at and _now_iso() > str(expires_at):
            self.repos.db.conn.execute(
                "UPDATE approval_requests SET state=? WHERE id=?",
                (ApprovalState.EXPIRED.value, approval_request_id))
            self.repos.db.conn.commit()
            raise ValueError("approval request expired")
        if not self.is_authorized_approver(decided_by_role, req["required_approver_role"]):
            self.audit.record(
                action="approval.decide", actor_user_id=decided_by_user_id,
                actor_role=decided_by_role, organization_id=req["organization_id"],
                resource_type="approval_request", resource_id=approval_request_id,
                result="denied", failure_class="insufficient_approver_role")
            raise PermissionError("role not authorized to decide this approval")

        decision_row = ApprovalDecision(
            approval_request_id=approval_request_id,
            decided_by_user_id=decided_by_user_id, decided_by_role=decided_by_role,
            decision=decision, note=note,
        )
        self.repos.approval_decisions.add(decision_row)
        self.repos.db.conn.execute(
            "UPDATE approval_requests SET state=? WHERE id=?",
            (decision, approval_request_id))
        self.repos.db.conn.commit()
        self.audit.record(
            action="approval.decide", actor_user_id=decided_by_user_id,
            actor_role=decided_by_role, organization_id=req["organization_id"],
            resource_type="approval_request", resource_id=approval_request_id,
            after_meta={"decision": decision}, approval_ref=approval_request_id,
            result="success")
        return self.repos.approvals.get(approval_request_id)

    def cancel(self, approval_request_id: str, by_user_id: str) -> dict:
        req = self.repos.approvals.get(approval_request_id)
        if req is None:
            raise ValueError("unknown approval request")
        self.repos.db.conn.execute(
            "UPDATE approval_requests SET state=? WHERE id=?",
            (ApprovalState.CANCELLED.value, approval_request_id))
        self.repos.db.conn.commit()
        self.audit.record(action="approval.cancel", actor_user_id=by_user_id,
                          organization_id=req["organization_id"],
                          resource_type="approval_request",
                          resource_id=approval_request_id, result="success")
        return self.repos.approvals.get(approval_request_id)


def _now_iso() -> str:
    return utcnow().isoformat()