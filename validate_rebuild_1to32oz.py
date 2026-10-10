#!/usr/bin/env python3
"""Validation for the 1.0-32.0 oz rebuild. Exits non-zero on failure."""
import csv, hashlib, json, re, sys
from pathlib import Path

RB = Path("out_sb/rebuild_1to32oz")
OUT = Path("out_sb")
fails = []

def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        fails.append(name)

def rows(name):
    return list(csv.DictReader(open(RB / name, newline="", encoding="utf-8")))

market = rows("lions_mane_market_1to32oz.csv")
clean = rows("lions_mane_clean_comparables_1to32oz.csv")
review = rows("lions_mane_review_required_1to32oz.csv")
excluded = rows("lions_mane_excluded_1to32oz.csv")
ranked = rows("lions_mane_ranked_by_category_bsr.csv")
counts = json.loads((RB / "rebuild_counts.json").read_text(encoding="utf-8"))

def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

# 1. every included record has normalized net weight within 1-32 oz (or null only in review)
bad = [r["asin"] for r in market if not (f(r["total_sellable_net_weight_oz"]) is not None and 1.0 <= f(r["total_sellable_net_weight_oz"]) <= 32.0 and r["weight_ambiguity_flag"] == "False")]
check("1a market weights in [1,32] and non-ambiguous", not bad, str(bad[:5]))
bad = [r["asin"] for r in review if r["total_sellable_net_weight_oz"] not in ("", None) and not (1.0 <= f(r["total_sellable_net_weight_oz"]) <= 32.0)]
check("1b review weights null or in [1,32]", not bad, str(bad[:5]))

# 2. category rank resets per category
bycat = {}
for r in ranked:
    bycat.setdefault(r["bsr_category"], []).append(int(r["category_rank"]))
ok = all(sorted(v) == list(range(1, len(v) + 1)) for v in bycat.values())
check("2 category ranks reset per category (1..n)", ok, str({k: v[:3] for k, v in bycat.items()}))

# 3. no unknown BSR in ranking
bad = [r["asin"] for r in ranked if not r["bsr_primary"]]
check("3 no unknown BSR rows in ranking", not bad)

# 4. $/oz only when price and size known
bad = [r["asin"] for r in market + review + excluded if r["price_per_oz"] not in ("", None) and (f(r["total_price"]) is None or f(r["total_sellable_net_weight_oz"]) is None)]
check("4 $/oz only with price and size", not bad, str(bad[:5]))

# 5. price_per_oz == total_price / total_size
bad = []
for r in market + review + excluded:
    ppo, p, s = f(r["price_per_oz"]), f(r["total_price"]), f(r["total_sellable_net_weight_oz"])
    if ppo is not None and p and s and abs(ppo - p / s) > 0.01:
        bad.append(r["asin"])
check("5 price_per_oz == total_price / total_sellable_oz", not bad, str(bad[:5]))

# 6. multipack math uses total sellable content
bad = []
for r in market + review:
    if r["is_multipack"] == "True" and f(r["unit_count"]) and f(r["normalized_unit_weight_oz"]) and f(r["total_sellable_net_weight_oz"]):
        if abs(f(r["unit_count"]) * f(r["normalized_unit_weight_oz"]) - f(r["total_sellable_net_weight_oz"])) > 0.01:
            bad.append(r["asin"])
check("6 multipack total == unit_count × per-unit", not bad, str(bad[:5]))

# 7. BSR estimates labelled
bad = [r["asin"] for r in market if r["bsr_est_monthly_sales"] not in ("", None) and "ESTIMATE" not in (r["bsr_est_caveat"] or "")]
check("7 all BSR estimates carry ESTIMATE caveat", not bad, str(bad[:5]))

# 8. new 1 oz boundary in effect: rows <4 oz exist in market; nothing <1 oz included
has_small = any(f(r["total_sellable_net_weight_oz"]) and f(r["total_sellable_net_weight_oz"]) < 4.0 for r in market)
check("8a market contains rows <4 oz (1 oz floor in effect)", has_small)
bad = [r["asin"] for r in market if f(r["total_sellable_net_weight_oz"]) is not None and f(r["total_sellable_net_weight_oz"]) < 1.0]
check("8b no included row below 1.0 oz", not bad)

# 9. raw files unchanged (sha256 vs manifest)
manifest = json.loads((RB / "raw_hash_manifest.json").read_text(encoding="utf-8"))
bad = []
for name, h in manifest.items():
    cur = hashlib.sha256((OUT / name).read_bytes()).hexdigest()
    if cur != h:
        bad.append(name)
check("9 raw evidence files unchanged", not bad, str(bad))

# 10. partition integrity
all_asins = {r["asin"] for r in market} | {r["asin"] for r in review} | {r["asin"] for r in excluded}
check("10a union of statuses covers all cached ASINs", len(all_asins) == counts["total_asins"], f"{len(all_asins)} vs {counts['total_asins']}")
check("10b clean subset of market", {r["asin"] for r in clean} <= {r["asin"] for r in market})
check("10c clean count matches manifest", len(clean) == counts["clean_comparable"])
check("10d market count matches manifest", len(market) == counts["market_lens"])

# formula spot-check (documented model)
import importlib
L = importlib.import_module("lions_mane_sb")
for bsr, exp in [(1000, 2512), (10000, 501), (100000, 100)]:
    est, _ = L.bsr_monthly_sales(bsr, "Health & Household")
    check(f"formula H&H bsr={bsr} ~ {exp}", abs(est - exp) / exp < 0.05, f"got {est}")

print()
if fails:
    print("VALIDATION FAILED:", fails); sys.exit(1)
print("ALL VALIDATION CHECKS PASSED")
