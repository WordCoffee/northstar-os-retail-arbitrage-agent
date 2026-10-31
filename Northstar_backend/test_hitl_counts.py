"""Ty-generated HITL counts helper: behavior and missing-directory case."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel.hitl_counts import hitl_counts


def test_counts_pending_approved_denied(tmp_path):
    root = tmp_path / "root"
    hitl = root / "state" / "hitl"
    hitl.mkdir(parents=True)
    for i, status in enumerate(("pending", "approved", "denied", "pending")):
        (hitl / f"hitl_20260101T00000{i}_deadbeef.json").write_text(
            json.dumps({"id": i, "status": status}), encoding="utf-8")
    assert hitl_counts(root) == {"pending": 2, "approved": 1, "denied": 1, "total": 4}


def test_missing_state_directory_returns_zeros(tmp_path):
    assert hitl_counts(tmp_path / "empty") == {
        "pending": 0, "approved": 0, "denied": 0, "total": 0,
    }
