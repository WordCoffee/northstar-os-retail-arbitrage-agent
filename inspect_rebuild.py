import csv
from pathlib import Path

RB = Path("out_sb/rebuild_1to32oz")

def rows(name): return list(csv.DictReader(open(RB / name, newline="", encoding="utf-8")))

m = rows("lions_mane_market_1to32oz.csv")
c = rows("lions_mane_clean_comparables_1to32oz.csv")
rv = rows("lions_mane_review_required_1to32oz.csv")
ex = rows("lions_mane_excluded_1to32oz.csv")
print(f"market={len(m)} clean={len(c)} review={len(rv)} excluded={len(ex)}")

print("\n=== CLEAN COMPARABLES ===")
for r in c:
    print(f"{r['asin']} | {r['total_sellable_net_weight_oz']}oz | ${r['total_price']} | {r['brand'][:14]:14s} | bsr={r['bsr_primary']} | {r['title'][:52].encode('ascii','replace').decode()}")

print("\n=== MARKET: qualified_flagged sample (first 25) ===")
for r in [x for x in m if x["market_lens_status"] == "qualified_flagged"][:25]:
    flags = ",".join(k for k, v in [("extract", r["extract_flag"] == "True"), ("myc", r["mycelium_flag"] == "True"), ("blend", r["blend_flag"] == "True")] if v)
    print(f"{r['asin']} | {r['total_sellable_net_weight_oz']}oz | ${r['total_price']} | {flags:18s} | {r['title'][:58].encode('ascii','replace').decode()}")

print("\n=== REVIEW REQUIRED ===")
for r in rv:
    print(f"{r['asin']} | {r['total_sellable_net_weight_oz']}oz | status={r['market_lens_status']} | {str(r['status_reasons'])[:110]}")
    print(f"      {r['title'][:80].encode('ascii','replace').decode()}")

print("\n=== RECLASSIFIED BY SIZE RULE ===")
rec = [r for r in m + rv + ex if r["reclassified_by_size_rule"] == "True"]
for r in rec:
    print(f"{r['asin']} | old={r['old_verdict']} | new={r['market_lens_status']}/{r['clean_comparable_status']} | {r['total_sellable_net_weight_oz']}oz | {str(r['old_reasons'])[:70]}")

print("\n=== check specific edge cases ===")
allrows = {r["asin"]: r for r in m + rv + ex}
for a in ["B0H1YT14X5", "B0FY71CYK8", "B01DKZZFCE", "B07TJ63MH3", "B0D9592D7Y", "B01MUG4DVQ", "B07345XGQQ", "B0CKTZ9YS1", "B077VXRHK6", "B0F84DY8X7", "B0GKQ6SRK4"]:
    r = allrows.get(a)
    if not r:
        print(a, "NOT FOUND"); continue
    print(f"{a} | market={r['market_lens_status']} clean={r['clean_comparable_status']} | w={r['total_sellable_net_weight_oz']} unit={r['normalized_unit_weight_oz']} n={r['unit_count']} mp={r['is_multipack']} | {str(r['status_reasons'])[:95]}")
