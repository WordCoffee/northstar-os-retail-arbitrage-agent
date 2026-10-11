"""Remove ONLY the synthetic test tenants (Phase 8 item 4).

The two tenants created by ``create_foundation_test_accounts.py`` are labelled
by BOTH a slug prefix and a name prefix. This script deletes exactly the
tenants that carry BOTH markers - never anything else. It is a DRY RUN by
default; ``--apply`` performs the removal.

Run inside the API container:
    docker exec <api> python cleanup_test_tenants.py            # dry run
    docker exec <api> python cleanup_test_tenants.py --apply    # remove

After an --apply, the local credentials file (outside the repo) still holds
stale entries for the removed tenants; re-run create_foundation_test_accounts.py
to recreate them, or delete those keys from the file by hand.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The two markers a tenant must carry to be touched. Both must match.
TEST_TENANT_MARKER = "ns-test-tenant-"
TEST_TENANT_NAME_PREFIX = "Northstar Test Tenant"


def _sql(state, query: str, params: tuple = ()):
    conn = getattr(state.db, "conn", state.db)
    return conn.execute(query, params)


def _commit(state):
    conn = getattr(state.db, "conn", state.db)
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser(description="Remove ONLY the synthetic test tenants")
    ap.add_argument("--apply", action="store_true", help="perform the removal (default: dry run)")
    args = ap.parse_args()

    from foundation.api.state import FoundationState
    st = FoundationState.build()
    orgs = st.repos.organizations.list()

    candidates = [
        o for o in orgs
        if str(o.get("slug") or "").startswith(TEST_TENANT_MARKER)
        and str(o.get("name") or "").startswith(TEST_TENANT_NAME_PREFIX)
    ]
    untouched = [o for o in orgs if o not in candidates]

    print(f"organizations: {len(orgs)}; marked test tenants: {len(candidates)}")
    for o in candidates:
        members = st.repos.memberships.list(where={"organization_id": o["id"]})
        user_ids = [m["user_id"] for m in members]
        print(f"  WOULD REMOVE  {o.get('slug')} | {o.get('name')} | memberships={len(members)} users={len(user_ids)}")
    for o in untouched:
        print(f"  untouched     {o.get('slug')} | {o.get('name')}")

    if not args.apply:
        print("\nDRY RUN - nothing was deleted. Re-run with --apply to remove ONLY the tenants listed above.")
        return 0

    removed = 0
    for o in candidates:
        members = st.repos.memberships.list(where={"organization_id": o["id"]})
        user_ids = [m["user_id"] for m in members]
        _sql(st, "DELETE FROM memberships WHERE organization_id = ?", (o["id"],))
        for uid in user_ids:
            _sql(st, "DELETE FROM owner_credentials WHERE user_id = ?", (uid,))
            _sql(st, "DELETE FROM users WHERE id = ?", (uid,))
        _sql(st, "DELETE FROM organizations WHERE id = ?", (o["id"],))
        removed += 1
    _commit(st)
    print(f"\nREMOVED {removed} marked test tenant(s). Nothing else was touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
