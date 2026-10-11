"""Amazon FILE integration tests — parsers, writers, proposals, round-trip.

Fixtures are built with openpyxl on the HOST (a different writer than the
stdlib one under test), so the parser proves real interop. The written change
files are then re-opened with openpyxl to prove Excel-openability.

Run:  python tools/test_amazon_files.py
Exit: 0 = all green, 1 = a failure, 2 = harness error (missing host dependency).
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

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


def xlsx_bytes(sheets: list[tuple[str, list[list]]]) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets:
        ws = wb.create_sheet(title=name[:31])
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_fixtures() -> dict[str, bytes]:
    sp_sheet = [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID",
         "Campaign Name", "Ad Group Name", "Keyword Text", "Match Type", "Bid", "State"],
        ["Sponsored Products", "Campaign", "Update", "C100", "", "", "Launch", "", "", "", "", "enabled"],
        ["Sponsored Products", "Ad Group", "Update", "C100", "A200", "", "Launch", "Broad", "", "", "", "enabled"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K300", "Launch", "Broad", "tumbler steel", "broad", "0.75", "enabled"],
        ["Sponsored Products", "Keyword", "", "C100", "A200", "", "Launch", "Broad", "orphan keyword", "exact", "1.10", "enabled"],
    ]
    search_terms = [
        ["Customer Search Term", "Campaign ID", "Ad Group ID", "Clicks", "Impressions", "Spend", "Date"],
        ["cold brew filter", "C100", "A200", 12, 340, 4.20, "2026-10-01"],
        ["tumbler steel", "C100", "A200", 8, 210, 3.10, "2026-10-03"],
    ]
    listing = [
        ["item_sku", "item_name", "external_product_id", "update_delete", "standard_price", "quantity"],
        ["SKU-1", "Stainless Steel Tumbler 20oz", "B01TEST0001", "PartialUpdate", "24.99", "10"],
    ]
    ba = [
        ["Search Query", "Search Frequency Rank", "Search Query Score"],
        ["insulated tumbler", "41", "88.2"],
    ]
    aplus = [
        ["asin", "contentReferenceKey"],
        ["B01TEST0001", "mod-1"],
        ["B01TEST0002", "mod-1"],
    ]
    return {
        "sp_bulksheet.xlsx": xlsx_bytes([("Sponsored Products Campaigns", sp_sheet)]),
        "sp_search_terms.xlsx": xlsx_bytes([("Search Term Report", search_terms)]),
        "listing_template.txt": ("\n".join("\t".join(str(c) for c in r) for r in listing) + "\n").encode(),
        "brand_analytics.csv": ("\n".join(",".join(str(c) for c in r) for r in ba) + "\n").encode(),
        "aplus_list.csv": ("\n".join(",".join(str(c) for c in r) for r in aplus) + "\n").encode(),
        "legacy.xls": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64,
        "junk.csv": b"hello,world\n1,2\n",
    }


def main() -> int:
    if not HAS_OPENPYXL:
        print("NOT RUN  openpyxl is required on the host to build fixtures and prove Excel-openability.")
        return 2

    import amazon_file_parsers as P
    import amazon_file_writers as W
    import amazon_change_files as C

    fx = make_fixtures()

    # ── Detection ──────────────────────────────────────────────────────────
    expected = {
        "sp_bulksheet.xlsx": "ads_bulksheet",
        "sp_search_terms.xlsx": "ads_search_terms",
        "listing_template.txt": "listing_template",
        "brand_analytics.csv": "brand_analytics",
        "aplus_list.csv": "aplus_asin_list",
        "legacy.xls": "unsupported_xls",
        "junk.csv": "unknown",
    }
    for name, want in expected.items():
        det = P.detect_amazon_file(name, fx[name])
        if det["kind"] == want:
            ok(f"detection: {name} -> {want}")
        else:
            no(f"detection: {name} -> {det['kind']} (wanted {want}) :: {det.get('why')}")

    # ── Parse: bulksheet ───────────────────────────────────────────────────
    parsed = P.parse_upload("sp_bulksheet.xlsx", fx["sp_bulksheet.xlsx"])
    sheet = parsed["sheets"][0]
    kw = next(r for r in sheet["normalized"] if r.get("keyword_id") == "K300")
    if kw.get("bid") == "0.75" and kw.get("match_type") == "broad" and kw.get("campaign_id") == "C100":
        ok("bulksheet: keyword row parsed with exact IDs and values")
    else:
        no(f"bulksheet keyword row wrong: {kw}")
    if parsed["missing_columns"] == [] and "campaign_id" in parsed["columns_found"]:
        ok("bulksheet: required columns present, none missing")
    else:
        no(f"bulksheet columns wrong: found={parsed['columns_found']} missing={parsed['missing_columns']}")

    # ── Parse: search terms with an ISO date range ─────────────────────────
    st = P.parse_upload("sp_search_terms.xlsx", fx["sp_search_terms.xlsx"])
    if st["kind"] == "ads_search_terms" and st["observed_from"] == "2026-10-01" and st["observed_to"] == "2026-10-03":
        ok("search-term sheet: observed range derived from its own ISO dates (2026-10-01..03)")
    else:
        no(f"search-term range wrong: {st['observed_from']}..{st['observed_to']} kind={st['kind']}")

    # ── Parse: missing columns reported, not invented ──────────────────────
    listing = P.parse_upload("listing_template.txt", fx["listing_template.txt"])
    if listing["kind"] == "listing_template" and listing["sheets"][0]["normalized"][0]["sku"] == "SKU-1":
        ok("listing template: TSV parsed with its own SKU/update_delete vocabulary")
    else:
        no(f"listing template parse wrong: {listing['kind']}")

    ba = P.parse_upload("brand_analytics.csv", fx["brand_analytics.csv"])
    if ba["kind"] == "brand_analytics":
        ok("Brand Analytics: CSV detected and parsed")
    else:
        no(f"BA parse wrong: {ba['kind']}")

    legacy = P.parse_upload("legacy.xls", fx["legacy.xls"])
    if legacy["kind"] == "unsupported_xls" and "re-save" in " ".join(legacy["notes"]):
        ok("legacy .xls: honestly refused with the stated fix (no guessing)")
    else:
        no(f"legacy xls handling wrong: {legacy['kind']}")

    # ── Proposals: before/after, blocks, flags, guardrail, staleness ───────
    now = datetime.now(timezone.utc)
    meta = {
        "upload_id": "u1", "filename": "sp_bulksheet.xlsx", "checksum": parsed["checksum"],
        "downloaded_at": (now - timedelta(days=30)).date().isoformat(),
        "spend_limit_cents": 100, "now": now.isoformat(),
    }
    requested = [
        {"sheet": sheet["name"], "row_index": 2, "op": "Update", "fields": {"bid": "0.95"}, "reason": "raise bid on a converting term"},
        {"sheet": sheet["name"], "row_index": 0, "op": "Archive", "fields": {}, "reason": "retire the campaign"},
        {"sheet": sheet["name"], "row_index": 3, "op": "Update", "fields": {"bid": "1.20"}, "reason": "orphan row with no keyword id"},
        {"sheet": sheet["name"], "row_index": 2, "op": "Update", "fields": {"bid": "1.50"}, "reason": "above the seller limit"},
    ]
    props = C.build_proposals(parsed, requested, meta)
    p0, p1, p2, p3 = props
    if p0["status"] == "proposed" and p0["before"]["bid"] == "0.75" and p0["after"]["bid"] == "0.95" and p0["id_value"] == "K300":
        ok("proposal: before/after and the exact ID recorded for the bid change")
    else:
        no(f"proposal 0 wrong: {json.dumps(p0)[:200]}")
    if p1["op_value"] == "Archive" and p1["id_value"] == "C100":
        ok("proposal: Archive carries its operation value and the campaign ID")
    else:
        no(f"proposal 1 wrong: {json.dumps(p1)[:160]}")
    if p2["status"] == "blocked" and any("missing-id" in b for b in p2["blocks"]):
        ok("proposal: a row with an empty Keyword ID is BLOCKED (never written)")
    else:
        no(f"proposal 2 should be blocked: {json.dumps(p2)[:200]}")
    if p3["requires_second_confirmation"] and "exceeds your limit" in " ".join(p3["spend_notes"]):
        ok("spend guardrail: a bid above the seller limit requires a second confirmation")
    else:
        no(f"spend guardrail missing: {json.dumps(p3)[:200]}")
    if all(p["stale"] and p["stale_note"] for p in props):
        ok("stale source: a 30-day-old download carries the warning (not a silent pass)")
    else:
        no("staleness was not flagged")
    if p0["evidence"]["checksum"] == parsed["checksum"] and p0["evidence"]["filename"] == "sp_bulksheet.xlsx":
        ok("proposal: evidence carries the file name, checksum and download date")
    else:
        no("proposal evidence incomplete")

    # Title flags in a listing change (date-sensitive FLAGS, never blocks).
    long_title = "Stainless Steel Tumbler 20oz! Free Shipping Tumbler Tumbler Tumbler Premium Quality Cold Brew Edition"
    lp = C.build_proposals(listing, [{
        "sheet": listing["sheets"][0]["name"], "row_index": 0, "op": "Update",
        "fields": {"title": long_title},
        "reason": "title rewrite",
    }], {"upload_id": "u2", "filename": "listing_template.txt", "checksum": listing["checksum"], "downloaded_at": now.date().isoformat(), "spend_limit_cents": None, "now": now.isoformat()})[0]
    flagged_rules = {f["rule"] for f in lp["title_flags"]}
    if lp["status"] == "proposed" and {"title-length-75", "title-no-promotional", "title-special-chars", "title-same-word-twice"} <= flagged_rules:
        ok("listing writer: title change carries all four rule FLAGS (and is not blocked)")
    else:
        no(f"title flags wrong: status={lp['status']} rules={flagged_rules}")

    # ── Approval: blocked + second confirmation refused; then approved ─────
    res = C.approve_proposals(props, [p0["id"], p2["id"]])
    if res["approved"] == [p0["id"]] and any("blocked" in r["reason"] for r in res["refused"]):
        ok("approval: blocked rows can never be approved")
    else:
        no(f"approval wrong: {res}")
    res2 = C.approve_proposals(props, [p3["id"]])
    if res2["approved"] == [] and any("second confirmation" in r["reason"] for r in res2["refused"]):
        ok("approval: a spend-limit row is refused without the second confirmation")
    else:
        no(f"second confirmation wrong: {res2}")
    res3 = C.approve_proposals(props, [p3["id"]], second_confirmation=True)
    if res3["approved"] == [p3["id"]]:
        ok("approval: the same row approves WITH the explicit second confirmation")
    else:
        no(f"second confirmation with flag failed: {res3}")

    approved_all = [p for p in props if p["status"] == "approved"]

    # ── Write: delta xlsx with the source column order, changed rows only ──
    delta = W.write_delta(parsed["sheets"], approved_all, format="xlsx")
    written = P.parse_upload("change.xlsx", delta["content"])
    if written["kind"] == "ads_bulksheet" and len(written["sheets"][0]["rows"]) == len(approved_all):
        ok(f"delta xlsx: {len(approved_all)} approved row(s) written, nothing else")
    else:
        no(f"delta row count wrong: {len(written['sheets'][0]['rows'])} for {len(approved_all)} approved")
    wsheet = written["sheets"][0]
    if wsheet["headers"] == parsed["sheets"][0]["headers"]:
        ok("delta xlsx: the source column order is preserved exactly")
    else:
        no(f"column order changed: {wsheet['headers']}")

    if HAS_OPENPYXL:
        wb = openpyxl.load_workbook(io.BytesIO(delta["content"]))
        ws = wb.active
        if ws.cell(row=1, column=1).value == "Product" and ws.max_row == len(approved_all) + 1:
            ok("Excel-openability: openpyxl opens the written xlsx with the expected shape")
        else:
            no(f"openpyxl could not read the written workbook correctly (max_row={ws.max_row})")
    else:
        print("NOT RUN  Excel-openability (openpyxl missing)")

    # ── Round-trip: approved-only differences ──────────────────────────────
    rt = C.validate_roundtrip(parsed, written, approved_all,
                              source_content=fx["sp_bulksheet.xlsx"], written_content=delta["content"])
    if rt["ok"] and rt["written_count"] == len(approved_all) and rt["source_checksum"] and rt["written_checksum"]:
        ok(f"round-trip: only the {len(approved_all)} approved change(s) differ; checksums recorded")
    else:
        no(f"round-trip failed: {json.dumps(rt)[:240]}")

    # ── Round-trip: a tampered written file is caught ──────────────────────
    tampered = P.parse_upload("change.xlsx", delta["content"])
    tampered["sheets"][0]["rows"][0][10] = "9.99"  # bid changed without approval
    rt_bad = C.validate_roundtrip(parsed, tampered, approved_all,
                                  source_content=fx["sp_bulksheet.xlsx"], written_content=delta["content"])
    if not rt_bad["ok"] and any("unapproved change" in v for v in rt_bad["violations"]):
        ok("round-trip: an unapproved cell change in the written file is CAUGHT")
    else:
        no(f"tamper not caught: {json.dumps(rt_bad)[:200]}")

    # ── Round-trip: no-op (zero approvals -> zero rows, zero differences) ──
    noop = W.write_delta(parsed["sheets"], [], format="xlsx")
    noop_parsed = P.parse_upload("noop.xlsx", noop["content"])
    rt_noop = C.validate_roundtrip(parsed, noop_parsed, [], source_content=fx["sp_bulksheet.xlsx"], written_content=noop["content"])
    if rt_noop["ok"] and rt_noop["written_count"] == 0:
        ok("round-trip no-op: with no approvals the written file has zero rows and zero differences")
    else:
        no(f"no-op failed: {json.dumps(rt_noop)[:200]}")

    # ── Listing delta (TSV): source order, op mapped to update_delete ──────
    ldelta = W.write_delta(listing["sheets"], [lp], format="tsv")
    lwritten = P.parse_upload("listing_change.txt", ldelta["content"])
    lrow = lwritten["sheets"][0]["normalized"][0]
    if lwritten["kind"] == "listing_template" and lrow["update_delete"] == "PartialUpdate" and lrow["title"] == lp["fields"]["title"]:
        ok("listing delta TSV: update_delete mapped from Update -> PartialUpdate; the title change is the only edit")
    else:
        no(f"listing delta wrong: {json.dumps(lrow)[:200]}")
    lrt = C.validate_roundtrip(listing, lwritten, [lp], source_content=fx["listing_template.txt"], written_content=ldelta["content"])
    if lrt["ok"]:
        ok("listing delta round-trip: only the approved title change differs")
    else:
        no(f"listing round-trip failed: {json.dumps(lrt)[:200]}")

    # ── Blank Operation is refused ─────────────────────────────────────────
    try:
        W.write_delta(parsed["sheets"], [{**p0, "op_value": None}], format="xlsx")
        no("a blank Operation was accepted - it must be refused")
    except ValueError:
        ok("writer refuses an intended change with a blank Operation")

    # ── A+ pack: an asset pack, NOT an uploadable module file ──────────────
    aplus = P.parse_upload("aplus_list.csv", fx["aplus_list.csv"])
    pack = C.build_aplus_pack(aplus, [{"name": "hero.png", "placement": "Premium full-width image", "alt_text": None}],
                              {"upload_id": "u3", "filename": "aplus_list.csv", "checksum": aplus["checksum"], "downloaded_at": now.date().isoformat()})
    if pack["uploadable_module_file"] is False and pack["asin_bulk_upload_limit"] is None and "UNKNOWN" in pack["asin_bulk_upload_limit_note"]:
        ok("A+ pack: not an uploadable module file; the ASIN bulk-upload limit is recorded UNKNOWN")
    else:
        no(f"A+ pack wrong: {json.dumps(pack)[:200]}")
    if pack["assets"][0]["alt_text"] is None and "UNKNOWN" in pack["assets"][0]["alt_text_note"] and pack["asins"] == ["B01TEST0001", "B01TEST0002"]:
        ok("A+ pack: assets carry the required-alt-text instruction; ASINs read from the file")
    else:
        no(f"A+ pack assets wrong: {json.dumps(pack['assets'])[:200]}")

    print(f"\nAMAZON FILE INTEGRATION: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:\n  " + "\n  ".join(FAILURES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
