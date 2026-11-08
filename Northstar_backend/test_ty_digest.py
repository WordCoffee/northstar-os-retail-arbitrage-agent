"""The disk floor and the digest (WORK ORDER 3, folded fix 5)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ty_digest  # noqa: E402


def test_the_floor_refuses_below_five_gigabytes():
    low = ty_digest.allow_download(free=4.99)
    assert low["allow"] is False
    assert "below" in low["reason"]
    assert low["floor_gb"] == 5.0


def test_the_floor_allows_at_the_boundary_and_above():
    assert ty_digest.allow_download(free=5.0)["allow"] is True
    assert ty_digest.allow_worktree(free=11.2)["allow"] is True


def test_free_space_reads_from_disk():
    space = ty_digest.free_gb()
    assert space > 0


def test_the_digest_reports_free_space_even_with_no_other_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(ty_digest, "TY", tmp_path)
    monkeypatch.setattr(ty_digest, "QUEUE", tmp_path / "director_queue.json")
    monkeypatch.setattr(ty_digest, "SCORES", tmp_path / "scorecards.json")
    monkeypatch.setattr(ty_digest, "DB", tmp_path / "missing.sqlite")
    result = ty_digest.write(out=tmp_path / "digest.md")
    text = Path(result["path"]).read_text(encoding="utf-8")
    assert "Disk free:" in text
    assert "floor 5.0 GB" in text


def test_the_digest_ranks_the_worst_gaps_first(tmp_path, monkeypatch):
    scores = {"services": [
        {"id": "a", "score": 10, "bar": 85, "gap": 75, "weakest": "works", "meets_bar": False},
        {"id": "b", "score": 60, "bar": 85, "gap": 25, "weakest": "usable", "meets_bar": False},
        {"id": "c", "score": 90, "bar": 85, "gap": 0, "weakest": "", "meets_bar": True},
    ]}
    (tmp_path / "scorecards.json").write_text(json.dumps(scores), encoding="utf-8")
    monkeypatch.setattr(ty_digest, "TY", tmp_path)
    monkeypatch.setattr(ty_digest, "QUEUE", tmp_path / "nope.json")
    monkeypatch.setattr(ty_digest, "SCORES", tmp_path / "scorecards.json")
    monkeypatch.setattr(ty_digest, "DB", tmp_path / "nope.sqlite")
    data = ty_digest.collect()
    assert data["services"]["total"] == 3
    assert data["services"]["below_bar"] == 2
    assert [row["id"] for row in data["services"]["top_gaps"]] == ["a", "b"]


def test_missing_inputs_are_reported_as_zero_not_invented(tmp_path, monkeypatch):
    monkeypatch.setattr(ty_digest, "TY", tmp_path)
    monkeypatch.setattr(ty_digest, "QUEUE", tmp_path / "nope.json")
    monkeypatch.setattr(ty_digest, "SCORES", tmp_path / "nope.json")
    monkeypatch.setattr(ty_digest, "DB", tmp_path / "nope.sqlite")
    data = ty_digest.collect()
    assert data["seller_gaps"] == 0
    assert data["intel_findings"] == 0
    assert data["in_flight"] == ""
