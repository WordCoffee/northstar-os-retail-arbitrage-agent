"""Offline inspection of saved raw payload (NO network)."""

import json

with open("data/probe_real_time_raw.json", "r", encoding="utf-8") as f:
    root = json.load(f)

data = root.get("data", root) if isinstance(root, dict) else {}
print("=== data keys (%d) ===" % len(data))
for k in sorted(data.keys()):
    v = data[k]
    t = type(v).__name__
    extra = " len=%d" % len(v) if isinstance(v, (list, dict)) else ""
    if isinstance(v, (list, dict)):
        extra += " -> %s" % (sorted(v[0].keys())[:25] if isinstance(v, list) and v and isinstance(v[0], dict) else (sorted(v.keys())[:25] if isinstance(v, dict) else ""))
    print("  %-32s %s%s" % (k, t, extra))

# Look for offer-like lists specifically
print("\n=== candidate offer lists ===")
for k, v in data.items():
    if isinstance(v, list) and v and isinstance(v[0], dict):
        print("  LIST %s -> keys: %s" % (k, sorted(v[0].keys())))

print("\n=== BSR / rank candidates ===")
for cand in ("sales_rank", "salesRank", "rank", "bsr", "product_information", "product_details"):
    if cand in data:
        val = data[cand]
        if isinstance(val, (dict, list)):
            print("  %s: %s -> %s" % (cand, type(val).__name__, (sorted(val.keys()) if isinstance(val, dict) else "list len %d" % len(val))))
        else:
            print("  %s = %s" % (cand, str(val)[:160]))

print("\n=== price candidates ===")
for cand in ("product_price", "product_original_price", "price", "current_price", "buybox_price", "deal_price"):
    if cand in data:
        print("  %s = %s" % (cand, str(data[cand])[:160]))
