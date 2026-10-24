import csv, os, collections, urllib.parse as up
BASE = os.path.join("docs", "mogra-organics-research-2026-10-02")
rows = list(csv.DictReader(open(os.path.join(BASE, "supplier_master.csv"), newline="", encoding="utf-8")))

# Which existing suppliers are on a marketplace-style catalogue vs a direct B2B site?
MKT = ("indiamart", "tradeindia", "alibaba", "made-in-china", "globalsources", "tradewheel",
       "exportersindia", "ec21", "sourcify", "panjiva", "kompass", "europages")
print("=== existing suppliers sitting on a marketplace ===")
n = 0
for r in rows:
    h = up.urlparse(r["website"] or "").netloc.lower()
    if any(m in h for m in MKT):
        n += 1
        print("   %-34s %s" % (r["legal_name"][:34], h))
print("   count =", n)
print()
print("=== price-visibility evidence already captured ===")
for f in sorted(os.listdir(BASE)):
    if not f.endswith(".csv"):
        continue
    try:
        txt = open(os.path.join(BASE, f), newline="", encoding="utf-8").read(400000).lower()
    except Exception:
        continue
    hits = [k for k in ("published price", "price range", "request", "no price", "quote required",
                        "price_visible", "pricing") if k in txt]
    if hits and ("price" in txt):
        print("   %-38s %s" % (f, ", ".join(hits)))
print()
print("=== how many existing suppliers have a discoverable price field ===")
pm = os.path.join(BASE, "pricing_comparison.csv")
if os.path.exists(pm):
    pr = list(csv.DictReader(open(pm, newline="", encoding="utf-8")))
    print("   pricing_comparison.csv rows =", len(pr))
    print("   cols:", list(pr[0].keys())[:10])
    named = set()
    for r in pr:
        for k in r:
            if "supplier" in k.lower() or "provider" in k.lower():
                named.add((r[k] or "").strip())
    named.discard("")
    print("   distinct suppliers priced:", len(named))
    print("   sample:", sorted(named)[:8])