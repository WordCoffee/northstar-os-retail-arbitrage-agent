"""Apply the authorized step-budget change to exactly two tasks (versioned)."""
from __future__ import annotations

import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"
IDS = {
    "ty-artifact-jpeg": "ty-artifact-jpeg contract v1 (max_steps=8, two failed dispatches)",
    "ty-diff-select-headers": "ty-diff-select-headers contract v1 (max_steps=8, two failed dispatches)",
}

data = json.loads(REG.read_text(encoding="utf-8-sig"))
for task in data["tasks"]:
    tid = task.get("id")
    if tid in IDS:
        if task.get("contract_version") != 2:
            task["contract_version"] = 2
            task["supersedes"] = IDS[tid]
            task["budget_note"] = ("step budget raised 8 -> 20 by the 2026-11-01 bounded "
                                  "requalification; scope, probe, acceptance, commit paths, "
                                  "tools and limits unchanged")
        task["max_steps"] = 20
REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(json.dumps({t["id"]: {"max_steps": t["max_steps"],
                            "contract_version": t.get("contract_version"),
                            "supersedes": t.get("supersedes")}
                  for t in data["tasks"] if t.get("id") in IDS}, indent=2))
