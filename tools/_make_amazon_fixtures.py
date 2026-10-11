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

    print(f"fixtures written to {OUT}")
    for f in sorted(OUT.iterdir()):
        print(f"  {f.name} ({f.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
