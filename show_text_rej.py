import json
from collections import Counter
from pathlib import Path

rej = json.loads(Path("out_sb/rejected_text.json").read_text(encoding="utf-8"))
hist = Counter()
for r in rej:
    for part in str(r.get("reasons", "")).split("; "):
        hist[part.split("(")[0][:70]] += 1
for k, v in hist.most_common(30):
    print(f"{v:3d}  {k}")
print()
for r in rej[-15:]:
    t = (r.get("title") or "").encode("ascii", "replace").decode()
    print(r["asin"], "|", t[:75])
    print("    ", str(r.get("reasons"))[:150])
