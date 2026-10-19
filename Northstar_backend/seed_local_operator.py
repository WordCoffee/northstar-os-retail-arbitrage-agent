"""Local operator account bootstrap (private-beta local testing).

Why this exists — a real gap:
- ``foundation_seed_owner.py`` provisions the single ``internal_platform_admin``
  owner. Nothing provisions an ordinary local *operator* account.
- The local UI harnesses (``tools/verify-*.cjs``, ``northstar-os-ui/verify-*.cjs``)
  all default to the same local operator account: ``NS_TEST_EMAIL || 't2'`` and
  ``NS_TEST_PASSWORD || 'T2holdings'``. With no such account in the foundation
  store, every one of them fails at sign-in.
- The in-page dev shim identity (``demo-t2`` / ``org-t2``) is deliberately NOT a
  served credential and is expected to FAIL CLOSED
  (``tools/verify-shim-fail-closed.cjs`` asserts the explicit failure), so it can
  never be the account that satisfies those harnesses.

This script closes that gap: idempotently provision the local operator account in
the persistent local foundation SQLite store.

Safety properties:
- SQLite-only and local-only: refuses to run when ``DB_URL``/``FOUNDATION_DB_URL``
  is set (a hosted/Postgres posture) and refuses protected/production-looking
  paths (the same denylist the owner seeder uses).
- The password is read from ``NS_LOCAL_OPERATOR_PASSWORD`` ONLY. It is never a
  command-line argument, never written to a file, never printed, never logged.
- Idempotent: an existing organization/user/membership is reused. An existing
  credential is left untouched unless ``--rotate`` is passed explicitly.
- Writes an audit event for the credential action.

Usage (from ``Northstar_backend/``, or any cwd):
  $env:NS_LOCAL_OPERATOR_PASSWORD = "<password>"   # never committed, never printed
  python seed_local_operator.py
  python seed_local_operator.py --email t2 --org "T2 Holdings LLC" --role operator
  python seed_local_operator.py --rotate           # replace an existing password

Exit codes: 0 ok (incl. already present), 2 usage/policy, 3 unsafe target.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from foundation import credentials  # noqa: E402
from foundation.api.state import FoundationState  # noqa: E402
from foundation.enums import Role  # noqa: E402
from foundation.migrate import production_denylist  # noqa: E402
from foundation.models import Membership, Organization, User  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_UNSAFE = 3

PASSWORD_ENV = "NS_LOCAL_OPERATOR_PASSWORD"
DEFAULT_EMAIL = "t2"
DEFAULT_ORG = "T2 Holdings LLC"
DEFAULT_ROLE = Role.OPERATOR.value


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _default_db_path() -> str:
    env = os.environ.get("FOUNDATION_DB_PATH")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "foundation.db")


def _resolve_db_path(args) -> str:
    """Local SQLite target only; fail closed on any hosted/posture signal."""
    if os.environ.get("DB_URL") or os.environ.get("FOUNDATION_DB_URL"):
        print("REFUSING: DB_URL/FOUNDATION_DB_URL is set - this local seeder "
              "targets the local SQLite foundation store only.")
        raise SystemExit(EXIT_UNSAFE)
    path = args.db_path or _default_db_path()
    low = path.lower()
    if any(t and t in low for t in production_denylist()):
        print("REFUSING: target looks like a protected/production database.")
        raise SystemExit(EXIT_UNSAFE)
    if not low.endswith("foundation.db"):
        print("REFUSING: unexpected target filename (expected a foundation.db "
              "local store). Pass --db-path to name it explicitly.")
        raise SystemExit(EXIT_UNSAFE)
    return path


def seed(*, db_path: str, email: str, org_name: str, role: str,
         password: Optional[str], rotate: bool) -> int:
    email = email.strip().lower()
    if not email:
        print("REFUSING: an email/identifier is required.")
        return EXIT_USAGE
    if role not in {r.value for r in Role}:
        print(f"REFUSING: unknown role {role!r}.")
        return EXIT_USAGE

    state = FoundationState.build(db_path)
    try:
        credentials.ensure_table(state.db)

        # --- organization (reuse by slug) ---
        slug = _slug(org_name)
        org = next((o for o in state.repos.organizations.list()
                    if o["slug"] == slug), None)
        if org is None:
            org = state.repos.organizations.add(Organization(name=org_name, slug=slug))

        # --- user (reuse by email) ---
        user = next((u for u in state.repos.users.list()
                     if (u["email"] or "").lower() == email), None)
        if user is None:
            user = state.repos.users.add(
                User(id=str(uuid4()), email=email, display_name=email))
        uid = user["id"]

        # --- membership (reuse; reactivate if suspended) ---
        rows = [m for m in state.repos.memberships.for_user(uid)
                if m["organization_id"] == org["id"]]
        if not rows:
            state.repos.memberships.add(Membership(
                organization_id=org["id"], user_id=uid, role=role))
            membership_action = "created"
        else:
            existing = rows[0]
            if (existing.get("status") or "active") != "active":
                state.db.conn.execute(
                    "UPDATE memberships SET status='active' "
                    "WHERE organization_id=? AND user_id=?",
                    (org["id"], uid))
                state.db.conn.commit()
                membership_action = "reactivated"
            else:
                membership_action = "existing"

        # --- credential (never replaced without --rotate) ---
        row = credentials.get_by_email(state.db, email)
        if row is None:
            if not password:
                print(f"REFUSING: {PASSWORD_ENV} is not set; the password is "
                      "never taken from the command line.")
                return EXIT_USAGE
            credentials.create(state.db, user_id=uid, email=email, password=password)
            credential_action = "created"
        elif rotate:
            if not password:
                print(f"REFUSING: {PASSWORD_ENV} is not set; the password is "
                      "never taken from the command line.")
                return EXIT_USAGE
            credentials.rotate(state.db, email=email, password=password)
            credential_action = "rotated"
        else:
            credential_action = "existing (unchanged; pass --rotate to replace)"

        state.audit.record(
            action=f"local_operator.credential.{credential_action.split(' ')[0]}",
            actor_user_id=uid, actor_role=role,
            organization_id=org["id"], resource_type="owner_credential",
            resource_id=uid,
            after_meta={"email": email, "role": role,
                        "membership": membership_action,
                        "method": "seed_local_operator"})

        print(f"local operator ready: email={email} user={uid} "
              f"org={org['id']} ({org['name']}) role={role} "
              f"membership={membership_action} credential={credential_action}")
        return EXIT_OK
    finally:
        state.close()


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Provision the local operator account (idempotent).")
    ap.add_argument("--email", default=DEFAULT_EMAIL)
    ap.add_argument("--org", default=DEFAULT_ORG)
    ap.add_argument("--role", default=DEFAULT_ROLE)
    ap.add_argument("--db-path", default=None,
                    help="local foundation SQLite store "
                         "(default: FOUNDATION_DB_PATH or backend/data/foundation.db)")
    ap.add_argument("--rotate", action="store_true",
                    help="explicitly replace an existing password")
    args = ap.parse_args(argv)

    db_path = _resolve_db_path(args)
    # Read once; never echoed, never stored anywhere but the bcrypt hash.
    password = os.environ.get(PASSWORD_ENV) or None
    return seed(db_path=db_path, email=args.email, org_name=args.org,
                role=args.role, password=password, rotate=args.rotate)


if __name__ == "__main__":
    sys.exit(main())
