"""Node 3: assert the summary before anyone reports it."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
summary = json.loads((ROOT / "data" / "summary.json").read_text(encoding="utf-8"))

assert summary["total_orders"] == 24, summary
assert summary["days"] == 3, summary
print("verified total %d across %d days" % (summary["total_orders"],
                                            summary["days"]))
