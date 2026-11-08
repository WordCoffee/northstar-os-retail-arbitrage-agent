import json
from pathlib import Path
import lions_mane_sb as L

OUT = Path("out_sb")
d = json.loads((OUT / "audit_results.json").read_text(encoding="utf-8"))
details = json.loads((OUT / "details.json").read_text(encoding="utf-8"))
for x in d["rejected_audit"]:
    if x.get("result") == "CHECK":
        asin = x["asin"]
        p = dict(details.get(asin) or {}); p["asin"] = asin
        why, rev, size = L.text_gate(p)
        print("=" * 12, asin)
        print("  recorded:", str(x.get("recorded"))[:160])
        print("  text re-run: why=", why, "| review=", rev)
        imp = L._imp_sections(p)
        print("  ingredients_section:", repr(imp.get("ingredients"))[:120])
        v = json.loads((OUT / "vision_verdicts.json").read_text(encoding="utf-8")).get(asin, {})
        print("  vision: form=", v.get("form"), "extract/myceli=", v.get("mentions_extract_or_mycelium"),
              "other_ing=", v.get("other_ingredients_on_label"), "nw=", v.get("net_weight_on_label"))
