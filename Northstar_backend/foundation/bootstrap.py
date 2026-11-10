"""Initial owner provisioning (Phase 1C-01F).

Explicit, idempotent, audited bootstrap of the first organization owner.

Safety properties:
- NOT triggered by application startup.
- NOT exposed as a public route (CLI only).
- Does not accept arbitrary owner identity from requests.
- Idempotent; fails if an owner already exists unless ``--recover`` is given.
- Writes an audit event.
- Takes no password/secret on the command line (no secret in history/logs).

Usage:
  python -m foundation.bootstrap --org-name "Acme" --email owner@acme.test [--recover]
  python -m foundation.bootstrap --db <foundation.db> --org-name ... --email ...
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional
from uuid import uuid4

from .models import Organization, User, Membership
from .enums import Role


class BootstrapError(RuntimeError):
    pass


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return (local[:1] + "***@" + domain) if local else ("***@" + domain)


def bootstrap_owner(state, *, org_name: str, user_email: str,
                    org_slug: str = "", user_id: Optional[str] = None,
                    role: str = Role.ORGANIZATION_OWNER.value,
                    recover: bool = False) -> dict:
    """Create (or recover) the first organization owner. Idempotent, audited."""
    if not org_name or not user_email:
        raise BootstrapError("org_name and user_email are required")
    repos = state.repos
    slug = org_slug or org_name.strip().lower().replace(" ", "-")

    org = next((o for o in repos.organizations.list() if o["slug"] == slug), None)
    if org is None:
        o = Organization(name=org_name, slug=slug)
        org = repos.organizations.add(o)

    owners = [m for m in repos.memberships.for_org(org["id"])
              if m["role"] == Role.ORGANIZATION_OWNER.value]
    if owners and not recover:
        raise BootstrapError(
            "an owner already exists for this organization; use --recover to add explicitly")

    existing_user = next((u for u in repos.users.list()
                          if u["email"] == user_email), None)
    if existing_user:
        uid = existing_user["id"]
    else:
        u = User(id=user_id or str(uuid4()), email=user_email, display_name=user_email)
        repos.users.add(u)
        uid = u.id

    already = any(m["user_id"] == uid and m["organization_id"] == org["id"]
                  for m in repos.memberships.for_org(org["id"]))
    created = False
    if not already:
        repos.memberships.add(Membership(organization_id=org["id"], user_id=uid,
                                         role=role))
        created = True

    state.audit.record(
        action="bootstrap.owner", actor_user_id=uid, actor_role=role,
        organization_id=org["id"], resource_type="membership",
        resource_id=org["id"], after_meta={
            "email": _mask_email(user_email), "role": role,
            "recover": recover, "created": created},
    )
    return {"organization_id": org["id"], "user_id": uid, "role": role,
            "created": created, "slug": slug}


def _build_state(db_path: Optional[str]):
    from .api.state import FoundationState
    return FoundationState.build(db_path)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Provision the initial organization owner.")
    ap.add_argument("--db", default=None, help="foundation DB path (default: disposable)")
    ap.add_argument("--org-name", required=True)
    ap.add_argument("--org-slug", default="")
    ap.add_argument("--email", required=True)
    ap.add_argument("--user-id", default=None)
    ap.add_argument("--role", default=Role.ORGANIZATION_OWNER.value)
    ap.add_argument("--recover", action="store_true",
                    help="explicitly add an owner when one already exists")
    args = ap.parse_args(argv)

    state = _build_state(args.db)
    try:
        result = bootstrap_owner(
            state, org_name=args.org_name, user_email=args.email,
            org_slug=args.org_slug, user_id=args.user_id, role=args.role,
            recover=args.recover)
        print("bootstrap ok: org={organization_id} user={user_id} role={role} created={created}"
              .format(**result))
    except BootstrapError as exc:
        print(f"bootstrap refused: {exc}")
        return 2
    finally:
        state.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())