"""Node 2: summarise what node 1 collected."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
source = json.loads((DATA / "collected.json").read_text(encoding="utf-8"))
summary = {"days": len(source["orders"]), "total_orders": sum(source["orders"]),
           "currency": source["currency"]}
(DATA / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
print("summary total %d" % summary["total_orders"])
