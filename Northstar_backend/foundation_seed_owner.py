"""One-time owner bootstrap for the Foundation app (P2-T5a).

Creates (or explicitly rotates) the single ``internal_platform_admin`` owner
credential. Interactive only: the password is read with ``getpass`` and is NEVER
accepted via command-line argument, environment variable, log, Git, or chat.

Usage:
  python -m Northstar_backend.foundation_seed_owner --email owner@example.com \
      [--org "T2 Holdings"] [--db-path <foundation.db>] [--rotate] [--allow-remote]

Safety:
- Refuses ambiguous/unexpected accounts and unsafe target databases.
- Idempotent: re-running without --rotate refuses instead of silently resetting.
- Never grants ``internal_platform_admin`` to a second account.
- Prints identity only; never the password or its hash.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from typing import Callable, Optional
from urllib.parse import urlparse

sys.path.insert(0, os.getcwd())

from Northstar_backend.foundation import credentials  # noqa: E402
from Northstar_backend.foundation.enums import Role  # noqa: E402
from Northstar_backend.foundation.migrate import production_denylist  # noqa: E402

MIN_PASSWORD_LEN = 12

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_EXISTS = 3
EXIT_AMBIGUOUS = 4
EXIT_UNSAFE = 5
EXIT_WEAK = 6


def _resolve_db_path(args) -> Optional[str]:
    if args.db_path:
        return args.db_path
    url = os.environ.get("DB_URL") or os.environ.get("FOUNDATION_DB_URL")
    if not url:
        return None
    u = urlparse(url)
    host = (u.hostname or "").lower()
    dbname = (u.path or "").lstrip("/").lower()
    tokens = production_denylist()
    if any(t and (t in host or t in dbname) for t in tokens):
        print("REFUSING: target looks like a protected/production database.")
        raise SystemExit(EXIT_UNSAFE)
    loopback = host in ("127.0.0.1", "localhost", "::1")
    if not loopback and not (args.allow_remote or os.environ.get("NORTHSTAR_ALLOW_OWNER_SEED") == "1"):
        print("REFUSING: non-loopback database; pass --allow-remote to confirm.")
        raise SystemExit(EXIT_UNSAFE)
    return None  # FoundationState.build() will use DB_URL itself


def _existing_admin_emails(state) -> list[str]:
    rows = state.repos.memberships.list()
    admin_ids = {m["user_id"] for m in rows
                 if m.get("role") == Role.INTERNAL_PLATFORM_ADMIN.value
                 and m.get("status", "active") == "active"}
    out = []
    for u in state.repos.users.list():
        if u["id"] in admin_ids:
            out.append(u["email"])
    return out


def _prompt_password_twice(password_prompt: Callable[[str], str]) -> Optional[str]:
    pw1 = password_prompt("Owner password: ")
    pw2 = password_prompt("Confirm password: ")
    if pw1 != pw2:
        print("Passwords did not match.")
        return None
    if len(pw1) < MIN_PASSWORD_LEN:
        print(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
        return None
    return pw1


def main(argv: Optional[list[str]] = None, *,
         email_prompt: Callable[[str], str] = input,
         password_prompt: Callable[[str], str] = getpass.getpass) -> int:
    ap = argparse.ArgumentParser(description="One-time Foundation owner bootstrap.")
    ap.add_argument("--email", default=None)
    ap.add_argument("--org", default="Northstar")
    ap.add_argument("--db-path", default=None)
    ap.add_argument("--rotate", action="store_true",
                    help="explicitly replace an existing owner password")
    ap.add_argument("--allow-remote", action="store_true")
    args = ap.parse_args(argv)

    db_path = _resolve_db_path(args)

    from Northstar_backend.foundation.api.state import FoundationState
    state = FoundationState.build(db_path)
    try:
        credentials.ensure_table(state.db)

        email = (args.email or "").strip().lower()
        if not email:
            email = email_prompt("Owner email: ").strip().lower()
        if not email or "@" not in email:
            print("A valid owner email is required.")
            return EXIT_USAGE

        existing = credentials.get_by_email(state.db, email)
        if existing and not args.rotate:
            print("REFUSING: a credential already exists for this email; "
                  "pass --rotate to reset it explicitly.")
            return EXIT_EXISTS

        admins = _existing_admin_emails(state)
        other_admins = [a for a in admins if a.lower() != email]
        if other_admins:
            print("REFUSING: an internal_platform_admin already exists for a "
                  "different account; the owner credential is single-account.")
            return EXIT_AMBIGUOUS
        if args.rotate and not existing:
            print("REFUSING: --rotate given but no credential exists for this email.")
            return EXIT_EXISTS

        password = _prompt_password_twice(password_prompt)
        if password is None:
            return EXIT_WEAK

        from Northstar_backend.foundation.bootstrap import bootstrap_owner
        result = bootstrap_owner(state, org_name=args.org, user_email=email,
                                 role=Role.INTERNAL_PLATFORM_ADMIN.value, recover=True)
        user_id = result["user_id"]
        org_id = result["organization_id"]

        if existing:
            credentials.rotate(state.db, email=email, password=password)
            action = "rotated"
        else:
            credentials.create(state.db, user_id=user_id, email=email, password=password)
            action = "created"

        state.audit.record(action=f"owner.credential.{action}", actor_user_id=user_id,
                           actor_role=Role.INTERNAL_PLATFORM_ADMIN.value,
                           organization_id=org_id, resource_type="owner_credential",
                           resource_id=user_id,
                           after_meta={"email": email, "method": "foundation_seed_owner"})
        print(f"owner credential {action}: email={email} user={user_id} org={org_id}")
        return EXIT_OK
    finally:
        state.close()


if __name__ == "__main__":
    sys.exit(main())