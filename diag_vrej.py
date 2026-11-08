import json
from pathlib import Path

OUT = Path("out_sb")
rej = json.loads((OUT / "rejected_visual.json").read_text(encoding="utf-8"))
verdicts = json.loads((OUT / "vision_verdicts.json").read_text(encoding="utf-8"))
print("rejected_visual:", len(rej))
for r in rej:
    asin = r["asin"]
    v = verdicts.get(asin, {})
    t = (r.get("title") or "").encode("ascii", "replace").decode()
    print("=" * 10, asin, "|", t[:58])
    print("   reasons:", str(r.get("reasons"))[:150])
    print("   other_ing:", v.get("other_ingredients_on_label"),
          "| extract/myceli:", v.get("mentions_extract_or_mycelium"),
          "| nw_label:", v.get("net_weight_on_label"), "| nw_oz:", v.get("net_weight_oz"))
    print("   evidence:", str(v.get("evidence"))[:170].encode("ascii", "replace").decode())
