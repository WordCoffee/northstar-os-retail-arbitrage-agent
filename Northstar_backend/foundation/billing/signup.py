"""Invite-gated private access (1C-06 master slice / Phase C).

Default state is CLOSED. Signup requires a valid, non-revoked, non-expired
admin-managed invite (invite code + approved email). Uninvited attempts get a
NON-REVEALING denial — no confirmation of whether an email/org exists.
Admin revocation of an invite or suspension of an account blocks future
authenticated requests immediately (membership status is enforced per request
in get_context; invite status is enforced at signup).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional
from uuid import uuid4

from ..audit import AuditService
from ..context import RequestContext
from ..enums import Role
from ..models import Invite, Membership, Organization, User, utcnow
from ..repositories import Repositories


class SignupError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class InviteService:
    def __init__(self, repos: Repositories, *, audit: Optional[AuditService] = None) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)

    # -- admin ----------------------------------------------------------------

    def issue(self, ctx: RequestContext, *, email: str, role: str,
              tier_note: Optional[str] = None,
              expires_in_hours: int = 72) -> dict:
        org_id = ctx.effective_organization_id
        if not org_id:
            raise SignupError("no_organization")
        email = (email or "").strip().lower()
        if "@" not in email:
            raise SignupError("invalid_email")
        if role not in (Role.OPERATOR.value, Role.VIEWER.value,
                        Role.ANALYST.value, Role.ORGANIZATION_ADMIN.value,
                        Role.ORGANIZATION_OWNER.value):
            raise SignupError("invalid_role")
        existing = self.repos.invites.by_email(org_id, email)
        if existing and existing["status"] == "pending":
            raise SignupError("invite_pending", "an invite is already pending")
        invite = Invite(
            organization_id=org_id, invite_code=str(uuid4()).replace("-", "")[:16],
            email=email, role=role, status="pending",
            created_by=ctx.user_id, expires_at=utcnow() + timedelta(hours=expires_in_hours))
        row = self.repos.invites.add(invite)
        self.audit.record(action="invite.issue", actor_user_id=ctx.user_id,
                          organization_id=org_id, resource_type="invite",
                          resource_id=row["id"],
                          after_meta={"email_domain": email.split("@")[1]})
        return {"invite_id": row["id"], "email": email, "role": role,
                "status": "pending", "expires_at": row["expires_at"],
                "invite_code": row["invite_code"]}

    def revoke(self, ctx: RequestContext, invite_id: str, *, reason: str = "") -> dict:
        org_id = ctx.effective_organization_id
        invite = self.repos.invites.get(invite_id)
        if invite is None or invite["organization_id"] != org_id:
            raise SignupError("not_found", "invite not found")
        self.repos.db.conn.execute(
            "UPDATE invites SET status='revoked' WHERE id=?", (invite_id,))
        self.repos.db.conn.commit()
        self.audit.record(action="invite.revoke", actor_user_id=ctx.user_id,
                          organization_id=org_id, resource_type="invite",
                          resource_id=invite_id,
                          after_meta={"reason": reason})
        return {"status": "revoked"}

    def list(self, org_id: str) -> list[dict]:
        rows = self.repos.invites.list(where={"organization_id": org_id},
                                       order_by="created_at DESC")
        return [{"invite_id": r["id"], "email": r["email"], "role": r["role"],
                 "status": r["status"], "expires_at": r["expires_at"]} for r in rows]

    # -- signup (public, non-revealing) ----------------------------------------

    def signup(self, *, email: str, invite_code: str,
               display_name: Optional[str] = None) -> dict:
        """Create an account ONLY for a valid invite. Invalid/revoked/expired/
        used invites all return the SAME non-revealing denial."""
        email = (email or "").strip().lower()
        invite = self.repos.invites.by_code((invite_code or "").strip())
        if not self._valid(invite, email):
            raise SignupError("signup_denied",
                              "signup is not available at this time")
        # ensure the user exists
        user = next((u for u in self.repos.users.list()
                     if u["email"] == email), None)
        if user is None:
            u = User(id=str(uuid4()), email=email,
                     display_name=display_name or email.split("@")[0])
            self.repos.users.add(u)
            user = self.repos.users.get(u.id)
        # membership in the invite's org
        existing = self.repos.memberships.list(
            where={"organization_id": invite["organization_id"],
                   "user_id": user["id"]})
        if not existing:
            self.repos.memberships.add(Membership(
                id=str(uuid4()), organization_id=invite["organization_id"],
                user_id=user["id"], role=invite["role"]))
        # mark used
        self.repos.db.conn.execute(
            "UPDATE invites SET status='used', used_at=? WHERE id=?",
            (utcnow().isoformat(), invite["id"]))
        self.repos.db.conn.commit()
        self.audit.record(action="signup.accepted",
                          actor_user_id=user["id"],
                          organization_id=invite["organization_id"],
                          resource_type="invite", resource_id=invite["id"])
        return {"user_id": user["id"],
                "organization_id": invite["organization_id"],
                "role": invite["role"]}

    def _valid(self, invite: Optional[dict], email: str) -> bool:
        if not invite:
            return False
        if invite["status"] != "pending":
            return False
        if invite["email"].lower() != email:
            return False
        if invite.get("expires_at") and str(invite["expires_at"]) < utcnow().isoformat():
            return False
        return True