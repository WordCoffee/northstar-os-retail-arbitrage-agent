import json
from pathlib import Path

OUT = Path("out_sb")
vp = json.loads((OUT / "visual_pass.json").read_text(encoding="utf-8"))
vr = json.loads((OUT / "visual_review.json").read_text(encoding="utf-8"))
rj = json.loads((OUT / "rejected_visual.json").read_text(encoding="utf-8"))
print("\n=== VISUAL PASS:", len(vp), "===")
for r in vp:
    print(r["asin"], "|", (r.get("title") or "")[:58].encode("ascii", "replace").decode())
    print("   text_review:", r.get("text_review"), "| visual_reasons:", r.get("visual_reasons"))
print("\n=== VISUAL REVIEW:", len(vr), "===")
for r in vr:
    print(r["asin"], "|", (r.get("title") or "")[:58].encode("ascii", "replace").decode())
    print("   visual_reasons:", str(r.get("visual_reasons"))[:160])
print("\n=== VISUAL REJECT:", len(rj), "===")
for r in rj:
    print(r["asin"], "|", str(r.get("reasons"))[:120])
