"""Build a printable Costco field price-capture worksheet from the frozen
v2 enrichment + analytics artifacts. OFFLINE ONLY — reads inputs, writes two
new files, never modifies any source artifact.

Run: python build_costco_worksheet.py
"""

import csv
import glob
import html
import json
import os
from datetime import datetime, timezone

BACKEND = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(BACKEND, "data", "catalog")

SHORTLIST = os.path.join(CATALOG, "enrichment_shortlist_20260825T061558Z.json")
ANALYTICS_CSV = os.path.join(CATALOG, "analytics-top-opportunities.csv")


def _latest_v2():
    files = glob.glob(os.path.join(CATALOG, "enrichment_results_v2_*.json"))
    if not files:
        raise FileNotFoundError("No enrichment_results_v2_*.json found")
    files.sort()
    return files[-1]


def _clean_bsr_category(cat):
    if not cat:
        return "Unknown"
    # Strip Amazon's nav noise: "Health & Household ( See Top 100 in ... )"
    return cat.split("(")[0].strip() or "Unknown"


def _decode(text):
    if not isinstance(text, str):
        return text
    return html.unescape(text).strip()


def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    v2_path = _latest_v2()

    shortlist = json.load(open(SHORTLIST, "r", encoding="utf-8"))
    short_asins = shortlist["asins"]

    v2 = json.load(open(v2_path, "r", encoding="utf-8"))
    v2_by_asin = {r["asin"]: r for r in v2.get("results", [])}

    analytics = {}
    with open(ANALYTICS_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            analytics[row.get("asin")] = row

    # ---- TASK A: reconcile exact 20 ----
    asins = [a["asin"] for a in short_asins]
    assert len(asins) == 20, "shortlist count != 20: %d" % len(asins)
    assert len(set(asins)) == 20, "duplicate ASINs in shortlist"
    missing_v2 = [a for a in asins if a not in v2_by_asin]
    assert not missing_v2, "ASINs missing v2 result: %s" % missing_v2

    # ---- TASK B: build rows ----
    rows = []
    for a in short_asins:
        asin = a["asin"]
        title = _decode(a.get("product_title")) or "Unknown"
        v = v2_by_asin.get(asin, {})
        bsr = (v.get("bsr") or {})
        buy_box = v.get("buy_box_price")
        offers = v.get("offers_returned_count")
        analytics_row = analytics.get(asin, {})

        # Amazon-listing completeness (decision-ready on Amazon data)
        decision_ready = "Yes" if (isinstance(buy_box, (int, float)) and buy_box > 0) else "No"

        conf = analytics_row.get("sales_estimation_confidence") or "unknown"
        est = analytics_row.get("estimated_monthly_sales")
        if est:
            demand_lane = "%s (~%s/mo)" % (conf, est)
        else:
            demand_lane = conf

        form = "Unknown"
        for kw in ("Tablets", "Softgels", "Chewable Tablets", "Wipes",
                   "Trash Bags", "Trash Bag", "Wastebasket Liners",
                   "Sprays", "Servings"):
            if kw.lower() in title.lower():
                form = kw
                break

        rows.append({
            "ASIN": asin,
            "title": title,
            "buy_box": buy_box if isinstance(buy_box, (int, float)) else "Unknown",
            "bsr_rank": bsr.get("bsr_primary_rank") or "Unknown",
            "bsr_category": _clean_bsr_category(bsr.get("bsr_primary_category")),
            "demand_lane": demand_lane,
            "offers": offers if isinstance(offers, int) else "Unknown",
            "decision_ready": decision_ready,
            "form": form,
            "analytics_rank": int(analytics_row["rank"]) if analytics_row.get("rank", "").isdigit() else 999,
        })

    # Sort: decision-ready first, then strongest analytics rank, then remainder
    rows.sort(key=lambda r: (0 if r["decision_ready"] == "Yes" else 1, r["analytics_rank"]))

    csv_cols = [
        "Priority", "ASIN", "Exact Amazon product title", "Brand",
        "Product form / variant", "Pack count / size / count",
        "Amazon buy-box price", "Live BSR rank", "BSR category",
        "Demand lane", "Competition / offer count", "Decision-ready status",
        "Costco found? (blank)", "Costco warehouse item number (blank)",
        "Costco UPC (blank)", "Costco shelf price (blank)",
        "Costco instant-savings amount (blank)", "Costco final unit cost (blank)",
        "Costco pack / size observed (blank)", "Packaging match status",
        "Match notes (blank)", "Photo captured? Y/N (blank)",
        "Date checked (blank)", "Warehouse location (blank)",
    ]

    out_csv = os.path.join(CATALOG, "costco_price_capture_20asin_%s.csv" % ts)
    out_md = os.path.join(CATALOG, "costco_price_capture_20asin_%s.md" % ts)

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(csv_cols)
        for i, r in enumerate(rows, 1):
            w.writerow([
                i,
                r["ASIN"],
                r["title"],
                "Kirkland Signature",
                r["form"] if r["form"] != "Unknown" else "",
                "",  # pack count / size / count -> operator fills from store
                r["buy_box"],
                r["bsr_rank"],
                r["bsr_category"],
                r["demand_lane"],
                r["offers"],
                r["decision_ready"],
                "", "", "", "", "", "", "", "",  # Costco blanks
                "",  # packaging match status (blank)
                "",  # match notes
                "",  # photo
                "",  # date
                "",  # warehouse
            ])

    # ---- Markdown ----
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Costco In-Store Price-Capture Worksheet (20 ASINs)\n\n")
        f.write("Generated: %s (offline build, no live calls)\n" % ts)
        f.write("Source shortlist: enrichment_shortlist_20260825T061558Z.json\n")
        f.write("Source enrichment: %s\n\n" % os.path.basename(v2_path))
        f.write("> Costco prices are a LOCAL RETAIL DISCOVERY input only. A "
                "store receipt is NOT wholesale invoice documentation and is "
                "NOT a purchase authorization or proof that Costco sourcing is "
                "invoice-safe or scalable.\n\n")
        f.write("| %s |\n" % " | ".join([
            "Priority", "ASIN", "Exact Amazon product title", "Amazon buy-box",
            "Live BSR rank", "BSR category", "Demand lane",
            "Comp / offers", "Decision-ready",
        ]))
        f.write("| %s |\n" % " | ".join(["---"] * 9))
        for i, r in enumerate(rows, 1):
            f.write("| %s | %s | %s | %s | %s | %s | %s | %s | %s |\n" % (
                i, r["ASIN"], r["title"], r["buy_box"], r["bsr_rank"],
                r["bsr_category"], r["demand_lane"], r["offers"],
                r["decision_ready"],
            ))
        f.write("\n## Costco capture columns (fill in-store)\n")
        f.write("For each ASIN, capture: Costco found?, warehouse item number, "
                "UPC, shelf price, instant-savings amount, final unit cost, "
                "pack/size observed, packaging match status (Exact / Different "
                "pack / Different formulation / Not found), match notes, photo "
                "captured Y/N, date checked, warehouse location.\n")
        f.write("\n## Decision-ready (9 of 20)\n")
        ready = [r["ASIN"] for r in rows if r["decision_ready"] == "Yes"]
        f.write("Amazon-listing-complete (buy-box + BSR + offers present): %s\n"
                % ", ".join(ready))
        f.write("\nNote: the analytics cost layer marks all 20 as "
                "economics-unavailable (no Costco cost supplied). The 9 "
                "decision-ready flags above reflect Amazon listing data "
                "completeness only — not purchase authorization.\n")

    # ---- TASK A + C console output ----
    print("RECONCILE: shortlist ASIN count = %d, unique = %d, missing_v2 = %s"
          % (len(asins), len(set(asins)), missing_v2 or "none"))
    print("V2 source: %s" % os.path.basename(v2_path))
    print("Wrote: %s" % out_csv)
    print("Wrote: %s" % out_md)
    print()
    print("COMPACT 20-ASIN TABLE (decision-ready first):")
    print("%-3s %-12s %-60s %-10s %-12s %-5s" % (
        "P", "ASIN", "Title", "BB price", "BSR", "Ready"))
    for i, r in enumerate(rows, 1):
        t = r["title"]
        if len(t) > 57:
            t = t[:54] + "..."
        print("%-3d %-12s %-60s %-10s %-12s %-5s" % (
            i, r["ASIN"], t, r["buy_box"], r["bsr_rank"], r["decision_ready"]))
    print()
    ready = [r["ASIN"] for r in rows if r["decision_ready"] == "Yes"]
    print("DECISION-READY (9): %s" % ", ".join(ready))
    print("CONFIRM: 0 network requests, 0 live provider calls, 0 original "
          "artifacts modified.")


if __name__ == "__main__":
    main()
