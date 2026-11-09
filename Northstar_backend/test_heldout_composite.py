"""The resumable held-out composite pass: merge, resume, and never touch the tuned proof.

The behaviour that matters is the one a crash exposes. If the pass dies at brief 15, the fourteen
finished briefs must survive, the next run must pick up only the seven that are left, and the tuned
three-brief proof must still be exactly what it was.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import heldout_composite as H  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    briefs = {"briefs": [{"id": f"HO-{n:03d}", "situation": "lifestyle"} for n in range(1, 5)]}
    briefs_path = tmp_path / "briefs.json"
    briefs_path.write_text(json.dumps(briefs), encoding="utf-8")
    monkeypatch.setattr(H, "BRIEFS", briefs_path)
    monkeypatch.setattr(H, "PROOF", tmp_path / "heldout_composite_proof.json")
    monkeypatch.setattr(H, "GAPS", tmp_path / "heldout_gaps.json")
    monkeypatch.setattr(H, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(H, "WORK", tmp_path / "work")
    return tmp_path


def _row(brief_id, score, passed):
    return {"brief_id": brief_id, "score": score, "passed": passed}


def test_merge_accumulates_and_recomputes_from_rows(isolated):
    H.merge({"results": [_row("HO-001", 100.0, True), _row("HO-002", 50.0, False)]})
    H.merge({"results": [_row("HO-003", 80.0, True)]})
    proof = json.loads((isolated / "heldout_composite_proof.json").read_text(encoding="utf-8"))
    assert [row["brief_id"] for row in proof["results"]] == ["HO-001", "HO-002", "HO-003"]
    assert proof["scored"] == 3
    assert proof["passed"] == 2
    assert proof["mean_score"] == 76.7  # (100 + 50 + 80) / 3


def test_merge_overwrites_a_repeated_brief_rather_than_double_counting(isolated):
    H.merge({"results": [_row("HO-001", 40.0, False)]})
    H.merge({"results": [_row("HO-001", 100.0, True)]})
    proof = json.loads((isolated / "heldout_composite_proof.json").read_text(encoding="utf-8"))
    assert len(proof["results"]) == 1
    assert proof["mean_score"] == 100.0


def test_a_cannot_verify_row_counts_as_done_but_not_passed(isolated):
    H.merge({"results": [{"brief_id": "HO-002", "score": 0.0, "passed": False,
                          "cannot_verify": True}]})
    state = H.status()
    assert "HO-002" not in state["remaining"]
    assert state["passed"] == 0


def test_status_lists_exactly_the_briefs_with_no_verdict(isolated):
    H.merge({"results": [_row("HO-001", 100.0, True)]})
    state = H.status()
    assert state["done"] == 1
    assert state["remaining"] == ["HO-002", "HO-003", "HO-004"]


def test_a_crash_between_chunks_keeps_what_finished(isolated, monkeypatch):
    # the second chunk fails outright: its proof is never written
    calls = {"n": 0}

    def fake_run_chunk(chunk, renderer, model, scene_size, steps, briefs):
        calls["n"] += 1
        if calls["n"] == 1:
            H.merge({"results": [_row(b["id"], 90.0, True) for b in briefs]})
            return {"ok": True, "returncode": 0, "rows": len(briefs)}
        return {"ok": False, "returncode": 1, "error": "KSampler crashed"}

    monkeypatch.setattr(H, "run_chunk", fake_run_chunk)
    code = H.main(["--run", "--chunk", "2"])
    assert code == 2
    state = H.status()
    assert state["done"] == 2
    assert state["remaining"] == ["HO-003", "HO-004"]


def test_the_tuned_proof_is_never_the_target(isolated):
    assert H.PROOF.name != "composite_proof.json"
    assert H.PROOF.name.startswith("heldout_")
