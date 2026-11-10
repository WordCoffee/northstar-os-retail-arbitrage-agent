"""Freeze the quad-area contract for the unattended Go lane run."""
from __future__ import annotations

import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"

TASK = {
    "id": "ty-quad-area-guard",
    "name": "A degenerate dieline quad is refused",
    "schema_version": 2,
    "authorized": True,
    "authorization_note": (
        "Local-only behavioural fix discovered and frozen during the 2026-11-02 "
        "unattended campaign. No auth, tenancy, billing, security, provider or external "
        "I/O. The probe is read-only and outside the author's write scope."),
    "risk": "low",
    "risk_class": "low",
    "execution": "ty",
    "contract_version": 1,
    "objective": (
        "Northstar_backend/print_prep.py has one behavioural defect: face_pixels() "
        "measures the face as the mean of opposite edges, so a COLLINEAR quad (all four "
        "corners on one line) yields a positive width and height even though the shape has "
        "zero area, and the print gate then reports a face no die can cut. Read the file "
        "and fix face_pixels so a quad whose corners are collinear - or whose computed "
        "area is zero - raises ValueError, while a valid quad still returns its width and "
        "height. The read-only probe state/probes/t8_quad_area.py is the contract - run it "
        "to check your change; if it fails, edit the source file - never the probe. "
        "Change only that file."),
    "write_paths": ["Northstar_backend/print_prep.py"],
    "read_paths": ["Northstar_backend/print_prep.py", "state/probes/t8_quad_area.py"],
    "checks": [{"name": "quad area probe", "cwd": ".",
                "cmd": ["python", "state/probes/t8_quad_area.py"]}],
    "acceptance_commands": [["python", "state/probes/t8_quad_area.py"]],
    "commit_paths": ["Northstar_backend/print_prep.py"],
    "commit_message": "fix(print): refuse a degenerate dieline quad instead of measuring it",
    "required_artifact": "Northstar_backend/print_prep.py",
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
print(json.dumps({"frozen": TASK["id"], "probe": TASK["checks"][0]["cmd"]}, indent=2))
