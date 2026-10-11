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
    # Sponsored Brands bulksheet: creative + product-collection entities.
    sb = [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Creative ID",
         "Product Collection ID", "State"],
        ["Sponsored Brands", "Creative", "Update", "C100", "A200", "CR700", "", "enabled"],
        ["Sponsored Brands", "Product Collection", "Update", "C100", "A200", "", "PC800", "enabled"],
    ]
    # Amazon Ads error report: the bulksheet shape plus an Error column.
    ads_err = [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID", "Error"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K300", "Bid is invalid: must be a number"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K999", "Keyword does not exist"],
    ]
    # Seller Central processing report (TSV): sku + error columns.
    listing_err = (
        "sku\terror-type\terror-message\n"
        "SKU-1\tError\tThe value provided for standard_price is invalid\n"
        "SKU-9\tError\tThe SKU does not exist in this marketplace\n"
    ).encode()
    # A current product-detail template (beyond price/quantity).
    detail = [
        ["item_sku", "update_delete", "bullet_point1", "bullet_point2", "product_description",
         "generic_keywords", "standard_price", "quantity"],
        ["SKU-1", "PartialUpdate", "Keeps drinks cold 24h", "Fits every cup holder",
         "A 20oz stainless steel tumbler.", "tumbler steel insulated", "24.99", "10"],
    ]
    # An OLD template: no operation column at all.
    old_listing = [
        ["item_sku", "item_name", "standard_price"],
        ["SKU-1", "Stainless Steel Tumbler 20oz", "24.99"],
    ]
    # Before/after metric files for the performance comparison.
    metrics_before = [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID",
         "Impressions", "Clicks", "Spend", "Sales", "Orders"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K300", 340, 12, 4.20, 20.00, 1],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K301", 90, 3, 1.10, 5.00, 0],
    ]
    metrics_after = [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID",
         "Impressions", "Clicks", "Spend", "Sales", "Orders"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K300", 400, 18, 6.00, 25.00, 2],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K302", 30, 1, 0.40, 0.00, 0],
    ]
    return {
        "sp_bulksheet.xlsx": xlsx_bytes([("Sponsored Products Campaigns", sp_sheet)]),
        "sp_search_terms.xlsx": xlsx_bytes([("Search Term Report", search_terms)]),
        "listing_template.txt": ("\n".join("\t".join(str(c) for c in r) for r in listing) + "\n").encode(),
        "brand_analytics.csv": ("\n".join(",".join(str(c) for c in r) for r in ba) + "\n").encode(),
        "aplus_list.csv": ("\n".join(",".join(str(c) for c in r) for r in aplus) + "\n").encode(),
        "sb_bulksheet.xlsx": xlsx_bytes([("Sponsored Brands Campaigns", sb)]),
        "sp_error_report.xlsx": xlsx_bytes([("Sponsored Products Campaigns", ads_err)]),
        "listing_processing_report.txt": listing_err,
        "listing_detail_template.txt": ("\n".join("\t".join(str(c) for c in r) for r in detail) + "\n").encode(),
        "listing_old_template.txt": ("\n".join("\t".join(str(c) for c in r) for r in old_listing) + "\n").encode(),
        "metrics_before.xlsx": xlsx_bytes([("Sponsored Products Campaigns", metrics_before)]),
        "metrics_after.xlsx": xlsx_bytes([("Sponsored Products Campaigns", metrics_after)]),
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
        "sb_bulksheet.xlsx": "ads_bulksheet",
        "sp_error_report.xlsx": "ads_error_report",
        "listing_processing_report.txt": "listing_processing_report",
        "listing_detail_template.txt": "listing_template",
        "listing_old_template.txt": "listing_template",
        "metrics_before.xlsx": "ads_bulksheet",
        "metrics_after.xlsx": "ads_bulksheet",
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

    # ── A+ copy slots: operator text or UNKNOWN, never invented (item 6) ───
    pack2 = C.build_aplus_pack(aplus, [], {"upload_id": "u3", "filename": "aplus_list.csv", "checksum": aplus["checksum"]},
                               copy={"headline": "Built for the job"})
    slots = {s["slot"]: s for s in pack2["copy_slots"]}
    if slots["headline"]["text"] == "Built for the job" and slots["headline"]["source"] == "operator":
        ok("A+ copy: an operator-supplied headline is carried with its source")
    else:
        no(f"A+ copy headline wrong: {json.dumps(slots['headline'])}")
    if slots["body"]["text"] is None and "UNKNOWN" in (slots["body"]["note"] or "") and slots["cta"]["text"] is None:
        ok("A+ copy: empty slots stay UNKNOWN with a write-it-yourself note (nothing generated)")
    else:
        no(f"A+ copy empty slots wrong: {json.dumps(slots)}")

    # ── Sponsored Brands deltas: creative + product-collection entities ────
    sb = P.parse_upload("sb_bulksheet.xlsx", fx["sb_bulksheet.xlsx"])
    sb_props = C.build_proposals(sb, [
        {"sheet": "Sponsored Brands Campaigns", "row_index": 0, "op": "Update", "fields": {"state": "paused"}, "reason": "pause creative"},
        {"sheet": "Sponsored Brands Campaigns", "row_index": 1, "op": "Update", "fields": {"state": "paused"}, "reason": "pause collection"},
    ], {"upload_id": "u-sb", "filename": "sb_bulksheet.xlsx", "checksum": sb["checksum"], "now": now.isoformat()})
    if sb_props[0]["id_field"] == "creative_id" and sb_props[0]["id_value"] == "CR700" and not sb_props[0]["blocks"]:
        ok("SB delta: a Creative row resolves to creative_id (ID copied exactly)")
    else:
        no(f"SB creative row wrong: {json.dumps(sb_props[0])[:200]}")
    if sb_props[1]["id_field"] == "product_collection_id" and sb_props[1]["id_value"] == "PC800" and not sb_props[1]["blocks"]:
        ok("SB delta: a Product Collection row resolves to product_collection_id")
    else:
        no(f"SB collection row wrong: {json.dumps(sb_props[1])[:200]}")
    sb_delta = W.write_delta(sb["sheets"], [p for p in sb_props if not p["blocks"]], format="xlsx")
    sb_written = P.parse_upload("sb-change.xlsx", sb_delta["content"])
    sb_rt = C.validate_roundtrip(sb, sb_written, [p for p in sb_props if not p["blocks"]],
                                 source_content=fx["sb_bulksheet.xlsx"], written_content=sb_delta["content"])
    if sb_written["kind"] == "ads_bulksheet" and len(sb_written["sheets"][0]["rows"]) == 2 and sb_rt["ok"]:
        ok("SB delta: two changed rows written (only changed rows), round-trip clean")
    else:
        no(f"SB delta write/round-trip wrong: {json.dumps(sb_rt)[:200]}")

    # ── Product-detail template: columns beyond price/quantity (item 4) ────
    detail = P.parse_upload("listing_detail_template.txt", fx["listing_detail_template.txt"])
    dsheet = detail["sheets"][0]
    dmap = dsheet["mapped"]
    if all(dmap.get(c) is not None for c in ("sku", "update_delete", "bullet1", "bullet2", "description", "generic_keywords")):
        ok("product-detail template: bullet/description/keyword columns are mapped")
    else:
        no(f"product-detail columns missing: {dmap}")
    dprop = C.build_proposals(detail, [{
        "sheet": dsheet["name"], "row_index": 0, "op": "Update",
        "fields": {"bullet1": "Keeps drinks cold for 24 hours"}, "reason": "clearer bullet",
    }], {"upload_id": "u-d", "filename": "listing_detail_template.txt", "checksum": detail["checksum"], "now": now.isoformat()})[0]
    ddelta = W.write_delta(detail["sheets"], [dprop], format="tsv")
    dwritten = P.parse_upload("detail-change.txt", ddelta["content"])
    drt = C.validate_roundtrip(detail, dwritten, [dprop], source_content=fx["listing_detail_template.txt"], written_content=ddelta["content"])
    if dprop["op_value"] == "PartialUpdate" and dwritten["sheets"][0]["normalized"][0]["bullet1"] == "Keeps drinks cold for 24 hours" and drt["ok"]:
        ok("product-detail delta: bullet update written as PartialUpdate; round-trip clean")
    else:
        no(f"product-detail delta wrong: {json.dumps(drt)[:200]}")
    if "update_delete" not in detail["missing_columns"] and "sku" not in detail["missing_columns"]:
        ok("product-detail template: required columns (sku + operation) present, no missing-column entry")
    else:
        no(f"product-detail required columns wrongly reported: {detail['missing_columns']}")

    # ── Old-template warning: no operation column (item 3) ─────────────────
    old = P.parse_upload("listing_old_template.txt", fx["listing_old_template.txt"])
    if any("OLD or partial template" in n for n in old["notes"]):
        ok("old-template warning: a template without an operation column is flagged for re-download")
    else:
        no(f"old-template warning missing: {old['notes']}")
    if any("update_delete" in m for m in old["missing_columns"]):
        ok("old-template warning: the missing operation column is listed in missing_columns")
    else:
        no(f"missing update_delete not reported: {old['missing_columns']}")

    # ── Processing report: detection + row-level matching (item 2) ─────────
    change_parsed = P.parse_upload("change.xlsx", delta["content"])
    err = P.parse_upload("sp_error_report.xlsx", fx["sp_error_report.xlsx"])
    m = C.match_processing_report(err, change_parsed, approved_all)
    if m["matched_count"] == 1 and m["unmatched_count"] == 1:
        ok("ads error report: 1 row matched to the change file, 1 unmatched row reported (never guessed)")
    else:
        no(f"ads error match counts wrong: {json.dumps(m)[:200]}")
    hit = m["matches"][0]
    if hit["proposal_id"] == approved_all[0]["id"] and "Bid is invalid" in hit["cause"] and "bid" in (hit["fix_hint"] or "").lower():
        ok("ads error match: the row is linked to its proposal; the cause is quoted and the bid hint is specific")
    else:
        no(f"ads error match linkage wrong: {json.dumps(hit)[:240]}")
    if "not matched" in m["unmatched"][0]["cause"]:
        ok("ads error report: an id that is not in the change file is reported unmatched")
    else:
        no(f"unmatched cause wrong: {json.dumps(m['unmatched'][0])[:200]}")

    lpr = P.parse_upload("listing_processing_report.txt", fx["listing_processing_report.txt"])
    lm = C.match_processing_report(lpr, lwritten, [lp])
    if lpr["kind"] == "listing_processing_report" and lm["matched_count"] == 1 and lm["unmatched_count"] == 1 and lm["matches"][0]["proposal_id"] == lp["id"]:
        ok("Seller Central processing report: SKU row matched to the listing change and its proposal")
    else:
        no(f"listing processing match wrong: {json.dumps(lm)[:240]}")
    if "not accepted" in (lm["matches"][0]["fix_hint"] or "").lower() and "SKU-9" in (lm["unmatched"][0]["id_value"] or ""):
        ok("listing processing report: cause quoted + fix hint given; unknown SKU reported")
    else:
        no(f"listing processing hints wrong: {json.dumps(lm['matches'][0])[:200]}")

    # ── Corrected resubmittable file: new version, originals untouched ─────
    prep = C.build_corrected_change(change_parsed, [
        {"row_index": 1, "drop": True},                     # drop the second row
        {"row_index": 0, "fields": {"bid": "0.85"}},        # correct the matched row
    ])
    if prep["dropped"] == 1 and len(prep["payloads"]) == len(approved_all) - 1 and not prep["errors"]:
        ok("corrected file prep: the dropped row is removed, the corrected row kept, zero errors")
    else:
        no(f"corrected prep wrong: {json.dumps(prep)[:240]}")
    corr_delta = W.write_delta(change_parsed["sheets"], prep["payloads"], format="xlsx")
    corr_parsed = P.parse_upload("corrected.xlsx", corr_delta["content"])
    corr_row = corr_parsed["sheets"][0]["normalized"][0]
    if corr_row.get("bid") == "0.85" and len(corr_parsed["sheets"][0]["rows"]) == len(prep["payloads"]):
        ok("corrected file: the bid correction is written and only the kept rows appear")
    else:
        no(f"corrected file wrong: {json.dumps(corr_row)[:200]}")
    corr_rt = C.validate_roundtrip(change_parsed, corr_parsed, prep["payloads"],
                                   source_content=delta["content"], written_content=corr_delta["content"])
    if corr_rt["ok"]:
        ok("corrected file round-trip: only the corrections differ from the change file")
    else:
        no(f"corrected round-trip failed: {json.dumps(corr_rt)[:240]}")
    if len(change_parsed["sheets"][0]["rows"]) == len(approved_all):
        ok("corrected file: the change file it was built from is untouched (same row count)")
    else:
        no("the source change file was mutated")
    if HAS_OPENPYXL:
        openpyxl.load_workbook(io.BytesIO(corr_delta["content"]))
        ok("corrected file: Excel-openable (openpyxl)")
    else:
        print("NOT RUN  corrected-file Excel-openability (openpyxl missing)")
    # A correction naming a column the file does not carry is refused with a message.
    bad_prep = C.build_corrected_change(change_parsed, [{"row_index": 0, "fields": {"bullet1": "nope"}}])
    if bad_prep["errors"] and "not a column" in bad_prep["errors"][0]:
        ok("corrected file: a correction for a column the file does not carry is refused with a stated reason")
    else:
        no(f"unknown-column correction not refused: {json.dumps(bad_prep)[:200]}")

    # ── Before/after comparison: sample, ranges, no-causation (item 5) ─────
    before_p = P.parse_upload("metrics_before.xlsx", fx["metrics_before.xlsx"])
    after_p = P.parse_upload("metrics_after.xlsx", fx["metrics_after.xlsx"])
    cmp = C.compare_performance(before_p, after_p, {"before_from": "2026-09-01", "before_to": "2026-09-14",
                                                    "after_from": "2026-09-15", "after_to": "2026-09-28"})
    rows_by_key = {r["key"]: r for r in cmp["rows"]}
    k300 = rows_by_key.get("K300")
    if k300 and k300["delta_clicks"] == 6.0 and k300["present_in"] == "both" and k300["metrics"]["spend"]["before"] == 4.2:
        ok("comparison: per-entity before/after values and the click delta are computed")
    else:
        no(f"comparison K300 wrong: {json.dumps(k300)[:240]}")
    if k300 and k300["sample"].get("sample") and k300["observed"]["before_from"] == "2026-09-01" and k300["observed"]["after_to"] == "2026-09-28":
        ok("comparison: sample-size label + observed date ranges are attached per entity")
    else:
        no(f"comparison sample/ranges wrong: {json.dumps(k300)[:240]}")
    if rows_by_key["K301"]["metrics"]["clicks"]["after"] == "UNKNOWN" and rows_by_key["K302"]["metrics"]["clicks"]["before"] == "UNKNOWN":
        ok("comparison: a metric missing from one file is UNKNOWN (never 0)")
    else:
        no(f"comparison UNKNOWN handling wrong: {json.dumps(cmp['rows'])[:240]}")
    if "NO CAUSATION" in cmp["causation"] and "engineering choice" in cmp["stale_window_note"] and cmp["stale_window_days"] == 14:
        ok("comparison: explicit no-causation notice; the 14-day window is labelled an engineering choice")
    else:
        no(f"comparison notices wrong: {json.dumps({k: cmp[k] for k in ('causation', 'stale_window_note')})[:240]}")

    print(f"\nAMAZON FILE INTEGRATION: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:\n  " + "\n  ".join(FAILURES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
