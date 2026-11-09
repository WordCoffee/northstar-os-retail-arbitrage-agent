"""The held-out set: it must be buildable, valid, and honest about the line it cannot score.

Two things are being proven here. First, the briefs are a valid catalogue under the same validator
the tuned catalogue uses — a held-out brief that the pipeline cannot even read is not a test.
Second, the report never turns a missing product photograph into a score: Neck Nirvana is declared
`declared_unscorable` and appears in the report as such, and a `cannot_verify` row counts as a
failure rather than a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from seller_tester.briefs import validate_catalog  # noqa: E402

import heldout_briefs  # noqa: E402
import heldout_run  # noqa: E402


@pytest.fixture(scope="module")
def payload():
    return heldout_briefs.build()


def test_twenty_one_runnable_briefs_across_two_real_lines(payload):
    briefs = payload["briefs"]
    assert len(briefs) == 21
    assert {b["product_line"] for b in briefs} == {"lions-mane", "word-coffee"}
    # every runnable brief has a real reference on disk — that is what makes it a test
    for brief in briefs:
        path = brief["reference"]["path"]
        assert path, brief["id"]
        assert (ROOT / path).is_file(), f"{brief['id']} points at a missing reference {path}"


def test_the_set_validates_under_the_same_validator_as_the_catalogue(payload):
    assert validate_catalog(payload, require_coverage=False) == []


def test_ids_and_pairs_are_unique(payload):
    briefs = payload["briefs"]
    assert len({b["id"] for b in briefs}) == len(briefs)
    pairs = [(b["category"], b["situation"], b["difficulty"], b["source_mode"]) for b in briefs]
    assert len(set(pairs)) == len(pairs)


def test_text_rules_are_the_ones_the_pipeline_understands(payload):
    allowed = {"no_text", "allowed", "text_expected"}
    for brief in payload["briefs"]:
        assert brief["constraints"]["text_rule"] in allowed, brief["id"]
    # a white-background main image must be text free; an infographic must expect text
    by_situation = {b["situation"]: b["constraints"]["text_rule"] for b in payload["briefs"]}
    assert by_situation["white_background_main"] == "no_text"
    assert by_situation["infographic"] == "text_expected"


def test_neck_nirvana_is_declared_and_never_runnable(payload):
    declared = payload["declared_unscorable"]
    assert len(declared) == 3
    assert {b["product_line"] for b in declared} == {"neck-nirvana"}
    assert all(b["reference"]["path"] is None for b in declared)
    runnable_ids = {b["id"] for b in payload["briefs"]}
    assert not runnable_ids & {b["id"] for b in declared}


def test_a_cannot_verify_row_is_a_failure_not_a_pass(tmp_path, monkeypatch, payload):
    briefs_path = tmp_path / "briefs.json"
    briefs_path.write_text(json.dumps(payload), encoding="utf-8")
    proof_path = tmp_path / "proof.json"
    first = payload["briefs"][0]["id"]
    second = payload["briefs"][1]["id"]
    proof_path.write_text(json.dumps({"results": [
        {"brief_id": first, "score": 90.0, "passed": True, "failed_checks": []},
        {"brief_id": second, "score": 40.0, "passed": False, "cannot_verify": True,
         "failed_checks": ["product_region"]},
    ]}), encoding="utf-8")
    monkeypatch.setattr(heldout_run, "BRIEFS", briefs_path)
    monkeypatch.setattr(heldout_run, "PROOF", proof_path)
    monkeypatch.setattr(heldout_run, "PROOF_FALLBACK", tmp_path / "absent.json")
    monkeypatch.setattr(heldout_run, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(heldout_run, "REPORT", tmp_path / "report.md")
    summary = heldout_run.split()["summary"]
    assert summary["scored"] == 2
    assert summary["passed"] == 1
    assert summary["mean"] == 65.0  # (90 + 40) / 2, not 90 over the passing rows alone
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "neck-nirvana" in report and "not scored" in report
    assert "**not scored**" in report


def test_the_proof_it_reads_is_named(tmp_path, monkeypatch, payload):
    briefs_path = tmp_path / "briefs.json"
    briefs_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(heldout_run, "BRIEFS", briefs_path)
    monkeypatch.setattr(heldout_run, "PROOF", tmp_path / "absent.json")
    monkeypatch.setattr(heldout_run, "PROOF_FALLBACK", tmp_path / "also-absent.json")
    monkeypatch.setattr(heldout_run, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(heldout_run, "REPORT", tmp_path / "report.md")
    result = heldout_run.split()
    assert result["summary"]["scored"] == 0
    assert result["summary"]["mean"] is None
    assert result["proof"].endswith("also-absent.json")
