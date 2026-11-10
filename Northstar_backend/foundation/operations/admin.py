"""Internal admin tools for tester account control (1C-06 / Phase C).

All admin actions are role-protected (platform admin), operate from the
admin's server-derived context, are append-only audited, and never leak
internal notes to external testers. Cross-org object guessing stays
non-enumerating.
"""
from __future__ import annotations

from typing import Optional

from ..audit import AuditService
from ..context import RequestContext
from ..models import EntitlementOverride, OrgAdminNote, utcnow
from ..repositories import Repositories
from . import lifecycle as lc_mod
from .lifecycle import OrgLifecycleService


class AdminError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class AdminOpsService:
    def __init__(self, repos: Repositories, *,
                 lifecycle_svc: Optional[OrgLifecycleService] = None,
                 audit: Optional[AuditService] = None) -> None:
        self.repos = repos
        self.lifecycle = lifecycle_svc or OrgLifecycleService(repos, audit=audit)
        self.audit = audit or AuditService(repos)

    # -- target-org helpers (non-enumerating) ----------------------------------

    def _target_org(self, org_id: str) -> dict:
        org = self.repos.organizations.get(org_id)
        if org is None:
            raise AdminError("not_found", "organization not found")
        return org

    # -- lifecycle admin actions ------------------------------------------------

    def grant(self, ctx: RequestContext, org_id: str, *, reason: str) -> dict:
        """Approve/activate a tester org (e.g., invited -> onboarding/active)."""
        self._target_org(org_id)
        current = self.lifecycle.current_state(org_id)
        to = lc_mod.ONBOARDING if current == lc_mod.INVITED else lc_mod.ACTIVE
        res = self.lifecycle.set_state(org_id, to, actor=ctx.user_id or "",
                                       reason=reason, correlation_id=ctx.request_id,
                                       transition=True)
        return self._view(org_id)

    def change_plan(self, ctx: RequestContext, org_id: str, *, cohort: str,
                    reason: str) -> dict:
        """Assign or change plan/cohort. Update the subscription tier + refresh
        entitlements (immediately affects the next entitlement check)."""
        self._target_org(org_id)
        from ..billing import tiers as tiers_mod
        if cohort not in tiers_mod.COHORTS:
            raise AdminError("unknown_cohort", "unknown cohort")
        tier = tiers_mod.COHORTS[cohort]["tier"]
        sub = self.repos.subscriptions.active_for_org(org_id)
        if sub is not None:
            self.repos.db.conn.execute(
                "UPDATE subscriptions SET tier=?, status='active', updated_at=? "
                "WHERE id=?", (tier, utcnow().isoformat(), sub["id"]))
            self.repos.db.conn.commit()
        else:
            # No subscription yet: create an admin-assigned plan subscription
            # so the centralized entitlement service resolves the cohort tier.
            from ..models import Subscription
            self.repos.subscriptions.add(Subscription(
                organization_id=org_id,
                processor_subscription_id=f"admin_{org_id[:12]}",
                price_id=f"price_{cohort}", tier=tier, status="active"))
        self.audit.record(action="admin.plan.change", actor_user_id=ctx.user_id,
                          organization_id=org_id,
                          resource_type="organization", resource_id=org_id,
                          correlation_id=ctx.request_id,
                          after_meta={"cohort": cohort, "reason": reason})
        from ..billing.entitlements import EntitlementService
        EntitlementService(self.repos).refresh(org_id)
        return self._view(org_id)

    def suspend(self, ctx: RequestContext, org_id: str, *, reason: str) -> dict:
        self._target_org(org_id)
        self.lifecycle.set_state(org_id, lc_mod.SUSPENDED,
                                  actor=ctx.user_id or "", reason=reason,
                                  correlation_id=ctx.request_id, transition=True)
        return self._view(org_id)

    def resume(self, ctx: RequestContext, org_id: str, *, reason: str) -> dict:
        self._target_org(org_id)
        current = self.lifecycle.current_state(org_id)
        to = lc_mod.ACTIVE if current != lc_mod.DOWNGRADED else lc_mod.DOWNGRADED
        self.lifecycle.set_state(org_id, to, actor=ctx.user_id or "",
                                 reason=reason, correlation_id=ctx.request_id,
                                 transition=True)
        return self._view(org_id)

    def downgrade(self, ctx: RequestContext, org_id: str, *, reason: str) -> dict:
        self._target_org(org_id)
        self.lifecycle.transition(org_id, to_state=lc_mod.DOWNGRADED,
                                  actor=ctx.user_id or "", reason=reason,
                                  correlation_id=ctx.request_id)
        # also drop the subscription tier to free (revokes features next check)
        self.change_plan(ctx, org_id, cohort="free", reason=reason)
        return self._view(org_id)

    def cancel(self, ctx: RequestContext, org_id: str, *, reason: str) -> dict:
        self._target_org(org_id)
        self.lifecycle.set_state(org_id, lc_mod.CANCELLED,
                                  actor=ctx.user_id or "", reason=reason,
                                  correlation_id=ctx.request_id, transition=True)
        return self._view(org_id)

    def archive(self, ctx: RequestContext, org_id: str, *, reason: str) -> dict:
        self._target_org(org_id)
        self.lifecycle.set_state(org_id, lc_mod.ARCHIVED,
                                  actor=ctx.user_id or "", reason=reason,
                                  correlation_id=ctx.request_id, transition=True)
        return self._view(org_id)

    # -- internal notes (never externally exposed) ------------------------------

    def add_note(self, ctx: RequestContext, org_id: str, *, note: str) -> dict:
        self._target_org(org_id)
        if not note or not note.strip():
            raise AdminError("empty_note", "note is required")
        row = self.repos.org_admin_notes.add(OrgAdminNote(
            organization_id=org_id, author_user_id=ctx.user_id, note=note))
        self.audit.record(action="admin.note.add", actor_user_id=ctx.user_id,
                          organization_id=org_id,
                          resource_type="organization", resource_id=org_id,
                          correlation_id=ctx.request_id)
        return {"note_id": row["id"]}

    def notes(self, org_id: str) -> list[dict]:
        self._target_org(org_id)
        return [{"id": n["id"], "author_user_id": n.get("author_user_id"),
                 "note": n["note"], "created_at": n["created_at"]}
                for n in self.repos.org_admin_notes.for_org(org_id)]

    # -- temporary entitlement overrides -----------------------------------------

    def set_override(self, ctx: RequestContext, org_id: str, *, feature: str,
                     value: object, reason: str,
                     expires_at: Optional[str] = None,
                     permanent: bool = False) -> dict:
        self._target_org(org_id)
        from ..billing import tiers as tiers_mod
        if feature not in tiers_mod.ATOMIC_ENTITLEMENTS:
            raise AdminError("unknown_feature", "unknown entitlement feature")
        row = self.repos.entitlement_overrides.add(EntitlementOverride(
            organization_id=org_id, feature=feature,
            value_text=str(value) if isinstance(value, (bool, str)) else None,
            value_int=int(value) if isinstance(value, int) else None,
            reason=reason, created_by=ctx.user_id, scope="org",
            expires_at=expires_at, permanent=permanent))
        self.audit.record(action="admin.override.set", actor_user_id=ctx.user_id,
                          organization_id=org_id,
                          resource_type="organization", resource_id=org_id,
                          correlation_id=ctx.request_id,
                          after_meta={"feature": feature, "value": str(value),
                                      "permanent": permanent,
                                      "expires_at": expires_at,
                                      "reason": reason})
        from ..billing.entitlements import EntitlementService
        EntitlementService(self.repos).refresh(org_id)
        return {"override_id": row["id"], "feature": feature}

    # -- history + view -----------------------------------------------------------

    def history(self, org_id: str) -> dict:
        self._target_org(org_id)
        return {"lifecycle": self.lifecycle.history(org_id),
                "notes": self.notes(org_id),
                "audit": self.audit.list_for_org(org_id, limit=100)}

    def _view(self, org_id: str) -> dict:
        org = self._target_org(org_id)
        sub = self.repos.subscriptions.active_for_org(org_id)
        from ..billing.entitlements import EntitlementService
        ent = EntitlementService(self.repos).entitlements_for_org(org_id)
        members = self.repos.memberships.list(where={"organization_id": org_id})
        active = [m for m in members if (m.get("status") or "active") == "active"]
        return {
            "organization_id": org_id,
            "organization_name": org.get("name"),
            "lifecycle_state": self.lifecycle.current_state(org_id),
            "plan": {"tier": ent["tier"],
                     "subscription": sub["status"] if sub else "none"},
            "entitlements": ent,
            "seats": {"used": len(active), "limit": ent.get("seat_limit")},
        }