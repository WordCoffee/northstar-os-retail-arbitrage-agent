import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_kernel.hitl_counts import hitl_counts


def test_hitl_counts_accepts_a_string_root(tmp_path):
    root = tmp_path / "root"
    hitl = root / "state" / "hitl"
    hitl.mkdir(parents=True)
    (hitl / "hitl_20260101T000000_deadbeef.json").write_text(
        json.dumps({"status": "pending"}), encoding="utf-8")
    (hitl / "hitl_20260101T000001_deadbeef.json").write_text(
        json.dumps({"status": "approved"}), encoding="utf-8")
    assert hitl_counts(str(root)) == {
        "pending": 1, "approved": 1, "denied": 0, "skipped": 0, "total": 2,
    }
