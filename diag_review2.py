import json, re
from pathlib import Path

OUT = Path("out_sb")
vp = json.loads((OUT / "visual_pass.json").read_text(encoding="utf-8"))
vr = json.loads((OUT / "visual_review.json").read_text(encoding="utf-8"))
details = json.loads((OUT / "details.json").read_text(encoding="utf-8"))

print("=== PASS rows ===")
for r in vp:
    print(r["asin"], "|", (r.get("title") or "")[:62].encode("ascii", "replace").decode())

print("\n=== REVIEW rows with contexts ===")
def ctx(text, word, n=70):
    out = []
    for m in re.finditer(word, str(text), re.I):
        s = max(0, m.start() - n); e = min(len(str(text)), m.end() + n)
        out.append(str(text)[s:e].replace("\n", " "))
    return out[:2]

for r in vr:
    asin = r["asin"]
    solid = details.get(asin, {})
    print("=" * 15, asin, "|", (r.get("title") or "")[:55].encode("ascii", "replace").decode())
    print("   reasons:", str(r.get("visual_reasons"))[:180])
    print("   text_review:", r.get("text_review"))
    for w in ["extract", "myceli", "reishi", "cordyceps", "chaga", "shiitake"]:
        for c in ctx(solid.get("bullet_points"), w):
            print(f"     bullets[{w}]:", c.encode("ascii", "replace").decode()[:150])
