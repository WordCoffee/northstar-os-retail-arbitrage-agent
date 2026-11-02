"""Record the three accepted trajectories produced in this campaign.

Data comes from the supervisor's own run records and the author's tool history,
not from a summary written after the fact. Idempotent: a task already recorded with
the same commit is skipped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fix_patterns as fp

AUTHOR = "deepseek-v4.1-flash (opencode-go, operator session)"
SHARED_PATTERN = ("A silent-skip loop is repaired by adding a counter that is "
                  "initialised with the other counters, incremented in the exact "
                  "branch that discards the record, and returned alongside them; the "
                  "existing total keeps its meaning and is not recomputed from the "
                  "new counter.")

TRAJECTORIES = [
    {
        "task": "ty-hitl-skip-report",
        "defect_class": "silent-skip-counter",
        "outcome": "accepted",
        "author": AUTHOR,
        "model_lane": "qwen3.5:4b (local supervisor + author)",
        "read_sequence": ["Northstar_backend/agent_kernel/hitl_counts.py",
                          "state/probes/t5_hitl_corrupt.py"],
        "edit_attempts": [{"n": 1, "op": "replace_function_body:hitl_counts",
                           "result": "applied", "note": "included the def line; the tool stripped it"}],
        "self_revisions": ["ran the probe after the edit and re-read the file to confirm the return"],
        "final_edit": {"op": "replace_function_body", "target": "hitl_counts",
                       "shape": "add skipped counter + return key"},
        "probe_before": "FAIL (1): unreadable records are reported",
        "probe_after": "PASS",
        "steps": 5,
        "commit": "883a7fed",
        "pattern": SHARED_PATTERN,
        "summary": "Count the records the loop throws away instead of dropping them silently.",
    },
    {
        "task": "ty-artifact-jpeg",
        "defect_class": "classifier-missing-branch",
        "outcome": "accepted",
        "author": AUTHOR,
        "model_lane": "external author + qwen3.5:4b supervisor",
        "read_sequence": ["Northstar_backend/agent_kernel/artifacts.py",
                          "state/probes/t7_artifact_jpeg.py"],
        "edit_attempts": [{"n": 1, "op": "replace_function_body:artifact_kind",
                           "result": "applied",
                           "note": "new .jpg/.jpeg branch before the video branch"}],
        "self_revisions": [
            "self-review: a missing file and a 1-byte file must not raise",
            "self-review: real JPEGs carry trailing bytes, so EOI is searched in the last 64 bytes",
            "self-review: suffix check is lowercased, so .JPG matches",
        ],
        "final_edit": {"op": "replace_function_body", "target": "artifact_kind",
                       "shape": "SOI check + tail EOI scan -> image_jpeg / jpeg_invalid"},
        "probe_before": "FAIL (2): valid jpeg classified as an image; broken magic refused",
        "probe_after": "PASS",
        "steps": 1,
        "commit": "9e8e2cdb",
        "pattern": ("A classifier that handles some magic bytes but not one of the "
                    "formats its callers already emit is repaired by adding the missing "
                    "branch in the existing order, validating the real header and the "
                    "real trailer, and leaving every other branch untouched."),
        "summary": "Recognise the format the pipeline already produces instead of calling it binary.",
    },
    {
        "task": "ty-diff-select-headers",
        "defect_class": "fragment-loses-context",
        "outcome": "accepted",
        "author": AUTHOR,
        "model_lane": "external author + qwen3.5:4b supervisor",
        "read_sequence": ["Northstar_backend/agent_kernel/diff.py",
                          "state/probes/t6_diff_select_headers.py"],
        "edit_attempts": [{"n": 1, "op": "replace_function_body:select_hunks",
                           "result": "applied",
                           "note": "carries the file header pair per selected hunk"}],
        "self_revisions": [
            "self-review: two selected hunks from one file must not repeat the header",
            "self-review: an empty selection must return an empty string, not a bare header",
            "self-review: multi-file diffs must keep each hunk with its own file header",
        ],
        "final_edit": {"op": "replace_function_body", "target": "select_hunks",
                       "shape": "hunk index -> preceding ---/+++ pair, emitted once per file"},
        "probe_before": "FAIL (2): one/both hunks keep the file header",
        "probe_after": "PASS",
        "steps": 1,
        "commit": "e1585917",
        "pattern": ("A function that returns a fragment of a structured document must "
                    "carry the context that makes the fragment usable: map each element "
                    "to its enclosing header while parsing, emit the header once per "
                    "group, and preserve the input order."),
        "summary": "A selected hunk must still name its target file.",
    },
]


def main() -> int:
    added = []
    existing = {(e.get("task"), e.get("commit")) for e in fp.entries()}
    for item in TRAJECTORIES:
        if (item["task"], item["commit"]) in existing:
            continue
        fp.record(item)
        added.append(item["task"])
    print(json.dumps({"added": added, "total": len(fp.entries())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
