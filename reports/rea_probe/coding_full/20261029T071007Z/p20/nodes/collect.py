"""Node 1: collect the week's order counts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = {"orders": [12, 7, 5], "currency": "USD"}

out = ROOT / "data" / "collected.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(DATA), encoding="utf-8")
print("collected %d days" % len(DATA["orders"]))
