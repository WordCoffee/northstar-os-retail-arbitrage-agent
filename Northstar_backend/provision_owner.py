"""Provision (or repair) the local operator sign-in.

Creates the first organization owner and sets its password credential. This is
the missing link: ``foundation/bootstrap.py`` deliberately takes no password on
the command line, and nothing in the repo ever called
``foundation.credentials.create`` — so a fresh deployment had an org with an
owner but no way to sign in as one.

Idempotent: re-running only repairs what is missing.

The password is read from the ``NS_OWNER_PASSWORD`` environment variable and is
NEVER printed, logged, echoed, or written anywhere. The email is likewise not
printed (it is the username).

Usage (inside the api container, which already has the DB URL):
    NS_OWNER_EMAIL=t2 NS_OWNER_PASSWORD=... python provision_owner.py
"""

from __future__ import annotations

import os
import sys

from foundation.api.state import FoundationState
from foundation.bootstrap import bootstrap_owner, BootstrapError
from foundation import credentials


def main() -> int:
    email = (os.environ.get("NS_OWNER_EMAIL") or "").strip().lower()
    password = os.environ.get("NS_OWNER_PASSWORD") or ""
    org_name = os.environ.get("NS_OWNER_ORG") or "T2 Holdings"

    if not email:
        print("NS_OWNER_EMAIL is required", file=sys.stderr)
        return 2
    if not password:
        print("NS_OWNER_PASSWORD is required", file=sys.stderr)
        return 2

    state = FoundationState.build()
    try:
        # 1. Organization + user + owner membership (idempotent).
        try:
            result = bootstrap_owner(state, org_name=org_name, user_email=email)
        except BootstrapError as exc:
            # An owner already exists for this org — recover/add this one.
            print(f"bootstrap note: {exc}")
            result = bootstrap_owner(state, org_name=org_name, user_email=email,
                                     recover=True)

        user_id = result["user_id"]
        print(f"org={result['organization_id']} role={result['role']} "
              f"membership_created={result['created']}")

        # 2. Password credential (idempotent: rotate when it already exists).
        existing = credentials.get_by_email(state.db, email)
        if existing is None:
            credentials.create(state.db, user_id=user_id, email=email,
                               password=password)
            print("credential: created")
        elif existing.get("user_id") != user_id:
            # A credential exists under a different user id — repoint it.
            credentials.rotate(state.db, email=email, password=password)
            print("credential: rotated (existing hash replaced)")
        else:
            credentials.rotate(state.db, email=email, password=password)
            print("credential: rotated (password re-set)")

        # 3. Report the sign-in shape WITHOUT revealing anything.
        memberships = [
            m for m in state.repos.memberships.for_user(user_id)
            if (m.get("status") or "active") == "active"
        ]
        for m in memberships:
            print(f"membership: org={m['organization_id']} role={m['role']}")
        if not memberships:
            print("membership: NONE — sign-in will have no resolved organization")
        return 0
    finally:
        state.close()


if __name__ == "__main__":
    sys.exit(main())
