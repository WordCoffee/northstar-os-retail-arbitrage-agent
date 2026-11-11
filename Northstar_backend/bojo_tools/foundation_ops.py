"""Bojo tools for the private-beta rooms, backed by the Foundation services.

Four services (`beta`, `beta-support`, `beta-signup`, `beta-ops`) had no tool at
all, so the scorecard scored their `complete` dimension 0 and Bojo could not
drive them. Each handler here is a thin wrapper over the service that already
backs the HTTP route -- the same `SupportService`, `InviteService`,
`PlanUsageService` and `TesterDashboard` the endpoints call. There is no second
implementation and no placeholder answer: if the store cannot be read the tool
says so instead of returning an empty success.

Identity is never taken from the model's arguments. The chat session's verified
user arrives in ``ctx['identity']`` and the role is re-read from the Foundation
``memberships`` table, exactly as ``foundation.api.deps.get_context`` does. A
session with no Foundation identity, no active membership, or no platform-admin
role is refused rather than served.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from foundation.context import build_context
from foundation.enums import Role

#: The one role that may read cross-organization cohort data.
PLATFORM_ADMIN = Role.INTERNAL_PLATFORM_ADMIN.value

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_DEFAULT_DB = _BACKEND_DIR / "data" / "foundation.db"


def _refuse(tool: str, reason: str) -> Dict[str, Any]:
    return {"ok": False, "tool": tool, "reason": reason}


# ── the Foundation store the app is actually using ──────────────────────────

_CACHE: Dict[str, Any] = {}


def _store_key() -> Tuple[str, str]:
    return (os.environ.get("FOUNDATION_DB_PATH") or "",
            os.environ.get("DB_URL") or os.environ.get("FOUNDATION_DB_URL") or "")


def _foundation(ctx: Optional[Dict[str, Any]]):
    """The FoundationState for this process, or None when there is none.

    Order matters. An injected state (tests) wins; otherwise the state the app
    built at startup is the only authoritative one. Only when no app state can
    be reached does this open the store named by the environment -- and it never
    invents a throwaway database, because a write into a temp store would look
    like success while changing nothing real.
    """
    injected = (ctx or {}).get("foundation") or (ctx or {}).get("foundation_state")
    if injected is not None:
        return injected

    try:
        from auth_deps import _app_foundation_state  # noqa: PLC0415 - same-process bridge

        state = _app_foundation_state()
        if state is not None:
            return state
    except Exception:  # noqa: BLE001 - no app in this process (tests, CLI)
        pass

    key = _store_key()
    if key in _CACHE:
        return _CACHE[key]
    path = key[0]
    url = key[1]
    if not path and not url:
        if not _DEFAULT_DB.is_file():
            return None
        path = str(_DEFAULT_DB)
    try:
        from foundation.api.state import FoundationState  # noqa: PLC0415

        state = FoundationState.build(path or None)
    except Exception:  # noqa: BLE001 - an unreadable store is reported, not replaced
        return None
    _CACHE[key] = state
    return state


# ── identity: verified session -> (user, org, role) ─────────────────────────

def _session(ctx: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    ident = (ctx or {}).get("identity") or {}
    if not isinstance(ident, dict):
        return None, None
    user_id = ident.get("id") or ident.get("user_id")
    org_id = (ident.get("tenant_id") or ident.get("organization_id")
              or (ctx or {}).get("account_id"))
    return (str(user_id) if user_id else None,
            str(org_id) if org_id else None)


def _active_memberships(state, user_id: str) -> List[dict]:
    try:
        rows = state.repos.memberships.for_user(user_id)
    except Exception:  # noqa: BLE001 - an unreadable table is not a membership
        return []
    return [row for row in rows if (row.get("status") or "active") == "active"]


def _membership(state, ctx) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
    """(user_id, org_id, role, reason). Role comes from the database."""
    user_id, org_id = _session(ctx)
    if not user_id:
        return None, None, None, ("the chat session carries no Foundation user, so a "
                                  "beta action cannot be attributed or authorised")
    if not org_id:
        return None, None, None, ("the chat session resolves to no organization, so the "
                                  "beta action has no scope")
    rows = _active_memberships(state, user_id)
    for row in rows:
        if row.get("organization_id") == org_id:
            return user_id, org_id, row.get("role"), ""
    return None, None, None, (f"user {user_id} has no active membership in {org_id}; "
                              "refusing rather than guessing a scope")


def _request_context(user_id: str, org_id: str, role: Optional[str]):
    return build_context(user_id=user_id, organization_id=org_id, role=role,
                         auth_method="chat_session")


# ── beta: onboarding checklist + plan ───────────────────────────────────────

def onboarding_status(*, ctx: Optional[Dict[str, Any]] = None, **_: Any) -> Dict[str, Any]:
    """The caller's own beta onboarding checklist, next step owed, and plan.

    Reads the two records the beta room shows: `SupportService.onboarding_status`
    (the nine-step checklist) and `PlanUsageService.view` (the plan tier and
    usage, filtered by the caller's real role).
    """
    tool = "onboarding_status"
    state = _foundation(ctx)
    if state is None:
        return _refuse(tool, "the Foundation store is unavailable in this process")
    user_id, org_id, role, reason = _membership(state, ctx)
    if not user_id:
        return _refuse(tool, reason)

    status = state.support.onboarding_status(org_id)
    steps = list(status.get("steps") or [])
    checklist = status.get("checklist") or {}
    next_step = next((step for step in steps if not checklist.get(step)), None)
    plan = state.plan_usage.view(_request_context(user_id, org_id, role))

    return {"ok": True, "tool": tool, "data": {
        "organization_id": org_id,
        "role": role,
        "onboarding": {
            "completed": bool(status.get("completed")),
            "completed_at": status.get("completed_at"),
            "steps": steps,
            "checklist": checklist,
            "next_step": next_step,
            "outstanding": [step for step in steps if not checklist.get(step)],
        },
        "plan": plan,
        "source": "foundation.operations.support.onboarding_status + operations.plan.PlanUsageService.view",
    }}


# ── beta-support: file a ticket on the real support queue ───────────────────

def submit_support_ticket(*, category: str, severity: str, subject: str,
                          description: str,
                          ctx: Optional[Dict[str, Any]] = None, **_: Any) -> Dict[str, Any]:
    """File one ticket on the org's support queue; returns its reference id.

    The service validates the category, the severity, and a non-empty subject,
    writes the row, and records the audit event -- this handler does none of that
    itself, so the queue the beta room reads is the queue the chat writes.
    """
    tool = "submit_support_ticket"
    state = _foundation(ctx)
    if state is None:
        return _refuse(tool, "the Foundation store is unavailable in this process")
    user_id, org_id, role, reason = _membership(state, ctx)
    if not user_id:
        return _refuse(tool, reason)

    from foundation.operations.support import (  # noqa: PLC0415
        CATEGORIES, NO_SECRETS_WARNING, SEVERITIES, SupportError,
    )

    try:
        ticket = state.support.submit_ticket(
            _request_context(user_id, org_id, role),
            category=str(category or "").strip(),
            severity=str(severity or "").strip(),
            subject=str(subject or "").strip(),
            description=str(description or ""),
        )
    except SupportError as exc:
        return _refuse(tool, f"{exc.code}: {exc}" if str(exc) != exc.code else exc.code)

    # Echo the row the queue now holds, not the arguments that were sent: if the
    # service normalises anything, the answer must show the stored value.
    stored = state.support.get_ticket(org_id, ticket["ticket_id"], tester_view=True)

    return {"ok": True, "tool": tool, "data": {
        **ticket,
        "category": stored.get("category"),
        "severity": stored.get("severity"),
        "subject": stored.get("subject"),
        "categories": list(CATEGORIES),
        "severities": list(SEVERITIES),
        "no_secrets_warning": NO_SECRETS_WARNING,
        "source": "foundation.operations.support.SupportService.submit_ticket",
    }}


# ── beta-signup: redeem an invite exactly as the signup route does ──────────

def redeem_invite(*, email: str, invite_code: str,
                  display_name: Optional[str] = None,
                  ctx: Optional[Dict[str, Any]] = None, **_: Any) -> Dict[str, Any]:
    """Create the invitee's account from a valid invite code.

    ``InviteService.signup`` is the public, non-revealing path: an invalid,
    revoked, expired, used or mismatched invite all produce the same denial, so
    this tool cannot be used to probe whether an address is invited.
    """
    tool = "redeem_invite"
    state = _foundation(ctx)
    if state is None:
        return _refuse(tool, "the Foundation store is unavailable in this process")

    from foundation.billing.signup import SignupError  # noqa: PLC0415

    if not str(email or "").strip() or not str(invite_code or "").strip():
        return _refuse(tool, "an email and an invite code are both required")

    try:
        result = state.invites.signup(
            email=str(email).strip(), invite_code=str(invite_code).strip(),
            display_name=(str(display_name).strip() if display_name else None))
    except SignupError:
        # Deliberately identical for every failure, matching the route.
        return _refuse(tool, "signup_denied: signup is not available at this time")

    return {"ok": True, "tool": tool, "data": {
        **result,
        "source": "foundation.billing.signup.InviteService.signup",
    }}


# ── beta-ops: the tester dashboard, platform admins only ────────────────────

def beta_cohort(*, lifecycle_state: Optional[str] = None, tier: Optional[str] = None,
                limit: int = 50,
                ctx: Optional[Dict[str, Any]] = None, **_: Any) -> Dict[str, Any]:
    """Read the beta cohort (organizations, lifecycle, usage, open tickets).

    Mirrors ``GET /api/v1/foundation/admin/dashboard``: platform-admin only. The
    gate is the membership table, not the token claim, and every row comes from
    ``TesterDashboard.list_orgs`` so the numbers are the dashboard's own.
    """
    tool = "beta_cohort"
    state = _foundation(ctx)
    if state is None:
        return _refuse(tool, "the Foundation store is unavailable in this process")
    user_id, org_id, role, reason = _membership(state, ctx)
    if not user_id:
        return _refuse(tool, reason)
    if not any(row.get("role") == PLATFORM_ADMIN
               for row in _active_memberships(state, user_id)):
        return _refuse(tool, "permission_denied: the tester dashboard requires "
                             "the internal platform admin role")

    try:
        cap = max(1, min(int(limit or 50), 200))
    except (TypeError, ValueError):
        return _refuse(tool, "limit must be an integer between 1 and 200")

    rows = state.dashboard.list_orgs(state=lifecycle_state or None,
                                     tier=tier or None, limit=cap)
    open_tickets = sum(int(row.get("open_tickets") or 0) for row in rows)
    blockers = sum(int(row.get("blocker_tickets") or 0) for row in rows)
    return {"ok": True, "tool": tool, "data": {
        "organizations": len(rows),
        "open_tickets": open_tickets,
        "blocker_tickets": blockers,
        "flagged": sorted(row["organization_id"] for row in rows if row.get("flags")),
        "rows": rows,
        "filters": {"lifecycle_state": lifecycle_state, "tier": tier, "limit": cap},
        "source": "foundation.operations.dashboard.TesterDashboard.list_orgs",
    }}


TOOLS = {
    "onboarding_status": onboarding_status,
    "submit_support_ticket": submit_support_ticket,
    "redeem_invite": redeem_invite,
    "beta_cohort": beta_cohort,
}
