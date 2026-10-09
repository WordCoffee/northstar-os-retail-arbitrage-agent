"""Create the six isolated test accounts for the overnight verification run.

Writes credentials to a file OUTSIDE the git tree. Never logs a password.

Roles (per the audit's A7):
  unauthenticated            - no account at all (proven by calling with no session)
  invited_not_activated      - an invite exists but has never been redeemed
  subscriber                 - a normal tenant owner
  operator                   - a tenant operator
  platform_admin             - the internal platform-admin axis
  other_tenant               - a SECOND tenant, for cross-tenant negative tests

The password is generated with `secrets`, written once to the credentials file
with 0600 permissions, and never printed to stdout/stderr.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
import string
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402
import invites  # noqa: E402

ROLES = (
    ("unauthenticated", None, None),
    ("invited_not_activated", None, None),
    ("subscriber", "owner", "foundation"),
    ("operator", "operator", "scout"),
    ("platform_admin", "admin", "autothink"),
    ("other_tenant", "owner", "mover"),
    ("operator_readonly", "member", "foundation"),
)

_ALPHABET = string.ascii_letters + string.digits + "!@#%^*+-_"
_PASSWORD_LENGTH = 24


def _generate_password() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_PASSWORD_LENGTH))


def _credentials_path() -> Path:
    """Outside the repo tree, so it can never be committed by accident."""
    override = os.environ.get("NS_TEST_CREDENTIALS_PATH")
    if override:
        return Path(override)
    return Path(os.environ.get("LOCALAPPDATA", tempfile_dir())) / "NorthstarOS" / "test-credentials.json"


def tempfile_dir() -> str:  # pragma: no cover - trivial
    import tempfile
    return tempfile.gettempdir()


def _existing(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> int:
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    record = _existing(path)
    accounts = record.setdefault("accounts", {})
    record["created_at"] = datetime.now(timezone.utc).isoformat()
    record["note"] = (
        "Isolated local test accounts. This file lives OUTSIDE the git tree "
        "and must never be committed. Passwords are never logged."
    )

    created = []
    for role, tenant_role, plan in ROLES:
        if role == "unauthenticated":
            accounts[role] = {
                "email": None,
                "password": None,
                "tenant_id": None,
                "tenant_role": None,
                "plan": None,
                "note": "No account. Proven by calling every route with no session.",
            }
            continue

        if role in accounts and accounts[role].get("email"):
            # Idempotent: never recreate an account that already exists.
            continue

        suffix = secrets.token_hex(3)
        email = f"ns-test-{role.replace('_', '-')}-{suffix}@northstar.test"
        password = _generate_password()

        if role == "invited_not_activated":
            invite = invites.create_invite("foundation", email=email)
            accounts[role] = {
                "email": email,
                "password": None,
                "tenant_id": None,
                "tenant_role": None,
                "plan": None,
                "invite_code": invite["code"],
                "note": (
                    "Invite issued but NEVER redeemed. Used for the "
                    "invited-not-activated role in tier B."
                ),
            }
            created.append(role)
            continue

        user = auth.register_user(email, password, plan=plan)
        # Tenant role is a separate axis from the account; record it so the
        # harness can mint a token that carries it.
        accounts[role] = {
            "email": email,
            "password": password,
            "user_id": user.get("id"),
            "tenant_id": user.get("id"),
            "tenant_role": tenant_role,
            "plan": plan,
        }
        created.append(role)

    # An invite for the "invited_not_activated" account is created above; also
    # mint a redeemable invite so the invite flow can be exercised end to end.
    if "redeemable_invite" not in record:
        invite = invites.create_invite("founding_operator")
        record["redeemable_invite"] = {
            "code": invite["code"],
            "cohort": invite["cohort"],
            "plan": invite["plan"],
            "expires_at": invite["expires_at"],
        }

    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except (AttributeError, OSError):  # pragma: no cover - platform dependent
        pass

    print(f"credentials file: {path}")
    print(f"accounts in file: {len(accounts)}")
    print(f"newly created: {created if created else 'none (already present)'}")
    for role, info in accounts.items():
        email = info.get("email") or "<no account>"
        print(f"  {role:24s} {email}")
    print("\nPasswords are in the file above and are never printed here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
