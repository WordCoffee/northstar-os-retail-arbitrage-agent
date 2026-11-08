import json, re
from pathlib import Path

OUT = Path("out_sb")
details = json.loads((OUT / "details.json").read_text(encoding="utf-8"))

# check the KOS "other mushroom mentioned in bullets" context
for asin in ["B0CZPGXZ2T", "B0DN5KFMZM", "B0DCC32S7J", "B0CVNDT5ZR"]:
    p = details.get(asin, {})
    b = str(p.get("bullet_points") or "")
    print("=" * 12, asin, (p.get("title") or "")[:60].encode("ascii", "replace").decode())
    for w in ["reishi", "cordyceps", "chaga", "maitake", "shiitake", "tremella", "turkey", "oyster", "agaricus", "other mushroom", "mushrooms"]:
        for m in re.finditer(w, b, re.I):
            s = max(0, m.start() - 80); e = min(len(b), m.end() + 80)
            print(f"   [{w}]:", b[s:e].replace("\n", " ").encode("ascii", "replace").decode()[:180])
    print()
