"""Create two isolated FOUNDATION test tenants for the Phase 7 D10 cross-tenant
negatives (the A7 accounts were created against the legacy auth store, which the
foundation login does not use).

Two organizations, one owner each. Credentials are written to a file OUTSIDE the
git tree and are never printed. Idempotent: an account that already exists in the
file is not recreated.

Run inside the API container (the foundation store lives there):
    python create_foundation_test_accounts.py
    (optionally NS_FOUNDATION_TEST_CREDENTIALS_PATH=/tmp/ns-foundation-test-accounts.json)
"""
from __future__ import annotations

import json
import os
import secrets
import stat
import string
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_PATH = os.environ.get("NS_FOUNDATION_TEST_CREDENTIALS_PATH") or "/tmp/ns-foundation-test-accounts.json"

ROLES = (
    ("tenant_a", "Northstar Test Tenant A", "ns-test-tenant-a"),
    ("tenant_b", "Northstar Test Tenant B", "ns-test-tenant-b"),
)

_ALPHABET = string.ascii_letters + string.digits + "!@#%^*+-_"


def _password() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(24))


def main() -> int:
    path = Path(DEFAULT_PATH)
    record = {}
    if path.exists():
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            record = {}
    accounts = record.setdefault("accounts", {})

    from foundation.api.state import FoundationState
    from foundation import credentials
    from foundation.enums import Role
    from foundation.models import Membership, Organization, User

    st = FoundationState.build()
    credentials.ensure_table(st.db)

    created = []
    for key, org_name, slug in ROLES:
        if accounts.get(key, {}).get("email"):
            continue  # idempotent
        suffix = secrets.token_hex(3)
        email = f"{slug}-{suffix}@northstar.test"
        pw = _password()

        org = Organization(name=org_name, slug=f"{slug}-{suffix}")
        st.repos.organizations.add(org)
        user = User(email=email, display_name=org_name)
        st.repos.users.add(user)
        st.repos.memberships.add(Membership(
            organization_id=org.id, user_id=user.id,
            role=Role.ORGANIZATION_OWNER.value,
        ))
        credentials.create(st.db, user_id=user.id, email=email, password=pw)
        accounts[key] = {
            "email": email,
            "password": pw,
            "user_id": user.id,
            "tenant_id": org.id,
            "tenant_role": Role.ORGANIZATION_OWNER.value,
            "note": "Isolated foundation test tenant. File lives OUTSIDE the git tree; never printed.",
        }
        created.append(key)

    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except (AttributeError, OSError):
        pass

    print(f"credentials file: {path}")
    print(f"newly created: {created if created else 'none (already present)'}")
    print(f"accounts: {sorted(accounts.keys())}")
    print("Passwords are in the file and are never printed here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
