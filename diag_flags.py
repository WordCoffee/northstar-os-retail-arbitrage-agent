import json, re
from pathlib import Path

OUT = Path("out_sb")
vp = json.loads((OUT / "visual_pass.json").read_text(encoding="utf-8"))
details = json.loads((OUT / "details.json").read_text(encoding="utf-8"))
verdicts = json.loads((OUT / "vision_verdicts.json").read_text(encoding="utf-8"))

def ctx(text, word):
    text = str(text)
    for m in re.finditer(word, text, re.I):
        s = max(0, m.start() - 60); e = min(len(text), m.end() + 60)
        yield text[s:e].replace("\n", " ")

for r in vp:
    asin = r["asin"]
    tr = r.get("text_review") or []
    flags = [x for x in tr if ("extract" in x or "mycelium" in x or "other mushroom" in x)]
    if not flags:
        continue
    p = details.get(asin) or {}
    v = verdicts.get(asin) or {}
    print("=" * 20, asin, "| vision extract/mycelium:", v.get("mentions_extract_or_mycelium"))
    bullets = str(p.get("bullet_points") or "")
    desc = str(p.get("description") or "")
    imp = str(p.get("important_information") or "")
    for w in ["extract", "myceli"]:
        for c in list(ctx(bullets, w))[:2]:
            print(f"   bullets[{w}]:", c.encode("ascii", "replace").decode()[:140])
        for c in list(ctx(desc, w))[:1]:
            print(f"   desc[{w}]:", c.encode("ascii", "replace").decode()[:140])
