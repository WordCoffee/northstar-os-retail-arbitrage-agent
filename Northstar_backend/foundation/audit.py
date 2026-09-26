"""Audit events. Never store secrets in payloads; metadata is allow-listed."""
from __future__ import annotations

from typing import Optional

from .enums import Environment, ViewContext, AuditResult
from .models import AuditEvent
from .repositories import Repositories

# Keys that must never appear in audit before/after metadata.
_FORBIDDEN_KEYS = {
    "password", "secret", "token", "api_key", "apikey", "authorization",
    "refresh_token", "access_token", "credential", "private_key", "session",
}


def _scrub(meta: Optional[dict]) -> Optional[dict]:
    if not meta:
        return meta
    out = {}
    for k, v in meta.items():
        if k.lower() in _FORBIDDEN_KEYS:
            out[k] = "[REDACTED]"
        elif isinstance(v, dict):
            out[k] = _scrub(v)
        else:
            out[k] = v
    return out


class AuditService:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def record(self, *, action: str, actor_user_id: Optional[str] = None,
               actor_role: Optional[str] = None, organization_id: Optional[str] = None,
               target_organization_id: Optional[str] = None,
               target_user_id: Optional[str] = None, resource_type: Optional[str] = None,
               resource_id: Optional[str] = None, before_meta: Optional[dict] = None,
               after_meta: Optional[dict] = None,
               environment: str = Environment.PRODUCTION.value,
               view_context: str = ViewContext.NORMAL.value,
               approval_ref: Optional[str] = None, job_run_ref: Optional[str] = None,
               correlation_id: Optional[str] = None,
               result: str = AuditResult.SUCCESS.value,
               failure_class: Optional[str] = None) -> dict:
        ev = AuditEvent(
            actor_user_id=actor_user_id, actor_role=actor_role,
            organization_id=organization_id,
            target_organization_id=target_organization_id,
            target_user_id=target_user_id, action=action,
            resource_type=resource_type, resource_id=resource_id,
            before_meta=_scrub(before_meta), after_meta=_scrub(after_meta),
            environment=environment, view_context=view_context,
            approval_ref=approval_ref, job_run_ref=job_run_ref,
            correlation_id=correlation_id,
            result=result, failure_class=failure_class,
        )
        return self.repos.audit.add(ev)

    def list_for_org(self, organization_id: str, limit: int = 100) -> list[dict]:
        return self.repos.audit.list(where={"organization_id": organization_id},
                                     order_by="occurred_at DESC", limit=limit)