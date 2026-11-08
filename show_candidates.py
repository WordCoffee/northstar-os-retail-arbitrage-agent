import json
from pathlib import Path
cands = json.loads(Path("out_lions_mane/candidates_visual.json").read_text(encoding="utf-8"))
for c in cands:
    print(f"{c['asin']} | rank {c['rank']} | {c.get('size_oz')}oz | ${c.get('price')} | {str(c.get('brand'))[:22]:22s} | {str(c.get('title'))[:75]}")
print(len(cands), "candidates")
