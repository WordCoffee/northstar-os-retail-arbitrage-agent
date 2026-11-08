"""D5 - the gap queue and the idle-is-a-failure rule.

The queue is the ranked gap list, and an empty queue while services are below the bar is
a defect with a paper trail - not a quiet finish. Both are tested here against a
temporary queue database.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import director_queue as DQ  # noqa: E402
import director_gaps as G  # noqa: E402


def _row(sid, score, gap, weakest="works", impact=0.8):
    return {"id": sid, "label": sid.title(), "score": score, "bar": 85.0, "gap": gap,
            "impact": impact, "weakest": weakest, "meets_bar": score >= 85.0}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    scores = tmp_path / "scorecards.json"
    scores.write_text(json.dumps({"services": [
        _row("prospector", 15.0, 56.0),
        _row("thewatch", 60.0, 20.0),
        _row("listings", 88.5, 0.0, weakest="measured"),
        _row("golden-goose", 75.0, 8.0, weakest="complete"),
        _row("rivalboard", 82.0, 2.0, weakest="complete"),
        _row("rankledger", 83.0, 1.5, weakest="complete"),
    ]}), encoding="utf-8")
    monkeypatch.setattr(G, "SCORES", scores)
    monkeypatch.setattr(G, "SELF", tmp_path / "self_assessment.md")
    monkeypatch.setattr(G, "NEEDS", tmp_path / "needs_you.md")
    monkeypatch.setattr(DQ, "DB", tmp_path / "state" / "queue.sqlite")
    mirror = tmp_path / "reports" / "director_queue.json"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(json.dumps({"units": {}, "jobs": []}), encoding="utf-8")
    monkeypatch.setattr(DQ, "MIRROR", mirror)
    return tmp_path


def test_only_services_below_the_bar_are_ranked(world):
    rows = G.rank()
    ids = [row["id"] for row in rows]

    assert "listings" not in ids                 # at the bar
    assert ids[0] == "prospector"                # biggest gap first
    assert ids == sorted(ids, key=lambda one: -next(
        row["gap"] for row in rows if row["id"] == one))


def test_a_single_small_gap_waits_for_company_instead_of_becoming_an_edit(world):
    small = [row for row in G.rank() if row["id"] in ("rivalboard", "rankledger")]
    bundles = G.bundle(small)

    assert len(bundles) == 1
    assert set(bundles[0]["services"]) == {"rivalboard", "rankledger"}
    assert bundles[0]["points"] < G.MIN_POINTS
    assert "micro-edit" in bundles[0]["why"]


def test_a_large_gap_is_worth_a_builder_on_its_own(world):
    bundles = G.bundle([row for row in G.rank() if row["id"] == "prospector"])

    assert len(bundles) == 1
    assert bundles[0]["services"] == ["prospector"]
    assert bundles[0]["points"] == 70.0
    assert bundles[0]["write_paths"]


def test_an_empty_queue_is_replanned_not_idled(world):
    assert G.open_jobs() == []

    out = G.replan()

    assert out["ok"] is True and out["reason"] == "replanned"
    assert out["added"], out
    assert len(G.open_jobs()) >= 1


def test_an_impossible_bundle_is_written_down_as_a_defect(world, monkeypatch):
    monkeypatch.setattr(G, "bundle", lambda rows=None: [])

    out = G.replan()

    assert out["ok"] is False and out["reason"] == "no_viable_bundle"
    text = (world / "self_assessment.md").read_text(encoding="utf-8")
    assert "idle while below the bar" in text
    assert "no bundle clears the size threshold" in text
    assert "Director idle" in (world / "needs_you.md").read_text(encoding="utf-8")


def test_no_gaps_is_a_finish_not_a_defect(world, monkeypatch):
    monkeypatch.setattr(G, "SCORES", world / "perfect.json")
    (world / "perfect.json").write_text(json.dumps({"services": [
        _row("listings", 90.0, 0.0)]}), encoding="utf-8")

    out = G.replan()

    assert out["ok"] is True and out["reason"] == "no_gaps"
    assert not (world / "self_assessment.md").exists()
