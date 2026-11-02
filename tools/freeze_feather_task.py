"""Freeze the feather-sigma contract for the production campaign batch."""
from __future__ import annotations

import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"

TASK = {
    "id": "ty-feather-sigma-guard",
    "name": "A failed warp fit is refused, not blurred",
    "schema_version": 2,
    "authorized": True,
    "authorization_note": (
        "Local-only behavioural fix from the 2026-11-02 production register. No auth, "
        "tenancy, billing, security, provider or external I/O; the probe is read-only "
        "and outside the author's write scope."),
    "risk": "low",
    "risk_class": "low",
    "execution": "ty",
    "contract_version": 1,
    "objective": (
        "Northstar_backend/mockup_compositor.py has one behavioural defect: "
        "feather_sigma() turns the measured residual of a warp fit into a feather width, "
        "but a NON-FINITE residual (nan, inf, -inf) is silently mapped to the default "
        "clamp instead of being refused - so a failed geometry fit produces a normal-"
        "looking composite with a hard edge. Read the file and fix feather_sigma so a "
        "non-finite residual raises ValueError while a finite one still clamps into "
        "[lo, hi] monotonically. The read-only probe state/probes/t9_feather_sigma.py is "
        "the contract - run it to check your change; if it fails, edit the source file - "
        "never the probe. Change only that file."),
    "write_paths": ["Northstar_backend/mockup_compositor.py"],
    "read_paths": ["Northstar_backend/mockup_compositor.py",
                   "state/probes/t9_feather_sigma.py"],
    "checks": [{"name": "feather sigma probe", "cwd": ".",
                "cmd": ["python", "state/probes/t9_feather_sigma.py"]}],
    "acceptance_commands": [["python", "state/probes/t9_feather_sigma.py"]],
    "commit_paths": ["Northstar_backend/mockup_compositor.py"],
    "commit_message": "fix(compositor): refuse a non-finite warp residual instead of feathering it",
    "required_artifact": "Northstar_backend/mockup_compositor.py",
    "timeout_seconds": 600,
    "max_repairs": 1,
    "max_steps": 8,
    "model": "qwen3.5:4b",
    "provider": "ollama",
    "num_ctx": 8192,
    "native_tools": True,
    "allowed_tools": ["read", "ast_edit", "run", "finish"],
    "author_lane": "opencode-go/deepseek-v4.1-flash (unattended CLI)",
}

data = json.loads(REG.read_text(encoding="utf-8-sig"))
tasks = [t for t in data["tasks"] if t.get("id") != TASK["id"]]
tasks.append(TASK)
data["tasks"] = tasks
data["updated_at"] = "2026-11-02"
REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"frozen": TASK["id"]}, indent=2))
