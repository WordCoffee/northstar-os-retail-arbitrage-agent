#!/usr/bin/env python
"""LOCAL-DEVELOPMENT-ONLY platform-admin bootstrap (1C Phase 1C UI sprint).

Creates/audits an INTERNAL_PLATFORM_ADMIN identity for the DISPOSABLE loopback
database only. Refuses any non-loopback target and never exists as a
production route. Usage:

  python -m Northstar_backend.tools.local_bootstrap_admin \
      --email admin@local.test [--org "Local Production"]

Requires FOUNDATION_DB_URL pointing at the disposable loopback PostgreSQL.
The issued token is written to %LOCALAPPDATA%\\northstar-local-admin-token.txt.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid as _uuid
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.getcwd())

DISPOSABLE_DB = "northstar_phase1c02_ephemeral"
DISPOSABLE_USER = "northstar_phase1c02_test"
STATE_FILE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "northstar-local-admin-state.json"


def _refuse_unless_loopback(db_url: str) -> None:
    u = urlparse(db_url)
    if u.hostname != "127.0.0.1":
        raise SystemExit(f"REFUSING: host must be loopback (got {u.hostname})")
    if u.port not in (55432, 55433, 55434):
        raise SystemExit(f"REFUSING: port must be the disposable loopback PG (got {u.port})")
    if os.environ.get("ENVIRONMENT", "production") == "production" and \
            os.environ.get("NS_FOUNDATION_BIND_HOST", "127.0.0.1") != "127.0.0.1":
        raise SystemExit("REFUSING: non-loopback bind detected")


def main(argv: Optional[list[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description="Local platform-admin bootstrap (loopback only)")
    ap.add_argument("--email", default="admin@local.test")
    ap.add_argument("--org", default="Local Production")
    parsed = ap.parse_args(args)

    db_url = os.environ.get("FOUNDATION_DB_URL")
    if not db_url:
        print("FOUNDATION_DB_URL must be set (disposable loopback PG).")
        return 2
    _refuse_unless_loopback(db_url)
    os.environ["ENVIRONMENT"] = "production"
    os.environ["NS_FOUNDATION_BIND_HOST"] = "127.0.0.1"

    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.bootstrap import bootstrap_owner
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import User, Membership
    from Northstar_backend.foundation.authn import jwt_secret
    from Northstar_backend.foundation.beta.acceptance import record_acceptance
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment

    st = FoundationState.build()
    boot = bootstrap_owner(st, org_name=parsed.org, user_email=parsed.email,
                           recover=True)
    org_id = boot["organization_id"]

    # find or create the platform-admin user, then grant the membership
    user = None
    for u in st.repos.users.list():
        if u["email"] == parsed.email:
            user = u
            break
    if user is None:
        u = User(id=str(_uuid.uuid4()), email=parsed.email,
                 display_name="Local Platform Admin")
        st.repos.users.add(u)
        user = st.repos.users.get(u.id)
    member = next((m for m in st.repos.memberships.list(
        where={"organization_id": org_id, "user_id": user["id"]})), None)
    if member is None:
        st.repos.memberships.add(Membership(
            id=str(_uuid.uuid4()), organization_id=org_id, user_id=user["id"],
            role=Role.INTERNAL_PLATFORM_ADMIN.value, status="active"))
    else:
        st.db.conn.execute(
            "UPDATE memberships SET role=?, status='active' WHERE id=?",
            (Role.INTERNAL_PLATFORM_ADMIN.value, member["id"]))
        st.db.conn.commit()
    # auditable identity
    st.audit.record(action="admin.bootstrap.local",
                    actor_user_id=user["id"], organization_id=org_id,
                    resource_type="membership",
                    after_meta={"role": Role.INTERNAL_PLATFORM_ADMIN.value,
                                "loopback_only": True, "method": "local_bootstrap_admin"})
    # record the admin's legal acceptance (admin routes are acceptance-gated)
    record_acceptance(st, build_context(user_id=user["id"], organization_id=org_id,
                                        role=Role.INTERNAL_PLATFORM_ADMIN.value,
                                        environment=Environment.PRODUCTION.value),
                      business_use=True, age_18_plus=True,
                      request_id="local-bootstrap-admin")

    # issue a token for the platform admin
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    token = pyjwt.encode({
        "sub": user["id"], "type": "access", "iat": now,
        "exp": now + timedelta(hours=2), "jti": f"local-admin-{org_id[:8]}",
        "tenant_id": org_id, "role": Role.INTERNAL_PLATFORM_ADMIN.value,
        "iss": "https://northstar.local", "aud": "northstar-api",
    }, jwt_secret(), algorithm="HS256")
    token_path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "northstar-local-admin-token.txt"
    token_path.write_text(token, encoding="utf-8")
    STATE_FILE.write_text(json.dumps({
        "user_id": user["id"], "organization_id": org_id,
        "email": parsed.email, "role": Role.INTERNAL_PLATFORM_ADMIN.value,
        "loopback_only": True, "token_path": str(token_path),
        "token_url": "/local-token/local-admin", "created_at": now.isoformat(),
    }, indent=2), encoding="utf-8")
    st.close()
    print(f"Platform admin ready: {parsed.email} (org {org_id[:8]}). "
          f"Token -> {token_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())