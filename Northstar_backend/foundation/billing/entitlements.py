"""Centralized entitlement service (1C-06 master slice / Phase B).

Every tier check in the codebase goes through this module — no hardcoded
plan-name comparisons anywhere else. Entitlements are materialized per org
(`org_entitlements`) and refreshed on any subscription event so that
downgrade / cancellation / non-payment revokes gated features on the NEXT
entitlement check (not just at next login).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..context import RequestContext
from ..models import OrgEntitlement, utcnow
from ..repositories import Repositories
from ..audit import AuditService
from ..authn import environment as auth_environment
from .. import owner_test_mode as otm_mod
from . import tiers as tiers_mod

_OWNER_UNLIMITED = 10 ** 9


class EntitlementError(RuntimeError):
    def __init__(self, code: str, message: str = "", *, feature: Optional[str] = None,
                 limit: Optional[int] = None, current: Optional[int] = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.feature = feature
        self.limit = limit
        self.current = current


class EntitlementService:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    # -- materialization -----------------------------------------------------

    def current_tier(self, org_id: str) -> str:
        sub = self.repos.subscriptions.active_for_org(org_id)
        return sub["tier"] if sub else tiers_mod.DEFAULT_TIER

    def _apply_overrides(self, org_id: str, flags: dict) -> dict:
        """Apply active entitlement overrides (permanent or not yet expired)."""
        out = dict(flags)
        for o in self.repos.entitlement_overrides.active(org_id):
            f = o["feature"]
            if f not in tiers_mod.ATOMIC_ENTITLEMENTS:
                continue
            if o["value_text"] is not None:
                out[f] = str(o["value_text"]).lower() in ("1", "true", "yes")
            elif o["value_int"] is not None:
                out[f] = int(o["value_int"])
        return out

    def entitlements_for_org(self, org_id: str,
                             ctx: Optional[RequestContext] = None) -> dict:
        """Materialize the org's entitlement flags. The STORED row always holds
        the BASE tier flags (never override-inflated); ACTIVE overrides are
        applied on every read so expiry/downgrade takes effect immediately."""
        tier = self.current_tier(org_id)
        base = tiers_mod.tier_flags(tier)
        row = self.repos.org_entitlements.get(org_id)
        if row is None or row["tier"] != tier:
            self.repos.db.insert_ignore(
                "org_entitlements",
                {"organization_id": org_id, "tier": tier,
                 "max_jobs_per_month": base["max_jobs_per_month"],
                 "export_enabled": base["export_enabled"],
                 "advanced_reports": base["advanced_reports"],
                 "seat_limit": base["seat_limit"],
                 "updated_at": utcnow().isoformat()},
                conflict_cols=("organization_id",))
            # if the row pre-existed with a different tier, correct it
            self.repos.db.conn.execute(
                "UPDATE org_entitlements SET tier=?, max_jobs_per_month=?, "
                "export_enabled=?, advanced_reports=?, seat_limit=?, updated_at=? "
                "WHERE organization_id=? AND tier<>?",
                (tier, base["max_jobs_per_month"], base["export_enabled"],
                 base["advanced_reports"], base["seat_limit"],
                 utcnow().isoformat(), org_id, tier))
            self.repos.db.conn.commit()
        flags = self._apply_overrides(org_id, base)
        out = {
            "tier": tier,
            "max_jobs_per_month": flags["max_jobs_per_month"],
            "export_enabled": bool(flags["export_enabled"]),
            "advanced_reports": bool(flags["advanced_reports"]),
            "seat_limit": flags["seat_limit"],
            "support_level": flags.get("support_level", "none"),
            "override_allowed": bool(flags.get("override_allowed", False)),
        }
        # Owner Test Mode (P3-T2): every testable feature is available to the
        # owner only (gated flags on, limits unbounded; support_level untouched).
        if ctx is not None and self._is_owner_test_mode(ctx):
            out["export_enabled"] = True
            out["advanced_reports"] = True
            out["override_allowed"] = True
            out["max_jobs_per_month"] = _OWNER_UNLIMITED
            out["seat_limit"] = _OWNER_UNLIMITED
        return out

    # -- Owner Test Mode helpers (P3-T2) --------------------------------------

    def _is_owner_test_mode(self, ctx: RequestContext) -> bool:
        return otm_mod.is_owner_test_mode(role=ctx.effective_role,
                                          environment=otm_mod.raw_environment())

    def _audit_bypass(self, ctx: RequestContext, *, action: str, feature: str,
                      reason: str) -> None:
        try:
            AuditService(self.repos).record(
                action=action, actor_user_id=ctx.user_id,
                actor_role=ctx.effective_role,
                organization_id=ctx.effective_organization_id,
                resource_type="entitlement", resource_id=feature,
                after_meta={"owner_test_mode": True, "reason": reason,
                            "feature": feature})
        except Exception:  # noqa: BLE001 - audit must never break the request
            pass

    def _increment_monthly_jobs_unbounded(self, org_id: str) -> None:
        period = self.current_period()
        conn = self.repos.db.conn
        self.repos.db.insert_ignore(
            "usage_counters",
            {"organization_id": org_id, "period": period,
             "monthly_jobs_used": 0, "updated_at": utcnow().isoformat()},
            conflict_cols=("organization_id",))
        conn.execute(
            "UPDATE usage_counters SET monthly_jobs_used = monthly_jobs_used + 1, "
            "period = ?, updated_at = ? WHERE organization_id = ?",
            (period, utcnow().isoformat(), org_id))
        conn.commit()

    # -- centralized checks ---------------------------------------------------

    def check_feature(self, org_id: str, feature: str,
                      ctx: Optional[RequestContext] = None) -> bool:
        """Atomic flag check. Unknown features fail closed (False)."""
        ent = self.entitlements_for_org(org_id, ctx=ctx)
        return bool(ent.get(feature))

    def enforce_feature(self, ctx: RequestContext, feature: str) -> None:
        org_id = ctx.effective_organization_id
        if not org_id:
            raise EntitlementError("no_organization", feature=feature)
        if self._is_owner_test_mode(ctx):
            # Bypass only when the base (non-owner) tier would have denied it.
            if not self.check_feature(org_id, feature):
                self._audit_bypass(ctx, action="owner_test_mode.entitlement_bypass",
                                   feature=feature,
                                   reason="feature_enabled_by_owner_test_mode")
            return
        if not self.check_feature(org_id, feature):
            raise EntitlementError("entitlement_denied",
                                   f"feature {feature} not enabled for this tier",
                                   feature=feature)

    def enforce_limit(self, ctx: RequestContext, feature: str, *,
                      current: int) -> None:
        """Numeric limit check (e.g. max_jobs_per_month). Over-tier is denied
        with a non-revealing reason (no tier/limit disclosure)."""
        org_id = ctx.effective_organization_id
        if not org_id:
            raise EntitlementError("no_organization", feature=feature)
        if self._is_owner_test_mode(ctx):
            base = self.entitlements_for_org(org_id)
            limit = int(base.get(feature) or 0)
            if current >= limit:
                self._audit_bypass(ctx, action="owner_test_mode.quota_bypass",
                                   feature=feature, reason="quota_would_exceed")
            return
        ent = self.entitlements_for_org(org_id)
        limit = int(ent.get(feature) or 0)
        if current >= limit:
            raise EntitlementError(
                "entitlement_denied",
                "the requested action exceeds the permitted limit for this "
                "account", feature=feature, limit=limit, current=current)

    def jobs_used_this_month(self, org_id: str) -> int:
        row = self.repos.db.get("usage_counters",
                                {"organization_id": org_id})
        return int(row["monthly_jobs_used"]) if row else 0

    def current_period(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _atomic_increment_monthly_jobs(self, org_id: str, limit: int) -> bool:
        """Atomically reserve one monthly job slot. Returns False when the
        limit is reached. The UPDATE ... WHERE counter < limit is the atomic
        guard — concurrent attempts cannot collectively exceed the limit."""
        period = self.current_period()
        conn = self.repos.db.conn
        try:
            cur = conn.execute(
                "UPDATE usage_counters SET monthly_jobs_used = monthly_jobs_used + 1, "
                "period = ?, updated_at = ? "
                "WHERE organization_id = ? AND period = ? AND monthly_jobs_used < ?",
                (period, utcnow().isoformat(), org_id, period, limit))
            conn.commit()
            if cur.rowcount == 1:
                return True
            # ensure a counter row exists (race-safe insert), then retry
            self.repos.db.insert_ignore(
                "usage_counters",
                {"organization_id": org_id, "period": period,
                 "monthly_jobs_used": 0, "updated_at": utcnow().isoformat()},
                conflict_cols=("organization_id",))
            cur = conn.execute(
                "UPDATE usage_counters SET monthly_jobs_used = monthly_jobs_used + 1, "
                "period = ?, updated_at = ? "
                "WHERE organization_id = ? AND period = ? AND monthly_jobs_used < ?",
                (period, utcnow().isoformat(), org_id, period, limit))
            conn.commit()
            if cur.rowcount == 1:
                return True
            # stale period (new month)? only then reset the counter and retry.
            row = self.repos.db.get("usage_counters",
                                    {"organization_id": org_id})
            if row is not None and row["period"] != period:
                conn.execute(
                    "UPDATE usage_counters SET period=?, monthly_jobs_used=0, "
                    "updated_at=? WHERE organization_id=?",
                    (period, utcnow().isoformat(), org_id))
                conn.commit()
                cur = conn.execute(
                    "UPDATE usage_counters SET monthly_jobs_used = monthly_jobs_used + 1, "
                    "period = ?, updated_at = ? "
                    "WHERE organization_id = ? AND period = ? AND monthly_jobs_used < ?",
                    (period, utcnow().isoformat(), org_id, period, limit))
                conn.commit()
                return cur.rowcount == 1
            return False  # limit reached this period
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise

    def enforce_max_jobs(self, ctx: RequestContext) -> None:
        """ATOMIC monthly job-limit enforcement (over-tier denied with a
        non-leaky reason). The slot is reserved before the job is created."""
        org_id = ctx.effective_organization_id
        if not org_id:
            raise EntitlementError("no_organization", feature="max_jobs_per_month")
        if self._is_owner_test_mode(ctx):
            # Record usage (still counted) but do NOT enforce the block.
            base = self.entitlements_for_org(org_id)
            limit = int(base.get("max_jobs_per_month") or 0)
            used = self.jobs_used_this_month(org_id)
            self._increment_monthly_jobs_unbounded(org_id)
            if used >= limit:
                self._audit_bypass(ctx, action="owner_test_mode.quota_bypass",
                                   feature="max_jobs_per_month",
                                   reason="monthly_job_limit_exceeded")
            return
        ent = self.entitlements_for_org(org_id)
        limit = int(ent.get("max_jobs_per_month") or 0)
        if not self._atomic_increment_monthly_jobs(org_id, limit):
            used = self.jobs_used_this_month(org_id)
            raise EntitlementError(
                "entitlement_denied",
                "the monthly research-job allowance for this account is "
                "reached; it resets at the start of the next period",
                feature="max_jobs_per_month", limit=limit, current=used)

    def enforce_seat_limit(self, org_id: str,
                           ctx: Optional[RequestContext] = None) -> None:
        if ctx is not None and self._is_owner_test_mode(ctx):
            return
        ent = self.entitlements_for_org(org_id)
        limit = int(ent.get("seat_limit") or 0)
        members = self.repos.memberships.list(where={"organization_id": org_id})
        active = [m for m in members if (m.get("status") or "active") == "active"]
        if len(active) >= limit:
            raise EntitlementError(
                "entitlement_denied",
                "the seat limit for this account has been reached",
                feature="seat_limit", limit=limit, current=len(active))

    # -- denial explanations (non-leaky, plan/usage view) ----------------------

    def denial_reason(self, org_id: str, feature: str) -> dict:
        """Explain a denial for the plan/usage view WITHOUT leaking another
        org's data. Unknown features -> generic denial."""
        ent = self.entitlements_for_org(org_id)
        if feature == "max_jobs_per_month":
            limit = int(ent.get("max_jobs_per_month") or 0)
            used = self.jobs_used_this_month(org_id)
            return {
                "code": "entitlement_denied",
                "message": ("the monthly research-job allowance is reached; "
                            "it resets at the start of the next period"),
                "feature": feature, "limit": limit, "current": used,
                "resets": "next_period",
            }
        if feature == "seat_limit":
            return {"code": "entitlement_denied", "feature": feature,
                    "message": "the seat limit for this account has been reached"}
        if feature in ("export_enabled", "advanced_reports"):
            return {"code": "entitlement_denied", "feature": feature,
                    "message": "this feature is not enabled on the current plan"}
        return {"code": "entitlement_denied", "feature": feature,
                "message": "this action is not permitted on the current plan"}

    def plan_usage(self, org_id: str) -> dict:
        """Organization-scoped Plan & Usage view (role filtering is applied by
        the caller)."""
        ent = self.entitlements_for_org(org_id)
        period = self.current_period()
        return {
            "organization_id": org_id,
            "tier": ent["tier"],
            "plan": {"tier": ent["tier"],
                     "support_level": ent.get("support_level", "none"),
                     "override_allowed": bool(ent.get("override_allowed", False))},
            "entitlements": {k: ent[k] for k in tiers_mod.ATOMIC_ENTITLEMENTS
                             if k in ent},
            "usage": {"period": period,
                      "monthly_jobs_used": self.jobs_used_this_month(org_id),
                      "max_jobs_per_month": ent.get("max_jobs_per_month")},
            "seats": {"used": self._active_seat_count(org_id),
                      "limit": ent.get("seat_limit")},
            "reset_rule": "monthly; resets at the start of the next period",
            "denials": [],
        }

    def _active_seat_count(self, org_id: str) -> int:
        members = self.repos.memberships.list(where={"organization_id": org_id})
        return sum(1 for m in members if (m.get("status") or "active") == "active")

    # -- refresh on subscription events ---------------------------------------

    def refresh(self, org_id: str) -> dict:
        """Recompute entitlements from the CURRENT subscription state. Called
        after every billing event so downgrade/cancel/non-payment revokes gated
        features immediately (next check)."""
        return self.entitlements_for_org(org_id)