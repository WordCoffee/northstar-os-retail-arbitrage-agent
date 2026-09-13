#!/usr/bin/env python
"""Offline margin shortlist over the 245-ASIN PASS set (zero network).

Ranks compliant-PASS ASINs by house unit economics and emits the buy-depth
shortlist that the finite Easyparser roster balance (~99 credits) should be
spent on first.

Inputs (all local, zero network, zero credentials):
  - sourcescout_compliant_manifest.json (PASS scope + titles)
  - a Bright Data compliant run dir (fresh buy_box/title/category/weight)
  - data/costco-items.csv via costco_client.get_costco_price ONLY
    (never product_analysis.get_costco_price — that tries the live
    resolve_costco_cost API first).

Economics (house definition, pricing.compute_profit):
  profit = buy_box - COGS - 15% referral - FBA fee - 3.5% fuel - $0.35 inbound
  FBA fee = enriched fba_fee, else estimate_fba_fee(weight_lbs); absent both
  means needs-fee (never assumed).

Trust gates (nothing invented):
  - buy_box must be present and within [--min-price, --max-price]
    (default 1.00–500.00; kills the $0.12 parse artifact and the $925
    outlier class without touching the source files).
  - COGS trusted only on match_quality exact|high_confidence (the repo's
    own "estimated" basis, costco_client.py:549). candidate|mismatch|
    unknown -> needs-cost bucket with the reason recorded.
  - Only profit >= --min-profit (default 9.00) ranks; output capped at
    --top (default 90, sized to the Easyparser balance with headroom).

Exit codes: 0 success (even when the ranked list is short — that is a
finding, not an error); 2 usage; 4 manifest/run-dir rejected.
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import costco_client
from pricing import compute_profit, estimate_fba_fee

BACKEND_DIR = Path(__file__).resolve().parent
COMPLIANT_MANIFEST = BACKEND_DIR / "data" / "catalog" / "sourcescout_compliant_manifest.json"
DEFAULT_RUN_DIR = (BACKEND_DIR / "data" / "enrich" / "brightdata-compliant" /
                   "brightdata-compliant-20260913T050631Z-30e2")
SHORTLIST_BASE = BACKEND_DIR / "data" / "enrich" / "margin-shortlist"

TRUSTED_MATCH = ("exact", "high_confidence")


def _load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return None, "unreadable JSON %s: %s" % (path, exc)
    return data, None


def _pass_items(manifest: dict):
    import re
    pat = re.compile(r"^[A-Za-z0-9]{10}$")
    out, seen = [], set()
    for item in manifest.get("items") or []:
        if not isinstance(item, dict):
            continue
        qm = item.get("quantity_match") or {}
        if not isinstance(qm, dict) or qm.get("status") != "PASS":
            continue
        asin = str(item.get("asin") or "").strip().upper()
        if not pat.fullmatch(asin) or asin in seen:
            continue
        seen.add(asin)
        out.append(item)
    return out


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def build_shortlist(manifest_path, run_dir, min_profit=9.0, top=90,
                    min_price=1.0, max_price=500.0):
    manifest, err = _load_json(Path(manifest_path))
    if err or not isinstance(manifest, dict):
        return None, err or "manifest must be a JSON object"
    run_path = Path(run_dir)
    if not run_path.is_dir():
        return None, "run dir not found: %s" % run_path

    ranked, below_cut, ceilings = [], [], []
    needs_fee, needs_cost, price_flagged = [], [], []
    for item in _pass_items(manifest):
        asin = str(item.get("asin")).strip().upper()
        norm_path = run_path / "normalized" / ("%s.json" % asin)
        enriched, err = _load_json(norm_path)
        if err or not isinstance(enriched, dict):
            price_flagged.append({"asin": asin, "reason": "no enriched file"})
            continue
        buy_box = enriched.get("buy_box_price")
        if not _is_num(buy_box) or not (min_price <= buy_box <= max_price):
            price_flagged.append({"asin": asin, "reason": "buy_box=%r" % (buy_box,)})
            continue
        fee = enriched.get("fba_fee")
        fee_basis = "enriched"
        if not _is_num(fee):
            weight = enriched.get("weight_lbs")
            if _is_num(weight) and weight > 0:
                fee = estimate_fba_fee(weight)
                fee_basis = "weight-estimated"
            else:
                needs_fee.append({"asin": asin, "buy_box": buy_box})
                continue
        # COGS ceiling: max COGS that still clears min_profit. Actionable even
        # when the CSV has no match — tells the operator which Costco price to
        # beat, and ranks COGS-research priority by headroom.
        referral = 0.15 * buy_box
        fuel = 0.035 * fee
        ceiling = buy_box - referral - fee - fuel - 0.35 - min_profit
        ceilings.append({"asin": asin, "buy_box": round(buy_box, 2),
                         "fba_fee": round(fee, 2), "fba_fee_basis": fee_basis,
                         "cogs_ceiling": round(ceiling, 2)})
        title = (item.get("title") or
                 ((item.get("quantity_match") or {}).get("amazon_title")) or "")
        cost = costco_client.get_costco_price(title)
        quality = (cost or {}).get("match_quality")
        cogs = (cost or {}).get("costco_cost")
        if quality not in TRUSTED_MATCH or not _is_num(cogs) or cogs <= 0:
            needs_cost.append({"asin": asin, "buy_box": buy_box,
                               "match_quality": quality,
                               "match_reason": (cost or {}).get("match_reason")})
            continue
        profit, roi = compute_profit(buy_box, cogs, fba_fee=fee)
        row = {
            "asin": asin, "title": (enriched.get("title") or title)[:100],
            "buy_box": round(buy_box, 2), "cogs": round(cogs, 2),
            "fba_fee": round(fee, 2), "fba_fee_basis": fee_basis,
            "referral_rate": 0.15, "match_quality": quality,
            "profit": round(profit, 2), "roi_pct": round(roi, 1),
        }
        if profit >= min_profit:
            ranked.append(row)
        else:
            below_cut.append(row)
    ranked.sort(key=lambda r: r["profit"], reverse=True)
    below_cut.sort(key=lambda r: r["profit"], reverse=True)
    ceilings.sort(key=lambda r: r["cogs_ceiling"], reverse=True)
    return {
        "ranked": ranked[:top],
        "ranked_total": len(ranked),
        "below_cut": below_cut,
        "ceilings": ceilings,
        "needs_fee": needs_fee,
        "needs_cost": needs_cost,
        "price_flagged": price_flagged,
    }, None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline margin shortlist (zero network).")
    parser.add_argument("--manifest", default=str(COMPLIANT_MANIFEST))
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    parser.add_argument("--min-profit", type=float, default=9.0)
    parser.add_argument("--top", type=int, default=90)
    parser.add_argument("--min-price", type=float, default=1.0)
    parser.add_argument("--max-price", type=float, default=500.0)
    args = parser.parse_args(argv)

    result, err = build_shortlist(args.manifest, args.run_dir, args.min_profit,
                                  args.top, args.min_price, args.max_price)
    if err:
        print("shortlist: REJECTED - %s" % err)
        return 4
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = SHORTLIST_BASE / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "definition": ("profit = buy_box - cogs - 15% referral - fba_fee - "
                       "3.5% fuel - $0.35 inbound (pricing.compute_profit); "
                       "cogs trusted only on exact|high_confidence CSV match"),
        "min_profit": args.min_profit, "top": args.top,
        "counts": {k: (len(v) if isinstance(v, list) else v)
                   for k, v in result.items() if k != "ranked"},
        **result,
    }
    with open(out_dir / "shortlist.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    with open(out_dir / "shortlist.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "asin", "profit", "roi_pct", "buy_box", "cogs",
                    "fba_fee", "fba_fee_basis", "match_quality", "title"])
        for i, r in enumerate(result["ranked"], 1):
            w.writerow([i, r["asin"], r["profit"], r["roi_pct"], r["buy_box"],
                        r["cogs"], r["fba_fee"], r["fba_fee_basis"],
                        r["match_quality"], r["title"]])
    with open(out_dir / "ceilings.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "asin", "cogs_ceiling", "buy_box", "fba_fee",
                    "fba_fee_basis"])
        for i, r in enumerate(result["ceilings"], 1):
            w.writerow([i, r["asin"], r["cogs_ceiling"], r["buy_box"],
                        r["fba_fee"], r["fba_fee_basis"]])
    print("shortlist: %d ranked @ profit>=%.2f (top %d) | below-cut %d | "
          "needs-fee %d | needs-cost %d | price-flagged %d" % (
              result["ranked_total"], args.min_profit, len(result["ranked"]),
              len(result["below_cut"]),
              len(result["needs_fee"]), len(result["needs_cost"]),
              len(result["price_flagged"])))
    print("ceilings: %d ASINs with max-COGS-to-clear-$%.2f (see ceilings.csv)"
          % (len(result["ceilings"]), args.min_profit))
    print("artifacts: %s" % out_dir)
    for i, r in enumerate(result["ranked"][:10], 1):
        print("  %2d. %s profit=$%.2f roi=%.1f%% bb=$%.2f cogs=$%.2f fee=$%.2f(%s)" % (
            i, r["asin"], r["profit"], r["roi_pct"], r["buy_box"], r["cogs"],
            r["fba_fee"], r["fba_fee_basis"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
