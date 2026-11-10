"""Record the first unattended Go-lane trajectory (append-only, idempotent)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fix_patterns as fp

ROW = {
    "task": "ty-quad-area-guard",
    "defect_class": "geometry-degenerate-quad",
    "outcome": "accepted",
    "author": "deepseek-v4.1-flash via opencode-go CLI (unattended)",
    "read_sequence": ["Northstar_backend/print_prep.py",
                      "state/probes/t8_quad_area.py"],
    "edit_attempts": [{"n": 1, "op": "search/replace", "result": "applied",
                       "note": "corner-collinearity area check before the edge means"}],
    "self_revisions": [],
    "envelope_rejections": 6,
    "note": ("the first six replies were rejected by the lane's JSON contract, not by the "
             "author's self-review; the seventh applied cleanly"),
    "final_edit": {"op": "search/replace", "target": "face_pixels",
                   "shape": "reject a zero-area/collinear quad before measuring edges"},
    "probe_before": "FAIL (1): collinear quad accepted as 5.0x10.0",
    "probe_after": "PASS",
    "commit": "c0111fde",
    "pattern": ("A measurement that takes four corners must first prove they enclose an "
                "area: collinear or coincident corners yield positive edge means but no "
                "face, so the area check belongs before the edge arithmetic."),
    "summary": "The dieline gate refuses a degenerate quad instead of measuring it.",
}


def main() -> int:
    existing = {(e.get("task"), e.get("commit")) for e in fp.entries()}
    added = []
    if (ROW["task"], ROW["commit"]) not in existing:
        fp.record(ROW)
        added.append(ROW["task"])
    print(json.dumps({"added": added, "total": len(fp.entries())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
