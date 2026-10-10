"""Cross-tenant isolation test for the Design Studio store.

The security boundary lives in the DAO: every by-id operation is tenant-scoped
and a foreign record must be indistinguishable from a missing one. This test
uses two accounts against a throwaway SQLite file, so it never touches the
operator's northstar.db.

Run:  python tools/test_design_studio_isolation.py
Exit: 0 = isolated, 1 = a leak.
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Northstar_backend"))

PASS = 0
FAIL = 0
FAILURES: list[str] = []


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"PASS  {msg}")


def no(msg: str) -> None:
    global FAIL
    FAIL += 1
    FAILURES.append(msg)
    print(f"FAIL  {msg}")


def main() -> int:
    # ── Point the data layer at a throwaway DB before importing it ──────────
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="ns_isolation_")
    tmp.close()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("SUPABASE_DB_URL", None)

    import data_layer
    data_layer._SQLITE_PATH = __import__("pathlib").Path(tmp.name)

    layer = data_layer.DataLayer()
    db = data_layer.NorthstarDB.__new__(data_layer.NorthstarDB)
    db._layer = layer
    db.design_studio = data_layer.DesignStudioContainer(layer)

    A = "tenant-a-" + uuid.uuid4().hex[:8]
    B = "tenant-b-" + uuid.uuid4().hex[:8]

    print(f"fixture: temp DB {tmp.name}")
    print(f"tenant A = {A}")
    print(f"tenant B = {B}\n")

    projects = db.design_studio.projects
    assets = db.design_studio.assets
    jobs = db.design_studio.jobs

    # ── A creates a project ─────────────────────────────────────────────────
    pid = projects.create({
        "account_id": A, "name": "A's secret listing project",
        "section": "listing-images", "asin": "B000TESTA1",
        "metadata": {"note": "tenant A only"},
    })
    ok("tenant A created a project")

    own = projects.get_by_id(pid, account_id=A)
    if own and own["account_id"] == A:
        ok("tenant A can read its own project")
    else:
        no("tenant A could NOT read its own project")

    # ── B must not be able to see it ────────────────────────────────────────
    leak = projects.get_by_id(pid, account_id=B)
    if leak is None:
        ok("tenant B cannot read tenant A's project (returns None, not a 403/leak)")
    else:
        no(f"LEAK: tenant B read tenant A's project {pid}")

    # ── B must not be able to modify it ─────────────────────────────────────
    changed = projects.update(pid, {"name": "defaced by B"}, account_id=B)
    if changed is False:
        ok("tenant B cannot PATCH tenant A's project")
    else:
        no("LEAK: tenant B modified tenant A's project")

    after = projects.get_by_id(pid, account_id=A)
    if after and after["name"] == "A's secret listing project":
        ok("tenant A's project is unchanged after B's attempted patch")
    else:
        no(f"LEAK: tenant A's project name is now {after and after.get('name')!r}")

    # ── Ownership must not be reassignable via patch ────────────────────────
    projects.update(pid, {"account_id": B}, account_id=A)
    still_a = projects.get_by_id(pid, account_id=A)
    stolen = projects.get_by_id(pid, account_id=B)
    if still_a and stolen is None:
        ok("account_id is not reassignable through an update patch")
    else:
        no("LEAK: an update patch reassigned account_id")

    # ── B must not be able to delete it ─────────────────────────────────────
    deleted = projects.delete(pid, account_id=B)
    if deleted is False:
        ok("tenant B cannot DELETE tenant A's project")
    else:
        no("LEAK: tenant B deleted tenant A's project")

    # ── Listing must be scoped ──────────────────────────────────────────────
    projects.create({"account_id": B, "name": "B's own project", "section": "listing-images"})
    a_list = projects.list_by_section(account_id=A)
    b_list = projects.list_by_section(account_id=B)
    if len(a_list) == 1 and len(b_list) == 1 and a_list[0]["account_id"] == A and b_list[0]["account_id"] == B:
        ok(f"listing is tenant-scoped (A sees {len(a_list)}, B sees {len(b_list)})")
    else:
        no(f"LEAK: listing not scoped — A sees {len(a_list)}, B sees {len(b_list)}")

    # ── Assets and jobs: same contract ──────────────────────────────────────
    aid = assets.create({"account_id": A, "name": "A hero", "asset_type": "image", "project_id": pid})
    if assets.get_by_id(aid, account_id=B) is None:
        ok("tenant B cannot read tenant A's asset")
    else:
        no("LEAK: tenant B read tenant A's asset")
    if assets.delete(aid, account_id=B) is False:
        ok("tenant B cannot delete tenant A's asset")
    else:
        no("LEAK: tenant B deleted tenant A's asset")
    if assets.get_by_id(aid, account_id=A) is not None:
        ok("tenant A's asset survives B's attempted delete")
    else:
        no("tenant A's asset was destroyed by B")

    jid = jobs.create({"account_id": A, "job_type": "generate", "project_id": pid})
    if jobs.get_by_id(jid, account_id=B) is None:
        ok("tenant B cannot read tenant A's job")
    else:
        no("LEAK: tenant B read tenant A's job")
    if jobs.update(jid, {"status": "complete"}, account_id=B) is False:
        ok("tenant B cannot PATCH tenant A's job")
    else:
        no("LEAK: tenant B patched tenant A's job")
    if jobs.get_by_id(jid, account_id=A)["status"] != "complete":
        ok("tenant A's job status unchanged after B's attempted patch")
    else:
        no("LEAK: tenant A's job status was changed by B")

    # ── A itself can still do everything ────────────────────────────────────
    if projects.update(pid, {"name": "renamed by A"}, account_id=A):
        ok("owner can still update its own project")
    else:
        no("owner could not update its own project")
    if projects.delete(pid, account_id=A):
        ok("owner can still delete its own project")
    else:
        no("owner could not delete its own project")

    # ── Router discipline: every by-id call must pass account_id ────────────
    # Line-based, because a call can span arguments: we look at the call line
    # and the line before it, and require `account_id=` in that window.
    api_path = os.path.join(os.path.dirname(__file__), "..", "Northstar_backend", "design_studio_api.py")
    with open(api_path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    scoped = sum(1 for l in lines if "account_id=_account_id(user)" in l or "account_id=acct" in l)
    bare: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip route decorators and function signatures — they contain the
        # method name but are not calls.
        if stripped.startswith("@") or stripped.startswith("def "):
            continue
        if any(m in line for m in (".get_by_id(", ".update(", ".delete(", ".create(")):
            # A call can span a multi-line argument list, and the scoping
            # argument may sit several lines below the opening paren. Look at
            # the preceding line plus the next 8.
            window = "\n".join(lines[max(0, i - 1):i + 9])
            if "account_id" not in window:
                bare.append(f"L{i + 1}: {stripped[:80]}")
    if scoped >= 11 and not bare:
        ok(f"router: {scoped} scoped call sites, no unscoped by-id call remains")
    else:
        no(f"router scoping incomplete — {scoped} scoped sites; unscoped: {bare}")

    layer.close()
    try:
        os.unlink(tmp.name)
    except OSError:
        pass

    print(f"\nCROSS-TENANT ISOLATION: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:\n  " + "\n  ".join(FAILURES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
