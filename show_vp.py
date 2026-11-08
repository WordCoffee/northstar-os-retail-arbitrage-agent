import json
from collections import Counter
from pathlib import Path

vp = json.loads(Path("out_sb/visual_pass.json").read_text(encoding="utf-8"))
print("visual_pass:", len(vp))
c = Counter()
for r in vp:
    tr = r.get("text_review") or []
    for x in tr:
        c[x] += 1
    if tr:
        t = (r.get("title") or "").encode("ascii", "replace").decode()
        print(r["asin"], "|", t[:58], "||", "; ".join(tr)[:130])
print()
print("flag histogram:")
for k, v in c.most_common():
    print(f"  {v:2d}  {k}")
