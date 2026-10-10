import json, re
from collections import Counter
from pathlib import Path

OUT = Path("out_sb")
disc = json.loads((OUT / "discovery.json").read_text(encoding="utf-8"))
rej_title = json.loads((OUT / "rejected_title.json").read_text(encoding="utf-8"))
rej_text = json.loads((OUT / "rejected_text.json").read_text(encoding="utf-8"))
details = json.loads((OUT / "details.json").read_text(encoding="utf-8"))

print("discovery records:", len(disc["records"]))
print("details (enriched):", len(details))
print("rejected_title:", len(rej_title), "| rejected_text:", len(rej_text))

# title rejects whose ONLY reason is a size below 4 that is >= 1
size_re = re.compile(r"size ([\d.]+)oz outside")
only_size_1to4 = []
size_reasons = Counter()
for r in rej_title:
    reasons = [x for x in str(r.get("reasons", "")).split("; ") if x]
    size_matches = [size_re.search(x) for x in reasons]
    sizes = [float(m.group(1)) for m in size_matches if m]
    if sizes:
        size_reasons[sizes[0]] += 1
    if len(reasons) == 1 and sizes and 1.0 <= sizes[0] < 4.0:
        only_size_1to4.append((r["asin"], sizes[0], (r.get("title") or "")[:70]))

print("\n=== title rejects where ONLY reason is size, and 1.0 <= size < 4.0 ===")
print("count:", len(only_size_1to4))
for a, s, t in only_size_1to4:
    print(f"  {a} | {s} oz | {t.encode('ascii','replace').decode()}")

print("\n=== all size values seen in title rejects ===")
for s, c in sorted(size_reasons.items()):
    print(f"  {s} oz: {c}")

# text rejects with size-only hard fail in 1-4 range
print("\n=== text rejects mentioning size outside 4-32 ===")
for r in rej_text:
    reasons = str(r.get("reasons", ""))
    m = size_re.search(reasons)
    if m and 1.0 <= float(m.group(1)) < 4.0:
        print(f"  {r['asin']} | {m.group(1)} oz | {(r.get('title') or '')[:60].encode('ascii','replace').decode()} | {reasons[:90]}")

# enriched details sizes < 4
print("\n=== enriched records with label net weight < 4oz (from vision) ===")
vv = json.loads((OUT / "vision_verdicts.json").read_text(encoding="utf-8"))
for a, v in vv.items():
    nw = v.get("net_weight_oz")
    if nw and nw < 4.0:
        print(f"  {a} | vision nw {nw} | form={v.get('form')}")
