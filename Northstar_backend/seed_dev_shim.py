"""Dev-only seeder for the in-page dev shim identity (demo-t2 / org-t2).

The SignIn.jsx dev shim sends X-User-Id: demo-t2 / X-Org-Id: org-t2 and resolves
against the foundation store. Without a matching org + membership the shim fails
closed with cross_organization_access_denied. This seeder provisions that local-only
identity so the loopback dev shim reaches the workspace.

Safety properties (mirrors seed_local_operator.py):
- SQLite-only, local-only: refuses when DB_URL/FOUNDATION_DB_URL is set.
- Refuses protected/production-looking paths.
- Refuses to run unless ENVIRONMENT=development.
- Idempotent: reuses existing org/user/membership.
- Never prints secrets (there are none: the shim has no password).
"""
from __future__ import annotations

import argparse
import os
import sys
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

DEFAULT_ORG_ID = "org-t2"
DEFAULT_ORG_NAME = "T2 Holdings LLC"
DEFAULT_USER_ID = "demo-t2"
DEFAULT_ROLE = Role.OPERATOR.value


def _default_db_path() -> str:
    env = os.environ.get("FOUNDATION_DB_PATH")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "foundation.db")


def _resolve_db_path(args) -> str:
    if os.environ.get("DB_URL") or os.environ.get("FOUNDATION_DB_URL"):
        print("REFUSING: DB_URL/FOUNDATION_DB_URL is set - dev shim targets local SQLite only.")
        raise SystemExit(EXIT_UNSAFE)
    if (os.environ.get("ENVIRONMENT") or "").strip().lower() != "development":
        print("REFUSING: ENVIRONMENT must be 'development' for dev-shim seeding.")
        raise SystemExit(EXIT_UNSAFE)
    path = args.db_path or _default_db_path()
    low = path.lower()
    if any(t and t in low for t in production_denylist()):
        print("REFUSING: target looks like a protected/production database.")
        raise SystemExit(EXIT_UNSAFE)
    if not low.endswith("foundation.db"):
        print("REFUSING: unexpected target filename (expected foundation.db).")
        raise SystemExit(EXIT_UNSAFE)
    return path


def seed(*, db_path: str) -> int:
    state = FoundationState.build(db_path)
    try:
        credentials.ensure_table(state.db)

        # org
        org = next((o for o in state.repos.organizations.list() if o["id"] == DEFAULT_ORG_ID), None)
        if org is None:
            org = state.repos.organizations.add(Organization(id=DEFAULT_ORG_ID, name=DEFAULT_ORG_NAME, slug="org-t2"))

        # user
        user = next((u for u in state.repos.users.list() if u["id"] == DEFAULT_USER_ID), None)
        if user is None:
            user = state.repos.users.add(User(id=DEFAULT_USER_ID, email="", display_name=DEFAULT_USER_ID))

        uid = user["id"]
        org_id = org["id"]

        # membership
        rows = [m for m in state.repos.memberships.for_user(uid) if m["organization_id"] == org_id]
        if not rows:
            state.repos.memberships.add(Membership(organization_id=org_id, user_id=uid, role=DEFAULT_ROLE))
            membership_action = "created"
        else:
            existing = rows[0]
            if (existing.get("status") or "active") != "active":
                state.db.conn.execute("UPDATE memberships SET status='active' WHERE organization_id=? AND user_id=?", (org_id, uid))
                state.db.conn.commit()
                membership_action = "reactivated"
            else:
                membership_action = "existing"

        state.audit.record(
            action="dev_shim.identity.seeded", actor_user_id=uid, actor_role=DEFAULT_ROLE,
            organization_id=org_id, resource_type="dev_shim_identity", resource_id=uid,
            after_meta={"user_id": DEFAULT_USER_ID, "org_id": DEFAULT_ORG_ID, "role": DEFAULT_ROLE,
                        "membership": membership_action, "method": "seed_dev_shim"})

        print(f"dev shim identity ready: user={DEFAULT_USER_ID} org={DEFAULT_ORG_ID} role={DEFAULT_ROLE} membership={membership_action}")
        return EXIT_OK
    finally:
        state.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Provision the local dev-shim identity (dev only).")
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)
    db_path = _resolve_db_path(args)
    return seed(db_path=db_path)


if __name__ == "__main__":
    sys.exit(main())
PY