"""Permission evaluation — server-side RBAC.

Role capabilities are the single source of truth for what a role may do. Preview
never elevates: the effective role is min(real_role, target_role) (see context.py).
"""
from __future__ import annotations

from .enums import Role, CapabilitySafetyClass
from .context import RequestContext

# Permission strings
PERM_VIEW = "view"
PERM_DRAFT = "draft"
PERM_RUN_LOCAL = "run_local"
PERM_REQUEST_REFRESH = "request_refresh"
PERM_APPROVE = "approve"
PERM_MANAGE_TEAM = "manage_team"
PERM_MANAGE_ORG = "manage_org"
PERM_VIEW_AUDIT = "view_audit"
PERM_PREVIEW = "preview"
PERM_WRITE_EXTERNAL = "write_external"
PERM_PURCHASE = "purchase"
PERM_PLATFORM_ADMIN = "platform_admin"
# 1C-05 authorization gate: viewers are read-only and must NOT access
# billing/ledger, provider configuration, or the administrative approval queue.
PERM_VIEW_LEDGER = "view_ledger"
PERM_VIEW_PROVIDERS = "view_providers"
PERM_VIEW_APPROVALS = "view_approvals"

# The canonical server-side permission matrix (single source of truth).
#   owner     — everything below + manage org settings + membership + purchase
#   operator  — create and operate permitted research jobs (incl. job + usage
#               + provider + approval visibility needed to operate)
#   viewer    — strictly read-only; NO billing/ledger, secrets, provider
#               configuration, or administrative audit/approval metadata
_ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.VIEWER.value: {PERM_VIEW},
    Role.ANALYST.value: {PERM_VIEW, PERM_DRAFT, PERM_RUN_LOCAL},
    Role.OPERATOR.value: {
        PERM_VIEW, PERM_DRAFT, PERM_RUN_LOCAL, PERM_REQUEST_REFRESH,
        PERM_APPROVE, PERM_VIEW_AUDIT, PERM_PREVIEW,
        PERM_VIEW_LEDGER, PERM_VIEW_PROVIDERS, PERM_VIEW_APPROVALS,
    },
    Role.ORGANIZATION_ADMIN.value: {
        PERM_VIEW, PERM_DRAFT, PERM_RUN_LOCAL, PERM_REQUEST_REFRESH,
        PERM_APPROVE, PERM_VIEW_AUDIT, PERM_PREVIEW, PERM_MANAGE_TEAM,
        PERM_WRITE_EXTERNAL,
        PERM_VIEW_LEDGER, PERM_VIEW_PROVIDERS, PERM_VIEW_APPROVALS,
    },
    Role.ORGANIZATION_OWNER.value: {
        PERM_VIEW, PERM_DRAFT, PERM_RUN_LOCAL, PERM_REQUEST_REFRESH,
        PERM_APPROVE, PERM_VIEW_AUDIT, PERM_PREVIEW, PERM_MANAGE_TEAM,
        PERM_MANAGE_ORG, PERM_WRITE_EXTERNAL, PERM_PURCHASE,
        PERM_VIEW_LEDGER, PERM_VIEW_PROVIDERS, PERM_VIEW_APPROVALS,
    },
    Role.INTERNAL_PLATFORM_ADMIN.value: {
        PERM_VIEW, PERM_DRAFT, PERM_RUN_LOCAL, PERM_REQUEST_REFRESH,
        PERM_APPROVE, PERM_VIEW_AUDIT, PERM_PREVIEW, PERM_MANAGE_TEAM,
        PERM_MANAGE_ORG, PERM_WRITE_EXTERNAL, PERM_PURCHASE, PERM_PLATFORM_ADMIN,
        PERM_VIEW_LEDGER, PERM_VIEW_PROVIDERS, PERM_VIEW_APPROVALS,
    },
}

# NOTE: write_external/purchase are only ever *gated* by approvals at execution
# time; Phase 1B never executes them (owner decision 7).


def permissions_for_role(role: str) -> set[str]:
    return set(_ROLE_PERMISSIONS.get(role, set()))


def has_permission(role: str, permission: str) -> bool:
    return permission in _ROLE_PERMISSIONS.get(role, set())


def evaluate(ctx: RequestContext, permission: str) -> tuple[bool, str]:
    """Return (allowed, reason). Preview and environment guards applied here."""
    role = ctx.effective_role
    if role is None:
        return False, "no_role"
    # Owner Test Mode (P3-T2): the owner holds every permission string, including
    # purchase. Truth-label / fail-closed / spend-cap rules are enforced elsewhere
    # and are NOT bypassed (P3-T3).
    from .authn import environment as _env
    from . import owner_test_mode as _otm
    if _otm.is_owner_test_mode(role=role, environment=_env()):
        if permission == PERM_WRITE_EXTERNAL and ctx.is_sandbox:
            return False, "sandbox_blocks_external_write"
        if permission in (PERM_WRITE_EXTERNAL, PERM_PURCHASE) and not ctx.allow_write():
            return False, "preview_read_only"
        return True, "owner_test_mode"
    if not has_permission(role, permission):
        return False, f"role_{role}_lacks_{permission}"
    # Environment guard: production writes never allowed from sandbox context.
    if permission == PERM_WRITE_EXTERNAL and ctx.is_sandbox:
        return False, "sandbox_blocks_external_write"
    # Consequential actions blocked while previewing read-only.
    if permission in (PERM_WRITE_EXTERNAL, PERM_PURCHASE) and not ctx.allow_write():
        return False, "preview_read_only"
    return True, "ok"


def require(permission: str):
    """Dependency factory for FastAPI routes."""
    from fastapi import HTTPException

    def _dep(ctx: RequestContext) -> RequestContext:
        allowed, reason = evaluate(ctx, permission)
        if not allowed:
            raise HTTPException(status_code=403,
                                detail={"code": "permission_denied",
                                        "message": reason,
                                        "permission": permission})
        return ctx

    return _dep