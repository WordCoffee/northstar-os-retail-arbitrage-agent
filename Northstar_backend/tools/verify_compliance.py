#!/usr/bin/env python
"""Verify Sourcescout quantity-match compliance from manifest JSON (no API keys)."""
import json
from pathlib import Path
from collections import Counter

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "catalog"


def main():
    print("=== SOURCESCOUT QUANTITY COMPLIANCE VERIFICATION ===\n")

    # 1. Main manifest + summary
    mp = DATA_ROOT / "sourcescout_manifest.json"
    if not mp.exists():
        print(f"ERROR: {mp} not found")
        return 1
    manifest = json.loads(mp.read_text())
    summary = manifest.get("quantity_match_summary", {})
    items = manifest.get("items", [])
    print(f"Main manifest: {len(items)} items")
    print(f"  Summary: PASS={summary.get('pass')} FAIL={summary.get('fail')} "
          f"REVIEW={summary.get('review')} (total={summary.get('total')})")

    # 2. Status distribution from embedded quantity_match
    statuses = Counter()
    for item in items:
        statuses[item.get("quantity_match", {}).get("status", "MISSING")] += 1
    print("  Embedded status distribution:", dict(statuses))

    # 3. Compliant manifest
    cp = DATA_ROOT / "sourcescout_compliant_manifest.json"
    if cp.exists():
        comp = json.loads(cp.read_text())
        print(f"\nCompliant-only manifest: {comp.get('count', len(comp.get('items', [])))} items")

    # 4. Mismatch + review reports
    for name in ("quantity_mismatch_report.json", "quantity_review_report.json"):
        rp = DATA_ROOT / name
        if rp.exists():
            report = json.loads(rp.read_text())
            key = "failures" if "mismatch" in name else "reviews"
            print(f"{name}: {len(report.get(key, []))} items")

    # 5. PASS examples
    print("\n=== PASS EXAMPLES (first 3) ===")
    shown = 0
    for item in items:
        qm = item.get("quantity_match", {})
        if qm.get("status") != "PASS":
            continue
        aq = qm.get("amazon_quantity", {})
        cq = qm.get("costco_quantity", {})
        title = (item.get("title") or item.get("product_title") or "")[:60]
        print(f"  {item.get('asin')}: {title}")
        print(f"    Amazon: {aq.get('count')} {aq.get('unit')} of {aq.get('unit_type')}")
        if cq:
            print(f"    Costco: {cq.get('count')} {cq.get('unit')} of {cq.get('unit_type')}")
        print(f"    Match: {qm.get('match_reason', qm.get('reason'))}")
        shown += 1
        if shown >= 3:
            break

    # 6. FAIL examples
    print("\n=== FAIL EXAMPLES (first 3) ===")
    shown = 0
    for item in items:
        qm = item.get("quantity_match", {})
        if qm.get("status") != "FAIL":
            continue
        aq = qm.get("amazon_quantity", {})
        cq = qm.get("costco_quantity", {})
        title = (item.get("title") or item.get("product_title") or "")[:60]
        print(f"  {item.get('asin')}: {title}")
        print(f"    Amazon: {aq.get('count')} {aq.get('unit')} of {aq.get('unit_type')}")
        if cq:
            print(f"    Costco: {cq.get('count')} {cq.get('unit')} of {cq.get('unit_type')}")
        print(f"    Reason: {qm.get('mismatch_reason', qm.get('reason'))}")
        shown += 1
        if shown >= 3:
            break

    # 7. REVIEW examples
    print("\n=== REVIEW EXAMPLES (first 3) ===")
    shown = 0
    for item in items:
        qm = item.get("quantity_match", {})
        if qm.get("status") != "REVIEW":
            continue
        title = (item.get("title") or item.get("product_title") or "")[:60]
        print(f"  {item.get('asin')}: {title}")
        print(f"    Reason: {qm.get('mismatch_reason', qm.get('reason'))}")
        shown += 1
        if shown >= 3:
            break

    # 8. Credit savings
    print("\n=== CREDIT SAVINGS PROJECTION ===")
    total = len(items)
    pass_count = summary.get("pass", 0)
    skipped = total - pass_count
    per_item_credits = 5
    saved = skipped * per_item_credits
    print(f"Enrich only PASS ({pass_count}) instead of all ({total})")
    print(f"Skipped: {skipped} items -> saves {saved} credits/run")
    print(f"At 5 credits/item = {saved} credits saved/run")
    print(f"Monthly (30 runs): {saved * 30} credits saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
