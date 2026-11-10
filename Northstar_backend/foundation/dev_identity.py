"""Dev-only loopback demo identity provisioning.

Owner-authorized dev exception (AGENTS capsule): with ENVIRONMENT=development
and a loopback-only bind, the auth layer may resolve the demo identity
(demo-t2 / org-t2 / operator) without a sign-in. This module makes that identity
exist in the state's OWN store so the exception is usable even when the launcher
did not pin FOUNDATION_DB_PATH (the process then uses a throwaway SQLite
database, where the identity would otherwise be missing and every request would
fail closed with cross_organization_access_denied).

Safety:
- development posture only (ENVIRONMENT=development);
- local SQLite only — never PostgreSQL / DB_URL;
- idempotent (reuses org/user/membership, reactivates a suspended one);
- no secrets and no credential row (the shim has no password).
"""
from __future__ import annotations

import os

from .db import FoundationDB
from .models import Membership, Organization, User

DEV_ORG_ID = "org-t2"
DEV_ORG_NAME = "T2 Holdings LLC"
DEV_USER_ID = "demo-t2"
DEV_ROLE = "operator"


def dev_posture() -> bool:
    return (os.environ.get("ENVIRONMENT") or "development").strip().lower() == "development"


def ensure_dev_identity(state) -> bool:
    """Provision the demo org/user/membership in the state's local store.

    Returns True when the store was eligible (dev posture + local SQLite) and
    the identity is present, False when this process is not a dev-local store.
    """
    if not dev_posture():
        return False
    if not isinstance(getattr(state, "db", None), FoundationDB):
        return False

    repos = state.repos
    created: list[str] = []

    org = next((o for o in repos.organizations.list() if o["id"] == DEV_ORG_ID), None)
    if org is None:
        repos.organizations.add(
            Organization(id=DEV_ORG_ID, name=DEV_ORG_NAME, slug="org-t2"))
        created.append("organization")

    user = next((u for u in repos.users.list() if u["id"] == DEV_USER_ID), None)
    if user is None:
        repos.users.add(User(id=DEV_USER_ID, email="", display_name=DEV_USER_ID))
        created.append("user")

    rows = [m for m in repos.memberships.for_user(DEV_USER_ID)
            if m["organization_id"] == DEV_ORG_ID]
    if not rows:
        repos.memberships.add(
            Membership(organization_id=DEV_ORG_ID, user_id=DEV_USER_ID,
                       role=DEV_ROLE))
        created.append("membership")
    elif (rows[0].get("status") or "active") != "active":
        state.db.conn.execute(
            "UPDATE memberships SET status='active' WHERE organization_id=? AND user_id=?",
            (DEV_ORG_ID, DEV_USER_ID),
        )
        state.db.conn.commit()
        created.append("membership_reactivated")

    if created:
        try:
            state.audit.record(
                action="dev_shim.identity.auto_provisioned",
                actor_user_id=DEV_USER_ID, actor_role=DEV_ROLE,
                organization_id=DEV_ORG_ID, resource_type="dev_shim_identity",
                resource_id=DEV_USER_ID,
                after_meta={"user_id": DEV_USER_ID, "org_id": DEV_ORG_ID,
                            "role": DEV_ROLE, "created": created,
                            "method": "startup_auto_provision"},
            )
        except Exception:
            # Audit is best-effort here: a provisioned identity that works is
            # still better than a startup failure, and the file is dev-only.
            pass

    return True
