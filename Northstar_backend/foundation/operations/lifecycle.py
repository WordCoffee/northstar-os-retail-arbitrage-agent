"""Account lifecycle state machine (1C-06 / subscriber rules).

Server-side, validated transition matrix for organization lifecycle states:
invited, onboarding, active, paused, suspended, downgraded, cancelled, archived.

- Every transition is validated (illegal transitions raise LifecycleError).
- Every transition is append-only audited (org_lifecycle_events) with actor,
  previous state, new state, reason, timestamp, and correlation id.
- Suspension/pause/archive/cancel set the org `active` flag so the NEXT
  authenticated request is blocked (get_context checks org state).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..audit import AuditService
from ..context import RequestContext
from ..models import OrgLifecycle, OrgLifecycleEvent, utcnow
from ..repositories import Repositories

INVITED = "invited"
ONBOARDING = "onboarding"
ACTIVE = "active"
PAUSED = "paused"
SUSPENDED = "suspended"
DOWNGRADED = "downgraded"
CANCELLED = "cancelled"
ARCHIVED = "archived"

LIFECYCLE_STATES = (INVITED, ONBOARDING, ACTIVE, PAUSED, SUSPENDED,
                    DOWNGRADED, CANCELLED, ARCHIVED)

# Org states that BLOCK feature access on the next authenticated request.
BLOCKING_STATES = frozenset({INVITED, PAUSED, SUSPENDED, CANCELLED, ARCHIVED})

# Legal transitions.
LEGAL_TRANSITIONS = {
    INVITED: {ONBOARDING, CANCELLED},
    ONBOARDING: {ACTIVE, PAUSED, SUSPENDED, CANCELLED, ARCHIVED},
    ACTIVE: {PAUSED, SUSPENDED, DOWNGRADED, CANCELLED, ARCHIVED, ONBOARDING},
    PAUSED: {ACTIVE, SUSPENDED, CANCELLED, ARCHIVED},
    SUSPENDED: {ACTIVE, PAUSED, CANCELLED, ARCHIVED, DOWNGRADED},
    DOWNGRADED: {ACTIVE, SUSPENDED, CANCELLED, ARCHIVED, PAUSED},
    CANCELLED: {ARCHIVED},
    ARCHIVED: set(),
}

# States that require the org `active` flag to be False (blocking).
_INACTIVE_FLAG_STATES = frozenset({INVITED, PAUSED, SUSPENDED, CANCELLED, ARCHIVED})


class LifecycleError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass
class LifecycleResult:
    organization_id: str
    previous_state: str
    new_state: str
    reason: str
    event_id: str


class OrgLifecycleService:
    def __init__(self, repos: Repositories, *, audit: Optional[AuditService] = None) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)

    def current_state(self, org_id: str) -> str:
        row = self.repos.org_lifecycle.get(org_id)
        return row["state"] if row else ACTIVE  # default active (existing orgs)

    def set_state(self, org_id: str, state: str, *, actor: Optional[str] = None,
                  reason: str = "", correlation_id: Optional[str] = None,
                  transition: bool = True) -> LifecycleResult:
        """Set the org lifecycle state via the validated transition matrix
        (or initialize it when absent). Append-only event + active-flag sync."""
        if state not in LIFECYCLE_STATES:
            raise LifecycleError("invalid_state", f"unknown lifecycle state {state!r}")
        prev = self.current_state(org_id)
        if transition and prev != state:
            if state not in LEGAL_TRANSITIONS.get(prev, set()):
                raise LifecycleError(
                    "illegal_transition",
                    f"illegal lifecycle transition {prev} -> {state}")
        elif prev == state and not reason:
            reason = f"state unchanged ({state})"
        # persist current pointer + append-only event
        row = self.repos.org_lifecycle.get(org_id)
        if row is None:
            self.repos.org_lifecycle.add(OrgLifecycle(organization_id=org_id,
                                                      state=state))
        else:
            self.repos.db.conn.execute(
                "UPDATE org_lifecycle SET state=?, updated_at=? WHERE organization_id=?",
                (state, utcnow().isoformat(), org_id))
            self.repos.db.conn.commit()
        event = OrgLifecycleEvent(
            organization_id=org_id, actor_user_id=actor,
            previous_state=prev, new_state=state, reason=reason,
            correlation_id=correlation_id)
        ev = self.repos.org_lifecycle_events.add(event)
        # sync the org active flag (blocking states disable the org)
        active = False if state in _INACTIVE_FLAG_STATES else True
        self.repos.db.conn.execute(
            "UPDATE organizations SET active=? WHERE id=?", (active, org_id))
        self.repos.db.conn.commit()
        self.audit.record(
            action=f"org.lifecycle.{state}", actor_user_id=actor,
            organization_id=org_id, resource_type="organization",
            resource_id=org_id, correlation_id=correlation_id,
            before_meta={"state": prev}, after_meta={"state": state,
                                                     "reason": reason})
        return LifecycleResult(org_id, prev, state, reason, ev["id"])

    def transition(self, org_id: str, *, to_state: str, actor: str,
                   reason: str, correlation_id: Optional[str] = None,
                   initialize: bool = False) -> LifecycleResult:
        """Validate + apply a lifecycle transition (or initialize when the
        org has no lifecycle row yet and initialize=True)."""
        prev = self.current_state(org_id)
        if prev == ACTIVE and self.repos.org_lifecycle.get(org_id) is None and not initialize:
            raise LifecycleError("not_initialized",
                                 "org has no lifecycle record; initialize first")
        return self.set_state(org_id, to_state, actor=actor, reason=reason,
                              correlation_id=correlation_id, transition=True)

    def history(self, org_id: str) -> list[dict]:
        return [{"previous_state": e["previous_state"], "new_state": e["new_state"],
                 "actor": e.get("actor_user_id"), "reason": e.get("reason"),
                 "correlation_id": e.get("correlation_id"),
                 "occurred_at": e.get("occurred_at")}
                for e in self.repos.org_lifecycle_events.for_org(org_id)]

    def initialize(self, org_id: str, *, actor: Optional[str] = None,
                   reason: str = "org created", state: str = INVITED,
                   correlation_id: Optional[str] = None) -> LifecycleResult:
        return self.set_state(org_id, state, actor=actor, reason=reason,
                              correlation_id=correlation_id, transition=False)