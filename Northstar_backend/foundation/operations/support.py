"""Beta onboarding + support flows (1C-06 / Phase D).

Onboarding pack (welcome, task checklist, FAQ, support/contact, usage
expectations) and an org-scoped support queue with:
- tester-visible vs internal note separation,
- reference/ticket id generation,
- categories and severities,
- a warning NOT to submit secrets/card data/marketplace credentials,
- NO attachment upload (safe-upload not yet proven).
Testers see only their own org's tickets and tester-visible responses.
"""
from __future__ import annotations

import uuid as _uuid
from typing import Optional

from ..audit import AuditService
from ..context import RequestContext
from ..models import Onboarding, SupportTicket, utcnow
from ..repositories import Repositories

CATEGORIES = ("bug", "onboarding", "usability", "data_quality",
              "billing_test_mode", "feature_request", "other")
SEVERITIES = ("blocker", "high", "medium", "low")
STATUSES = ("new", "acknowledged", "investigating", "resolved", "closed")

# Secret-warning text shown on the ticket form.
NO_SECRETS_WARNING = (
    "Please do NOT submit passwords, card data, API keys, marketplace "
    "credentials, invoices, or confidential supplier documents. Attachments "
    "are not accepted in this beta."
)

ONBOARDING_STEPS = (
    "invite_issued", "legal_documents_accepted", "org_active",
    "plan_assigned", "usage_initialized", "support_verified",
    "entitlement_visible", "suspension_path_known", "audit_present",
)


class SupportError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class SupportService:
    def __init__(self, repos: Repositories, *, audit: Optional[AuditService] = None) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)

    # -- onboarding pack --------------------------------------------------------

    def onboarding_pack(self) -> dict:
        return {
            "welcome": "Northstar OS — Private Beta Welcome & Getting Started",
            "task_script": [
                "Sign in with your invite", "Accept the beta documents",
                "Complete onboarding", "Submit one research job",
                "Check your Plan & Usage view", "Report your first finding",
            ],
            "faq_reference": "/api/v1/foundation/legal/filesets/faq",
            "support_contact_reference": "/api/v1/foundation/legal/filesets/support_contact",
            "usage_expectations": (
                "This is an invite-only beta with explicit plan limits and "
                "test-mode billing. Unknown data stays unknown. No outcome is "
                "guaranteed."),
            "support_boundaries": (
                "Support is provided by the beta operator on a best-effort "
                "basis. No guaranteed response time is offered."),
        }

    def onboarding_status(self, org_id: str) -> dict:
        row = self.repos.onboarding.get(org_id)
        if row is None:
            return {"organization_id": org_id, "completed": False,
                    "checklist": {k: False for k in ONBOARDING_STEPS},
                    "steps": list(ONBOARDING_STEPS)}
        import json as _json
        checklist = row.get("checklist")
        if isinstance(checklist, str):
            try:
                checklist = _json.loads(checklist)
            except (ValueError, TypeError):
                checklist = {}
        return {"organization_id": org_id,
                "completed": bool(row.get("completed")),
                "checklist": checklist or {},
                "steps": list(ONBOARDING_STEPS),
                "completed_at": row.get("completed_at")}

    def complete_onboarding(self, org_id: str, *, step: Optional[str] = None,
                            actor: Optional[str] = None) -> dict:
        row = self.repos.onboarding.get(org_id)
        checklist = {k: False for k in ONBOARDING_STEPS}
        if row is not None:
            import json as _json
            c = row.get("checklist")
            if isinstance(c, str):
                try:
                    c = _json.loads(c)
                except (ValueError, TypeError):
                    c = {}
            checklist.update(c or {})
        if step:
            if step not in ONBOARDING_STEPS:
                raise SupportError("unknown_step", "unknown onboarding step")
            checklist[step] = True
        else:
            checklist = {k: True for k in ONBOARDING_STEPS}
        completed = all(checklist.values())
        if row is None:
            self.repos.onboarding.add(Onboarding(
                organization_id=org_id, checklist=checklist,
                completed=completed,
                completed_at=utcnow() if completed else None))
        else:
            import json as _json
            self.repos.db.conn.execute(
                "UPDATE onboarding SET checklist=?, completed=?, completed_at=?, "
                "updated_at=? WHERE organization_id=?",
                (_json.dumps(checklist), completed,
                 utcnow().isoformat() if completed else None,
                 utcnow().isoformat(), org_id))
            self.repos.db.conn.commit()
        return self.onboarding_status(org_id)

    # -- support tickets ----------------------------------------------------------

    def submit_ticket(self, ctx: RequestContext, *, category: str, severity: str,
                      subject: str, description: str) -> dict:
        org_id = ctx.effective_organization_id
        if not org_id:
            raise SupportError("no_organization")
        if category not in CATEGORIES:
            raise SupportError("unknown_category")
        if severity not in SEVERITIES:
            raise SupportError("unknown_severity")
        if not subject or not subject.strip():
            raise SupportError("empty_subject")
        ref = f"NS-{_uuid.uuid4().hex[:8].upper()}"
        ticket = SupportTicket(
            organization_id=org_id, reference_id=ref,
            reporter_user_id=ctx.user_id, category=category, severity=severity,
            subject=subject, description=description, status="new")
        row = self.repos.support_tickets.add(ticket)
        self.audit.record(action="support.ticket.submit",
                          actor_user_id=ctx.user_id, organization_id=org_id,
                          resource_type="support_ticket", resource_id=row["id"],
                          correlation_id=ctx.request_id,
                          after_meta={"reference_id": ref, "category": category,
                                      "severity": severity})
        return {"ticket_id": row["id"], "reference_id": ref, "status": "new",
                "no_secrets_warning": NO_SECRETS_WARNING,
                "attachments": False}

    def list_tickets(self, org_id: str, *, tester_view: bool = True) -> list[dict]:
        rows = self.repos.support_tickets.for_org(org_id)
        return [self._ticket_view(t, tester_view=tester_view) for t in rows]

    def get_ticket(self, org_id: str, ticket_id: str, *, tester_view: bool = True) -> dict:
        t = self.repos.support_tickets.get(ticket_id)
        if t is None or t["organization_id"] != org_id:
            raise SupportError("not_found", "ticket not found")
        return self._ticket_view(t, tester_view=tester_view)

    def _ticket_view(self, t: dict, *, tester_view: bool) -> dict:
        view = {
            "id": t["id"], "reference_id": t.get("reference_id"),
            "category": t.get("category"), "severity": t.get("severity"),
            "subject": t.get("subject"), "status": t.get("status"),
            "created_at": t.get("created_at"), "updated_at": t.get("updated_at"),
        }
        if tester_view:
            # testers see only their own reporter + tester-visible note
            view["reporter_user_id"] = t.get("reporter_user_id")
            view["description"] = t.get("description")
            view["tester_visible_note"] = t.get("tester_visible_note")
        else:
            view["internal_note"] = t.get("internal_note")
            view["assignee_user_id"] = t.get("assignee_user_id")
        return view

    def triage(self, ctx: RequestContext, org_id: str, ticket_id: str, *,
               status: Optional[str] = None, assignee: Optional[str] = None,
               internal_note: Optional[str] = None,
               tester_visible_note: Optional[str] = None) -> dict:
        """Internal triage: change status, assign, add internal or
        tester-visible notes. Never exposes internal notes to testers."""
        t = self.repos.support_tickets.get(ticket_id)
        if t is None or t["organization_id"] != org_id:
            raise SupportError("not_found", "ticket not found")
        if status and status not in STATUSES:
            raise SupportError("unknown_status")
        sets = []
        params = []
        if status:
            sets.append("status=?"); params.append(status)
        if assignee is not None:
            sets.append("assignee_user_id=?"); params.append(assignee)
        if internal_note is not None:
            sets.append("internal_note=?"); params.append(internal_note)
        if tester_visible_note is not None:
            sets.append("tester_visible_note=?"); params.append(tester_visible_note)
        if sets:
            params.append(utcnow().isoformat())
            params.append(ticket_id)
            self.repos.db.conn.execute(
                f"UPDATE support_tickets SET {', '.join(sets)}, updated_at=? "
                "WHERE id=?", params)
            self.repos.db.conn.commit()
        self.audit.record(action="support.ticket.triage",
                          actor_user_id=ctx.user_id, organization_id=org_id,
                          resource_type="support_ticket", resource_id=ticket_id,
                          correlation_id=ctx.request_id,
                          after_meta={"status": status, "internal_note": bool(internal_note),
                                      "tester_visible_note": bool(tester_visible_note)})
        return self._ticket_view(self.repos.support_tickets.get(ticket_id),
                                 tester_view=False)