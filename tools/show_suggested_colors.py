import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
d = json.load(open(ROOT / "renders" / "package_readiness_live.json", encoding="utf-8"))
sc = (d["evidence"]["prepress"] or {}).get("suggested_colors") or []
print("suggested colours:", len(sc))
for c in sc[:6]:
    print("  {0} -> prints as {1} (shift {2})".format(
        c["hex"], c["prints_as_hex"], c["dE76"]))
