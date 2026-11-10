"""Generate the Amazon-file test fixtures (run once; the outputs are committed).

The fixtures are deliberately built with openpyxl (a DIFFERENT writer than the
stdlib one under test) so the parser proves real interop.

Run:  python tools/_make_amazon_fixtures.py
"""
from __future__ import annotations

import io
from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parent / "fixtures" / "amazon_files"
SAMPLES = Path(__file__).resolve().parents[1] / "northstar-os-ui" / "public" / "samples" / "amazon-files"


def xlsx_bytes(sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets:
        ws = wb.create_sheet(title=name[:31])
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

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

    (OUT / "sp_bulksheet.xlsx").write_bytes(xlsx_bytes([("Sponsored Products Campaigns", sp_sheet)]))
    (OUT / "sp_search_terms.xlsx").write_bytes(xlsx_bytes([("Search Term Report", search_terms)]))
    (OUT / "listing_template.txt").write_text("\n".join("\t".join(str(c) for c in r) for r in listing) + "\n", encoding="utf-8")
    (OUT / "brand_analytics.csv").write_text("\n".join(",".join(str(c) for c in r) for r in ba) + "\n", encoding="utf-8")
    (OUT / "aplus_list.csv").write_text("\n".join(",".join(str(c) for c in r) for r in aplus) + "\n", encoding="utf-8")
    (OUT / "legacy.xls").write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
    (OUT / "junk.csv").write_text("hello,world\n1,2\n", encoding="utf-8")
    # Reports + comparison fixtures used by the API/UI harnesses.
    (OUT / "ads_error_report.xlsx").write_bytes(xlsx_bytes([("Sponsored Products Campaigns", [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID", "Error"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K300", "Bid is invalid: must be a number"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K999", "Keyword does not exist"],
    ])]))
    (OUT / "listing_processing_report.txt").write_text(
        "sku\terror-type\terror-message\n"
        "SKU-1\tError\tThe value provided for standard_price is invalid\n"
        "SKU-9\tError\tThe SKU does not exist in this marketplace\n", encoding="utf-8")
    (OUT / "metrics_before.xlsx").write_bytes(xlsx_bytes([("Sponsored Products Campaigns", [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID",
         "Impressions", "Clicks", "Spend", "Sales", "Orders"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K300", 340, 12, 4.20, 20.00, 1],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K301", 90, 3, 1.10, 5.00, 0],
    ])]))
    (OUT / "metrics_after.xlsx").write_bytes(xlsx_bytes([("Sponsored Products Campaigns", [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID",
         "Impressions", "Clicks", "Spend", "Sales", "Orders"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K300", 400, 18, 6.00, 25.00, 2],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K302", 30, 1, 0.40, 0.00, 0],
    ])]))

    # ── The seller-facing SAMPLE PACK (item 11) ─────────────────────────────
    # Synthetic, redacted fixtures the seller can download and try the whole
    # round-trip with before touching real account files.
    SAMPLES.mkdir(parents=True, exist_ok=True)
    sb = [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Creative ID",
         "Product Collection ID", "State"],
        ["Sponsored Brands", "Creative", "Update", "C100", "A200", "CR700", "", "enabled"],
        ["Sponsored Brands", "Product Collection", "Update", "C100", "A200", "", "PC800", "enabled"],
    ]
    ads_err = [
        ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID", "Error"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K300", "Bid is invalid: must be a number"],
        ["Sponsored Products", "Keyword", "Update", "C100", "A200", "K999", "Keyword does not exist"],
    ]
    listing_err = (
        "sku\terror-type\terror-message\n"
        "SKU-1\tError\tThe value provided for standard_price is invalid\n"
        "SKU-9\tError\tThe SKU does not exist in this marketplace\n"
    )
    detail = [
        ["item_sku", "update_delete", "bullet_point1", "bullet_point2", "product_description",
         "generic_keywords", "standard_price", "quantity"],
        ["SKU-1", "PartialUpdate", "Keeps drinks cold 24h", "Fits every cup holder",
         "A 20oz stainless steel tumbler.", "tumbler steel insulated", "24.99", "10"],
    ]
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
    (SAMPLES / "sp_bulksheet.xlsx").write_bytes(xlsx_bytes([("Sponsored Products Campaigns", sp_sheet)]))
    (SAMPLES / "sp_search_terms.xlsx").write_bytes(xlsx_bytes([("Search Term Report", search_terms)]))
    (SAMPLES / "listing_template.txt").write_text("\n".join("\t".join(str(c) for c in r) for r in listing) + "\n", encoding="utf-8")
    (SAMPLES / "listing_detail_template.txt").write_text("\n".join("\t".join(str(c) for c in r) for r in detail) + "\n", encoding="utf-8")
    (SAMPLES / "aplus_list.csv").write_text("\n".join(",".join(str(c) for c in r) for r in aplus) + "\n", encoding="utf-8")
    (SAMPLES / "sb_bulksheet.xlsx").write_bytes(xlsx_bytes([("Sponsored Brands Campaigns", sb)]))
    (SAMPLES / "ads_error_report.xlsx").write_bytes(xlsx_bytes([("Sponsored Products Campaigns", ads_err)]))
    (SAMPLES / "listing_processing_report.txt").write_text(listing_err, encoding="utf-8")
    (SAMPLES / "metrics_before.xlsx").write_bytes(xlsx_bytes([("Sponsored Products Campaigns", metrics_before)]))
    (SAMPLES / "metrics_after.xlsx").write_bytes(xlsx_bytes([("Sponsored Products Campaigns", metrics_after)]))
    (SAMPLES / "README.txt").write_text(
        "NorthstarOS Amazon file samples (synthetic)\n"
        "===========================================\n\n"
        "These are REDACTED, synthetic files with fake IDs (C100, K300, SKU-1, B01TEST0001).\n"
        "Use them to try the whole round-trip before touching a real account file:\n\n"
        "1. sp_bulksheet.xlsx ........ Ads Sponsored Products bulksheet (what you download from Ads).\n"
        "2. sb_bulksheet.xlsx ........ Sponsored Brands bulksheet with Creative / Product Collection rows.\n"
        "3. sp_search_terms.xlsx ..... Search-term report (feeds briefs).\n"
        "4. listing_template.txt ..... Seller Central listing update template (tab-delimited).\n"
        "5. listing_detail_template.txt  Product-detail template (bullets, description, keywords).\n"
        "6. aplus_list.csv ........... A+ ASIN list (produces an asset pack, not a module file).\n"
        "7. ads_error_report.xlsx .... Ads processing report with an Error column (upload after a real submit).\n"
        "8. listing_processing_report.txt  Seller Central processing report (sku + error columns).\n"
        "9. metrics_before.xlsx / metrics_after.xlsx  Two periods for the before/after comparison.\n\n"
        "Nothing here contacts Amazon. The workflow is: download from Amazon, upload here,\n"
        "approve rows, download the change file, upload it to Amazon yourself.\n",
        encoding="utf-8",
    )

    print(f"fixtures written to {OUT}")
    for f in sorted(OUT.iterdir()):
        print(f"  {f.name} ({f.stat().st_size} bytes)")
    print(f"samples written to {SAMPLES}")
    for f in sorted(SAMPLES.iterdir()):
        print(f"  {f.name} ({f.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
