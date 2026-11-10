"""Point the three qualification tasks at the screened qwen3.5:4b lane (native tools)."""
from __future__ import annotations

import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"
IDS = ("ty-artifact-jpeg", "ty-hitl-skip-report", "ty-diff-select-headers")

data = json.loads(REG.read_text(encoding="utf-8-sig"))
for task in data["tasks"]:
    if task.get("id") in IDS:
        task["model"] = "qwen3.5:4b"
        task["provider"] = "ollama"
        task["num_ctx"] = 8192
        task["native_tools"] = True
        task["max_steps"] = 10
        task["max_protocol_errors"] = 8
        task["allowed_tools"] = ["read", "ast_edit", "run", "finish"]
REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(json.dumps({t["id"]: {k: t.get(k) for k in ("model", "num_ctx", "native_tools",
                                                  "max_steps")}
                  for t in data["tasks"] if t.get("id") in IDS}, indent=2))
