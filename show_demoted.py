import json
from pathlib import Path

vp = json.loads(Path("out_sb/visual_pass.json").read_text(encoding="utf-8"))
demoted = [r for r in vp if r.get("text_review")]
print("visual_pass:", len(vp), "| demoted by text_review:", len(demoted))
for r in demoted:
    print(r["asin"], "|", (r.get("title") or "")[:55].encode("ascii", "replace").decode())
    print("    flags:", "; ".join(r.get("text_review"))[:150])
