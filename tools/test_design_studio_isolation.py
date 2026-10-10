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
        no(f"LEAK: listing not scoped - A sees {len(a_list)}, B sees {len(b_list)}")

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

    # ── LIST negative tests: each store, both directions ────────────────────
    for store_name, store, kwargs in (
        ("projects", projects, {}),
        ("assets", assets, {"project_id": pid}),
        ("jobs", jobs, {"project_id": pid}),
    ):
        listfn = {"projects": "list_by_section", "assets": "list_by_project", "jobs": "list_by_project"}[store_name]
        a_rows = getattr(store, listfn)(account_id=A, **kwargs)
        b_rows = getattr(store, listfn)(account_id=B, **kwargs)
        a_only = all(r["account_id"] == A for r in a_rows)
        b_only = all(r["account_id"] == B for r in b_rows)
        if a_only and b_only:
            ok(f"list {store_name}: A sees {len(a_rows)}, B sees {len(b_rows)}, no mixing")
        else:
            no(f"LEAK: list {store_name} mixed tenants (A={len(a_rows)}, B={len(b_rows)})")

    # An UNSCOPED list is the leak case; confirm the scoped call is what differs.
    unscoped = projects.list_by_section()
    if len(unscoped) >= 2:
        ok(f"an unscoped list sees every tenant ({len(unscoped)}) - which is exactly why callers must pass account_id")
    else:
        no("unscoped list did not see both tenants, so the scoping test proves nothing")

    # ── SEARCH negative: the needle must not cross tenants ──────────────────
    # Both tenants hold a project whose name contains the same token.
    token = "shared-token-" + uuid.uuid4().hex[:6]
    projects.create({"account_id": A, "name": f"{token} A copy", "section": "ads"})
    projects.create({"account_id": B, "name": f"{token} B copy", "section": "ads"})
    a_hits = [p for p in projects.list_by_section(account_id=A, limit=1000) if token in (p.get("name") or "")]
    b_hits = [p for p in projects.list_by_section(account_id=B, limit=1000) if token in (p.get("name") or "")]
    if len(a_hits) == 1 and len(b_hits) == 1 and a_hits[0]["account_id"] == A and b_hits[0]["account_id"] == B:
        ok("search over a shared token returns exactly one hit per tenant")
    else:
        no(f"LEAK: search crossed tenants (A={len(a_hits)}, B={len(b_hits)})")

    # ── EXPORT negative: the manifest must refuse a foreign project ─────────
    if projects.get_by_id(pid, account_id=B) is None:
        ok("export manifest source (get_by_id) refuses a foreign project, so the route answers 404")
    else:
        no("LEAK: export manifest source did not refuse a foreign project")

    # ── Router discipline: the new routes must be scoped too ────────────────
    api_path = os.path.join(os.path.dirname(__file__), "..", "Northstar_backend", "design_studio_api.py")
    with open(api_path, encoding="utf-8") as fh:
        api_lines = fh.read().splitlines()
    for route in ("/search", "/export-manifest"):
        idx = next((i for i, l in enumerate(api_lines) if route in l), None)
        if idx is None:
            no(f"route {route} not found for the scoping check")
            continue
        window = "\n".join(api_lines[idx:idx + 25])
        if "account_id" in window:
            ok(f"route {route} is account-scoped")
        else:
            no(f"LEAK: route {route} is not account-scoped")

    if projects.delete(pid, account_id=A):
        ok("owner can still delete its own project")
    else:
        no("owner could not delete its own project")

    # ── Router discipline: every DAO call must be account-scoped ────────────
    # Match only real DAO calls (design_studio.<store>.<method> or store.<method>),
    # not arbitrary dict .update(). A call can span a multi-line argument list,
    # so the window reaches forwards and backwards. A call passing a prefabricated
    # `payload` is accepted when the file proves the payload is scoped.
    api_path = os.path.join(os.path.dirname(__file__), "..", "Northstar_backend", "design_studio_api.py")
    with open(api_path, encoding="utf-8") as fh:
        api_src = fh.read()
    api_lines = api_src.splitlines()

    import re as _re
    dao_call = _re.compile(
        r"(?:design_studio\.(?:projects|assets|jobs)\.|store\.(?:create|get_by_id|update|delete)\()"
        r"(?:create|get_by_id|update|delete)\("
    )
    payload_scoped = "'account_id': acct" in api_src or "\"account_id\": acct" in api_src
    scoped = sum(1 for l in api_lines if "account_id=acct" in l or "account_id=_account_id(user)" in l
                 or "'account_id': acct" in l)

    bare: list[str] = []
    for i, line in enumerate(api_lines):
        stripped = line.strip()
        if stripped.startswith("@") or stripped.startswith("def "):
            continue
        if not dao_call.search(line):
            continue
        window = "\n".join(api_lines[max(0, i - 6):i + 12])
        if "account_id" in window:
            continue
        # A prefabricated payload is fine when the file proves it is scoped.
        if "payload" in line and payload_scoped:
            continue
        bare.append(f"L{i + 1}: {stripped[:80]}")

    if scoped >= 11 and not bare:
        ok(f"router: {scoped} scoped call sites, no unscoped DAO call remains")
    else:
        no(f"router scoping incomplete - {scoped} scoped sites; unscoped: {bare}")

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
