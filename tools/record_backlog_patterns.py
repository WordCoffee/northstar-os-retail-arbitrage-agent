"""Record the three backlog-pass trajectories (append-only, idempotent)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fix_patterns as fp

AUTHOR = "deepseek-v4.1-flash (opencode-go, operator session)"

ROWS = [
    {
        "task": "ty-dpi-image-guard",
        "defect_class": "validator-ignores-input",
        "outcome": "accepted",
        "author": AUTHOR,
        "read_sequence": ["Northstar_backend/print_prep.py",
                          "state/probes/t1_dpi_image_guard.py"],
        "edit_attempts": [{"n": 1, "op": "replace_function_body:dpi_report",
                           "result": "applied"}],
        "self_revisions": [
            "self-review: image_size is unpacked defensively (TypeError/ValueError/IndexError/KeyError -> ValueError)",
            "self-review: the positive control must still return a report, so the guard runs before face_pixels",
            "self-review: face-vs-image is compared in pixels, not millimetres",
        ],
        "final_edit": {"op": "replace_function_body", "target": "dpi_report",
                       "shape": "validate image_size, then face <= image, then measure"},
        "probe_before": "FAIL (3): zero size, negative size, face larger than the image",
        "probe_after": "PASS",
        "commit": "d5ba3ced",
        "pattern": ("A measurement function that takes the source dimensions and then "
                    "never reads them is repaired by validating the dimensions first and "
                    "refusing a measurement that is physically impossible for them, while "
                    "leaving the normal path untouched."),
        "summary": "The print gate now refuses a quad that cannot belong to the image.",
    },
    {
        "task": "ty-frame-fill-guard",
        "defect_class": "missing-input-validation",
        "outcome": "accepted",
        "author": AUTHOR,
        "read_sequence": ["Northstar_backend/image_prep.py",
                          "state/probes/t2_frame_fill_guard.py"],
        "edit_attempts": [
            {"n": 1, "op": "replace_function_body:frame_on_white", "result": "applied",
             "note": "ran the probe before submitting: NameError - math was not imported"},
            {"n": 2, "op": "add_import:math", "result": "applied"},
        ],
        "self_revisions": [
            "self-review caught a missing `import math` by running the probe BEFORE submitting",
            "self-review: isfinite covers nan/inf, and the range check is half-open (0, 1]",
            "self-review: the empty-subject refusal reuses alpha_bbox, matching hero_on_white",
        ],
        "final_edit": {"op": "replace_function_body", "target": "frame_on_white",
                       "shape": "validate fill, refuse empty subject, then frame"},
        "probe_before": "FAIL (4): fill 0, -0.5, 1.5 and an empty cutout",
        "probe_after": "PASS",
        "commit": "9f692f21",
        "pattern": ("An entry point that scales a subject by a caller-supplied fraction "
                    "must validate that fraction and the subject before drawing: a fraction "
                    "outside (0, 1] crops the product, and an empty subject yields a blank "
                    "canvas presented as an artefact."),
        "summary": "Framing refuses an impossible fill and an empty cutout.",
    },
    {
        "task": "ty-hero-fill-guard",
        "defect_class": "missing-input-validation",
        "outcome": "accepted",
        "author": AUTHOR,
        "read_sequence": ["Northstar_backend/listing_image.py",
                          "state/probes/t3_hero_fill_guard.py"],
        "edit_attempts": [{"n": 1, "op": "replace_function_body:hero_on_white",
                           "result": "applied"}],
        "self_revisions": [
            "self-review: the same guard shape as frame_on_white, so the two lanes cannot drift",
            "self-review: the existing empty-subject refusal is preserved, not reimplemented",
            "self-review: fill=1.0 remains a valid boundary and still returns a PNG",
        ],
        "final_edit": {"op": "replace_function_body", "target": "hero_on_white",
                       "shape": "validate fill before any pixel is drawn"},
        "probe_before": "FAIL (5): fill 0, -1, 1.5, nan, inf",
        "probe_after": "PASS",
        "commit": "fa46b397",
        "pattern": ("Two lanes that render the same subject at a caller-supplied scale "
                    "must share one validation rule; fixing the first lane and copying the "
                    "same guard to the second prevents the pair from drifting."),
        "summary": "The MAIN image refuses a fill that would crop the product away.",
    },
]


def main() -> int:
    existing = {(e.get("task"), e.get("commit")) for e in fp.entries()}
    added = []
    for row in ROWS:
        if (row["task"], row["commit"]) in existing:
            continue
        fp.record(row)
        added.append(row["task"])
    print(json.dumps({"added": added, "total": len(fp.entries())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
