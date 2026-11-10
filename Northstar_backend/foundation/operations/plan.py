"""In-app Plan & Usage view (1C-06 / Phase A).

Organization-scoped and role-aware. Owners see the full plan/cohort,
entitlements, usage vs limit, seats, lifecycle state, reset rule, and any
denial/downgrade explanation. Operators/viewers see only the subset permitted
by their role.
"""
from __future__ import annotations

from ..billing.entitlements import EntitlementService
from ..context import RequestContext
from ..enums import Role
from .lifecycle import OrgLifecycleService


class PlanUsageService:
    def __init__(self, entitlements: EntitlementService,
                 lifecycle: OrgLifecycleService) -> None:
        self.entitlements = entitlements
        self.lifecycle = lifecycle

    def view(self, ctx: RequestContext) -> dict:
        org_id = ctx.effective_organization_id
        if not org_id:
            return {"error": "no_organization"}
        base = self.entitlements.plan_usage(org_id)
        base["lifecycle_state"] = self.lifecycle.current_state(org_id)
        role = ctx.effective_role or Role.VIEWER.value
        # role-aware subset
        if role in (Role.VIEWER.value,):
            # viewers see the plan label + lifecycle state only (no limits/usage)
            return {
                "organization_id": org_id,
                "plan": base["plan"],
                "lifecycle_state": base["lifecycle_state"],
                "role_restricted": True,
                "note": "usage, limits, and seat information are restricted "
                        "to operators and owners",
            }
        if role in (Role.ANALYST.value,):
            return {
                "organization_id": org_id,
                "plan": base["plan"],
                "lifecycle_state": base["lifecycle_state"],
                "usage": base["usage"],
                "role_restricted": True,
                "note": "seat information and denial details are restricted "
                        "to operators and owners",
            }
        # operator/owner/admin: full view
        return base