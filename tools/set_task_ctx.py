"""Set the per-request context for the narrow Ty task (idempotent)."""
import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"
data = json.loads(REG.read_text(encoding="utf-8-sig"))
for task in data["tasks"]:
    if task.get("id") == "ty-budget-stop":
        task["num_ctx"] = 8192
REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print("num_ctx set for ty-budget-stop")
