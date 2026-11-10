"""Internal tester dashboard (1C-06 / Phase E).

Platform-admin-only list/detail views over the beta cohort with filtering and
an exportable tester status report that EXCLUDES secrets, card data, tokens,
provider credentials, and unauthorized org data.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Optional

from ..audit import AuditService
from ..repositories import Repositories
from .admin import AdminOpsService
from . import lifecycle as lc_mod
from .support import SupportService


class DashboardError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


# The ONLY fields allowed in the export (safe field set).
EXPORT_FIELDS = (
    "organization_id", "organization_name", "lifecycle_state", "plan_tier",
    "subscription_status", "invite_status", "acceptance_complete",
    "onboarding_complete", "monthly_jobs_used", "max_jobs_per_month",
    "seats_used", "seat_limit", "open_tickets", "blocker_tickets",
    "last_activity", "flags",
)

EXPORT_EXCLUDED = ("secret", "token", "password", "card", "credential",
                   "provider_key", "api_key")


class TesterDashboard:
    def __init__(self, repos: Repositories, *,
                 admin: Optional[AdminOpsService] = None,
                 support: Optional[SupportService] = None,
                 audit: Optional[AuditService] = None) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)
        self.admin = admin or AdminOpsService(repos, audit=self.audit)
        self.support = support or SupportService(repos, audit=self.audit)

    # -- data assembly -----------------------------------------------------------

    def _org_row(self, org_id: str) -> dict:
        from ..billing.entitlements import EntitlementService
        org = self.repos.organizations.get(org_id)
        if org is None:
            return None
        ent = EntitlementService(self.repos).entitlements_for_org(org_id)
        sub = self.repos.subscriptions.active_for_org(org_id)
        invites = self.repos.invites.list(where={"organization_id": org_id},
                                          order_by="created_at DESC")
        state = self.admin.lifecycle.current_state(org_id)
        members = self.repos.memberships.list(where={"organization_id": org_id})
        active = [m for m in members if (m.get("status") or "active") == "active"]
        tickets = self.repos.support_tickets.for_org(org_id)
        ob = self.support.onboarding_status(org_id)
        acc = self.repos.account_acceptance.list(
            where={"organization_id": org_id})
        acc_users = len({a["user_id"] for a in acc})
        tickets_count = len([t for t in tickets if t["status"] != "closed"])
        blockers = len([t for t in tickets if t["severity"] == "blocker"])
        from ..models import utcnow
        return {
            "organization_id": org_id,
            "organization_name": org.get("name"),
            "owner": next((m.get("user_id") for m in active
                           if m.get("role") == "organization_owner"), None),
            "lifecycle_state": state,
            "plan_tier": ent["tier"],
            "subscription_status": sub["status"] if sub else "none",
            "invite_status": invites[0]["status"] if invites else "none",
            "acceptance_complete": acc_users > 0,
            "acceptance_count": acc_users,
            "onboarding_complete": bool(ob.get("completed")),
            "monthly_jobs_used": EntitlementService(self.repos).jobs_used_this_month(org_id),
            "max_jobs_per_month": ent.get("max_jobs_per_month"),
            "seats_used": len(active),
            "seat_limit": ent.get("seat_limit"),
            "open_tickets": tickets_count,
            "blocker_tickets": blockers,
            "last_activity": max([t.get("created_at") or "" for t in tickets]
                                 + [a.get("occurred_at") or "" for a in
                                    self.audit.list_for_org(org_id, limit=50)] or [""]),
            "flags": self._flags(state, ent, tickets_count),
            "_internal": {
                "acceptance_events": len(acc),
                "notes_count": len(self.repos.org_admin_notes.for_org(org_id)),
            },
        }

    @staticmethod
    def _flags(state: str, ent: dict, open_tickets: int) -> list[str]:
        flags = []
        if state in lc_mod.BLOCKING_STATES:
            flags.append(f"blocked:{state}")
        if open_tickets and open_tickets >= 3:
            flags.append("support_backlog")
        if not ent.get("export_enabled"):
            flags.append("no_export")
        return flags

    # -- list / detail / filters ---------------------------------------------------

    def list_orgs(self, *, state: Optional[str] = None, tier: Optional[str] = None,
                  invite_status: Optional[str] = None,
                  onboarding_incomplete: bool = False,
                  nearing_limit: bool = False,
                  suspended: bool = False,
                  severity: Optional[str] = None,
                  sort: str = "last_activity",
                  limit: int = 200) -> list[dict]:
        orgs = self.repos.organizations.list(order_by="created_at ASC")
        rows = []
        for org in orgs:
            r = self._org_row(org["id"])
            if r is None:
                continue
            if state and r["lifecycle_state"] != state:
                continue
            if tier and r["plan_tier"] != tier:
                continue
            if invite_status and r["invite_status"] != invite_status:
                continue
            if onboarding_incomplete and r["onboarding_complete"]:
                continue
            if nearing_limit and r["max_jobs_per_month"] and \
                    r["monthly_jobs_used"] < r["max_jobs_per_month"] * 0.8:
                continue
            if suspended and r["lifecycle_state"] != lc_mod.SUSPENDED:
                continue
            if severity:
                has_sev = any(t["severity"] == severity for t in
                              self.repos.support_tickets.for_org(org["id"]))
                if not has_sev:
                    continue
            rows.append(r)
        if sort == "last_activity":
            rows.sort(key=lambda r: r.get("last_activity") or "", reverse=True)
        elif sort == "usage":
            rows.sort(key=lambda r: r.get("monthly_jobs_used") or 0, reverse=True)
        return rows[:limit]

    def detail(self, org_id: str) -> dict:
        r = self._org_row(org_id)
        if r is None:
            raise DashboardError("not_found", "organization not found")
        r["lifecycle_history"] = self.admin.lifecycle.history(org_id)
        r["notes"] = self.admin.notes(org_id)
        r["tickets"] = [self.support._ticket_view(t, tester_view=False)
                        for t in self.repos.support_tickets.for_org(org_id)]
        r["audit"] = self.audit.list_for_org(org_id, limit=50)
        return r

    # -- export (safe field set only) ----------------------------------------------

    def export_csv(self, *, state: Optional[str] = None,
                  tier: Optional[str] = None) -> str:
        rows = self.list_orgs(state=state, tier=tier, limit=500)
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=list(EXPORT_FIELDS))
        writer.writeheader()
        for r in rows:
            writer.writerow({f: r.get(f, "") for f in EXPORT_FIELDS})
        payload = out.getvalue()
        # hard safety: reject if any excluded token slipped into the payload
        low = payload.lower()
        for token in EXPORT_EXCLUDED:
            if token in low:
                raise DashboardError("export_contains_excluded_data",
                                     f"excluded token in export: {token}")
        return payload

    def export_manifest(self) -> dict:
        return {"fields": list(EXPORT_FIELDS),
                "excludes": list(EXPORT_EXCLUDED),
                "note": ("export contains NO secrets, card data, tokens, "
                         "provider credentials, or cross-org data")}