"""Import-path fixtures (Phase 6 item 4 + item 6): missing columns, 65-day
gaps, duplicates, cross-tenant isolation (list, search, export), Brand
Analytics UNAVAILABLE, variant metrics matching.

Throwaway SQLite file; never touches the operator's northstar.db.

Run:  python tools/test_design_studio_imports.py
Exit: 0 = all fixtures hold, 1 = a failure.
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


SP_FULL = (
    "Customer Search Term,Campaign Name,Ad Group Name,Match Type,Date,Impressions,Clicks,Spend,Sales,7 Day Total Orders (#)\n"
    "stainless steel tumbler,Launch,Broad,broad,2026-09-20,1200,18,12.40,96.00,3\n"
    "yoga mat,Campaign 2,Exact,exact,2026-09-21,800,4,3.10,11.00,1\n"
)

# A file missing the Impressions and Sales columns entirely. Those values must
# arrive as NULL (UNKNOWN), never as 0.
SP_MISSING_COLUMNS = (
    "Customer Search Term,Campaign Name,Clicks,Spend\n"
    "cold brew filter,Launch,5,2.50\n"
    "pour over kettle,Launch,0,0\n"  # a real 0 stays 0
)

# 81 days between the first and last row: beyond the 65-day lookback ceiling.
SP_65_DAY_GAP = (
    "Customer Search Term,Date,Impressions,Clicks,Spend\n"
    "wide gap term,2026-07-01,100,6,1.00\n"
    "later term,2026-09-20,200,9,2.00\n"
)

BA_SQP = (
    "Search Query,Search Frequency Rank,Search Query Score\n"
    "whey protein isolate,41,88.2\n"
    "creatine monohydrate,120,71.5\n"
)


def main() -> int:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="ns_imports_")
    tmp.close()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("SUPABASE_DB_URL", None)

    import data_layer
    data_layer._SQLITE_PATH = __import__("pathlib").Path(tmp.name)
    layer = data_layer.DataLayer()
    db = data_layer.NorthstarDB.__new__(data_layer.NorthstarDB)
    db._layer = layer
    db.design_studio = data_layer.DesignStudioContainer(layer)

    import design_studio_imports as imp

    A = "tenant-a-" + uuid.uuid4().hex[:8]
    B = "tenant-b-" + uuid.uuid4().hex[:8]

    # ── Missing columns -> NULL, never zero ─────────────────────────────────
    parsed = imp.parse_import(kind=imp.KIND_SP_SEARCH_TERMS, content=SP_MISSING_COLUMNS, filename="sp.csv")
    r0 = parsed["rows"][0]
    r1 = parsed["rows"][1]
    if r0["impressions"] is None and r0["sales"] is None and r0["orders"] is None:
        ok("missing columns parse to NULL (impressions/sales/orders absent -> UNKNOWN)")
    else:
        no(f"missing columns became values: {r0}")
    if r1["clicks"] == 0.0:
        ok("a literal 0 in a present column stays a real 0 (only absence becomes NULL)")
    else:
        no(f"a real 0 was not preserved: clicks={r1['clicks']!r}")
    if set(parsed["missing_columns"]) >= {"impressions", "orders", "sales"}:
        ok(f"missing_columns reports what the file lacked: {parsed['missing_columns']}")
    else:
        no(f"missing_columns wrong: {parsed['missing_columns']}")

    # ── 65-day lookback / 31-day API range notes ────────────────────────────
    gap = imp.parse_import(kind=imp.KIND_SP_SEARCH_TERMS, content=SP_65_DAY_GAP, filename="sp.csv")
    joined = " | ".join(gap["notes"])
    if "65-day" in joined and "31 days" in joined:
        ok("the lookback (65-day) and API range (31-day) notes travel with the data")
    else:
        no(f"notes missing the range limits: {gap['notes']}")
    if "Click-only" in joined:
        ok("the click-only bias note travels with the data")
    else:
        no("the click-only note is missing")
    if gap["observed_from"] == "2026-07-01" and gap["observed_to"] == "2026-09-20" and gap["observed_source"] == "row-dates":
        ok("an 81-day span parses; the observed range is the file's own dates, derived not guessed")
    else:
        no(f"observed range wrong: {gap['observed_from']}..{gap['observed_to']} ({gap['observed_source']})")

    # ── Imports: archive + idempotent duplicate ─────────────────────────────
    imports = db.design_studio.imports
    terms = db.design_studio.search_terms

    def do_import(acct, content, label="SP console export", filename="sp.csv", kind=imp.KIND_SP_SEARCH_TERMS):
        p = imp.parse_import(kind=kind, content=content, filename=filename)
        existing = imports.get_by_fingerprint(acct, p["fingerprint"])
        if existing:
            return "duplicate", existing["id"], 0, p
        iid = imports.create({
            "account_id": acct, "kind": kind, "source_label": label,
            "filename": filename, "format": p["format"],
            "observed_from": p["observed_from"], "observed_to": p["observed_to"],
            "observed_source": p["observed_source"], "row_count": len(p["rows"]),
            "skipped_rows": p["skipped_rows"], "columns_found": p["columns_found"],
            "missing_columns": p["missing_columns"], "notes": p["notes"],
            "fingerprint": p["fingerprint"],
        })
        rows = [{"account_id": acct, "import_id": iid, "kind": kind, **{k: r.get(k) for k in (
            "term", "campaign", "ad_group", "match_type", "targeting", "currency",
            "impressions", "clicks", "orders", "units", "spend", "sales",
            "search_frequency_rank", "search_query_score", "asin_click_share",
            "row_from", "row_to")}} for r in p["rows"]]
        terms.add_many(rows)
        return "imported", iid, len(rows), p

    state, iid_a, n_a, p_a = do_import(A, SP_FULL)
    if state == "imported" and n_a == 2:
        ok("tenant A imported the SP file; 2 rows archived under 1 import")
    else:
        no(f"first import failed: state={state} rows={n_a}")

    state2, iid_a2, n_a2, _ = do_import(A, SP_FULL)
    if state2 == "duplicate" and iid_a2 == iid_a and terms.count_for_import(A, iid_a) == 2:
        ok("re-importing the identical file is idempotent (same import id, still 2 rows)")
    else:
        no(f"duplicate import duplicated: state={state2} id_same={iid_a2 == iid_a} rows={terms.count_for_import(A, iid_a)}")

    # Byte-noise duplicate: BOM + CRLF is the same file.
    noisy = "\ufeff" + SP_FULL.replace("\n", "\r\n")
    state3, iid_a3, _, _ = do_import(A, noisy)
    if state3 == "duplicate" and iid_a3 == iid_a:
        ok("a BOM/CRLF copy of the same file is recognized as the same import")
    else:
        no(f"BOM/CRLF copy was treated as new: {state3}")

    # A genuinely different file is a NEW import.
    changed = SP_FULL + "third term,Launch,Broad,broad,2026-09-22,10,1,0.50,9.00,0\n"
    state4, iid_a4, _, _ = do_import(A, changed)
    if state4 == "imported" and iid_a4 != iid_a and terms.count_for_import(A, iid_a4) == 3:
        ok("a changed file is a new import (old import untouched)")
    else:
        no(f"changed file mishandled: {state4}")

    # The 81-day-span file is archived too, so its NULL metrics exist in the store.
    state5, iid_gap, n_gap, _ = do_import(A, SP_65_DAY_GAP)
    if state5 == "imported" and n_gap == 2:
        ok("the 81-day-span file is archived (its missing columns stay NULL)")
    else:
        no(f"gap-span import failed: {state5} rows={n_gap}")

    # ── Brand Analytics: available only where imported ──────────────────────
    ba_state, ba_iid, ba_rows, ba_p = do_import(
        A, BA_SQP, label="Brand Analytics SQP", filename="sqp.csv",
        kind=imp.KIND_BRAND_ANALYTICS_SQP)
    ba_terms = terms.list_for_account(A, kind=imp.KIND_BRAND_ANALYTICS_SQP)
    a_sp_terms = terms.list_for_account(A, kind=imp.KIND_SP_SEARCH_TERMS)
    if ba_state == "imported" and ba_rows == 2:
        ok("Brand Analytics SQP imported (2 rows); clicks/impressions columns are simply absent")
    else:
        no(f"BA import failed: {ba_state} rows={ba_rows}")
    if all(t["clicks"] is None for t in ba_terms):
        ok("BA rows carry clicks=NULL (the file has no clicks column) - UNKNOWN, not 0")
    else:
        no("BA rows invented click values")
    if len(a_sp_terms) == 7 and len(ba_terms) == 2:
        ok(f"term listing filters by kind (SP {len(a_sp_terms)}, BA {len(ba_terms)})")
    else:
        no(f"kind filter wrong: SP={len(a_sp_terms)} BA={len(ba_terms)}")

    # ── Cross-tenant isolation: list, search, export ────────────────────────
    if imports.list_for_account(B) == []:
        ok("tenant B LIST sees no imports from tenant A")
    else:
        no("LEAK: tenant B saw tenant A's imports")
    if imports.get_by_id(iid_a, account_id=B) is None:
        ok("tenant B cannot READ tenant A's import by id")
    else:
        no("LEAK: tenant B read tenant A's import by id")
    if imports.delete(iid_a, account_id=B) is False and imports.get_by_id(iid_a, account_id=A):
        ok("tenant B cannot DELETE tenant A's import")
    else:
        no("LEAK: tenant B destroyed or deleted tenant A's import")
    if terms.list_for_account(B, q="tumbler") == [] and terms.count_for_import(B, iid_a) == 0:
        ok("tenant B SEARCH finds none of tenant A's terms; B's export source is empty")
    else:
        no("LEAK: tenant B's search/export source saw tenant A's terms")
    # Rows are per-import: a term present in two different files appears once
    # per import (a term unique to the changed file appears exactly once).
    third = terms.list_for_account(A, q="third term")
    tumbler = terms.list_for_account(A, q="tumbler")
    if len(third) == 1 and len(tumbler) == 2 and all(t["account_id"] == A for t in third + tumbler):
        ok(f"tenant A search returns its own rows only (unique term 1 hit; per-import term {len(tumbler)} rows across imports)")
    else:
        no(f"tenant A search wrong: third={len(third)} tumbler={len(tumbler)}")
    # A NULL cell exports EMPTY, never an integer zero.
    null_cell = next((t for t in terms.list_for_account(A, kind=imp.KIND_SP_SEARCH_TERMS)
                      if t["term"] == "wide gap term" and t["orders"] is None), None)
    if null_cell is not None:
        ok("export source keeps a missing metric as None (written as an empty cell, not 0)")
    else:
        no("export source cannot distinguish NULL from 0")

    # ── Fail fixtures: the parser refuses rather than guesses ───────────────
    for desc, fn in (
        ("unknown kind", lambda: imp.parse_import(kind="not_a_kind", content=SP_FULL)),
        ("empty file", lambda: imp.parse_import(kind=imp.KIND_SP_SEARCH_TERMS, content="   ")),
        ("no term column", lambda: imp.parse_import(kind=imp.KIND_SP_SEARCH_TERMS, content="Impressions,Clicks\n1,2\n")),
        ("every row term-less", lambda: imp.parse_import(kind=imp.KIND_SP_SEARCH_TERMS, content="Customer Search Term,Clicks\n,\n,\n")),
    ):
        try:
            fn()
            no(f"parser accepted a bad file: {desc}")
        except imp.ImportParseError:
            ok(f"parser refuses {desc} with a stated reason")

    # ── Variants (item 6): isolation + file matching ────────────────────────
    variants = db.design_studio.variants
    vid_a = variants.create({"account_id": A, "name": "Hero A", "asset_id": "asset-a-1", "format": "1:1"})
    if variants.get_by_id(vid_a, account_id=B) is None:
        ok("tenant B cannot READ tenant A's variant")
    else:
        no("LEAK: tenant B read tenant A's variant")
    if variants.update(vid_a, {"name": "defaced"}, account_id=B) is False:
        ok("tenant B cannot PATCH tenant A's variant")
    else:
        no("LEAK: tenant B patched tenant A's variant")
    if variants.delete(vid_a, account_id=B) is False:
        ok("tenant B cannot DELETE tenant A's variant")
    else:
        no("LEAK: tenant B deleted tenant A's variant")

    vm = imp.parse_variant_metrics(content="variant,impressions,clicks,orders,spend\nHero A,1000,12,3,4.20\nGhost variant,5,1,0,0.10\n")
    if vm["rows"][0]["clicks"] == 12.0 and vm["rows"][1]["variant"] == "Ghost variant":
        ok("variant metrics file parses reliably")
    else:
        no(f"variant metrics parse wrong: {vm['rows']}")
    variants.add_metric({"account_id": A, "variant_id": vid_a, "source": "file",
                         "impressions": 1000, "clicks": 12, "orders": 3, "spend": 4.2})
    if variants.metrics_for_variant(B, vid_a) == []:
        ok("tenant B sees none of tenant A's variant metrics")
    else:
        no("LEAK: tenant B read tenant A's variant metrics")
    a_metrics = variants.metrics_for_variant(A, vid_a)
    if len(a_metrics) == 1 and a_metrics[0]["clicks"] == 12:
        ok("tenant A sees its own metric row intact")
    else:
        no("tenant A metric row wrong")

    # ── Brief honesty: UNKNOWN kept, bias attached, no winner without clicks ─
    brief = imp.build_brief(
        terms=terms.list_for_account(A),
        brand={"audience": "home bakers", "voice": "warm", "promise": "Bakes better."},
        keywords=["tumbler"],
    )
    ranked = brief["ranked_terms"]
    unknown_rows = [r for r in ranked if r["confidence"]["sample"] == "UNKNOWN"]
    if unknown_rows:
        ok("a term without a clicks column ranks with sample=UNKNOWN (never a zero-size claim)")
    else:
        no("no UNKNOWN sample label survived the brief")
    if all(r["bias"] for r in ranked if r["confidence"]["clicks"] is not None):
        ok("every ranking that reads clicks carries the click-only caveat")
    else:
        no("a ranking read clicks without the caveat")
    if "No image or video is generated" in " ".join(brief["notes"]):
        ok("the brief states that nothing was generated")
    else:
        no("the brief does not state the no-generation boundary")

    layer.close()
    try:
        os.unlink(tmp.name)
    except OSError:
        pass

    print(f"\nIMPORT + VARIANT FIXTURES: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:\n  " + "\n  ".join(FAILURES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
