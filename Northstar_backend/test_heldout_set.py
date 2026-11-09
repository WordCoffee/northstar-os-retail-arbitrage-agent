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


def test_the_mode_label_stays_stored_reference_only_until_both_other_modes_reach_ten():
    rows = [{"source_mode": "uploaded_reference", "score": 90.0, "passed": True} for _ in range(21)]
    coverage = heldout_run.mode_coverage(rows)
    assert coverage["label"] == "stored-reference only"
    assert coverage["counts"]["uploaded_reference"] == 21


def test_the_label_lifts_only_when_prompt_only_and_stored_reference_are_both_covered():
    rows = ([{"source_mode": "prompt_only", "score": 1.0, "passed": False}] * 10
            + [{"source_mode": "stored_reference", "score": 1.0, "passed": False}] * 10
            + [{"source_mode": "uploaded_reference", "score": 1.0, "passed": False}] * 1)
    assert heldout_run.mode_coverage(rows)["label"] == "all three modes"
    # one mode short is still short
    short = rows[:-11]
    assert heldout_run.mode_coverage(short)["label"] == "stored-reference only"


def test_the_mode_table_shows_unmeasured_modes_at_zero_rather_than_omitting_them():
    rows = [{"source_mode": "uploaded_reference", "score": 80.0, "passed": True},
            {"source_mode": "uploaded_reference", "score": 60.0, "passed": False}]
    table = heldout_run.by_mode(rows)
    assert list(table) == ["prompt_only", "stored_reference", "uploaded_reference"]
    assert table["prompt_only"] == {"n": 0, "passed": 0, "mean": None}
    assert table["uploaded_reference"] == {"n": 2, "passed": 1, "mean": 70.0}


def test_no_brief_treats_a_brand_wordmark_as_the_product(payload):
    """A logo is not a product: two briefs that shared one produced byte-identical composites."""
    for brief in payload["briefs"]:
        name = Path(brief["reference"]["path"]).name.lower()
        assert "logo" not in name, f"{brief['id']} uses a wordmark as its reference"
        assert "wordmark" not in name, brief["id"]


def test_every_reference_is_on_the_reviewed_roster_and_distinct(payload):
    """Bytes, not names: two "different" files were one photograph, and one "product" file was a card.

    Distinct *files* must be distinct photographs. A photograph may still serve several briefs
    (three Mogra images carry ten Lion's Mane briefs) — that is disclosed in the report's limits.
    """
    import hashlib

    roster = set(heldout_briefs.HELDOUT_REFERENCES)
    for brief in payload["briefs"]:
        assert brief["reference"]["path"] in roster, (
            f"{brief['id']} uses {brief['reference']['path']}, which is not on the reviewed roster")
    by_hash = {}
    for path in sorted({b["reference"]["path"] for b in payload["briefs"]}):
        digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert digest not in by_hash, (
            f"{path} is byte-identical to {by_hash[digest]}; that is one photograph sold twice")
        by_hash[digest] = path
    assert len(by_hash) >= 8, f"only {len(by_hash)} distinct photographs"


def test_a_reference_is_never_reused_for_the_same_situation(payload):
    """Ten Lion's Mane briefs share three photographs and eleven Word Coffee briefs share seven:
    that is the real stock of product imagery on this machine. What must not happen is the same
    product being tested twice in the same situation, which would be one test wearing two ids."""
    pairs = [(b["reference"]["path"], b["situation"]) for b in payload["briefs"]]
    assert len(pairs) == len(set(pairs)), "the same product is tested twice in one situation"
    distinct = {b["reference"]["path"] for b in payload["briefs"]}
    assert len(distinct) >= 8, f"only {len(distinct)} distinct products; the set is too thin"


def test_each_situation_inherits_the_tuned_bar_for_that_situation(payload):
    """The held-out part of a brief is the product photograph, never the constraint.

    The first held-out run copied one brief's constraints onto all eight situations, which put a
    required white matte on lifestyle and infographic briefs and made 21 of 21 fail `alpha_matte`
    for a rule that was never about them. This is the test that stops that coming back.
    """
    catalog = json.loads((ROOT / "ty" / "seller_briefs.json").read_text(encoding="utf-8"))
    tuned = {}
    for brief in catalog["briefs"]:
        if brief.get("source_mode") == "prompt_only":
            continue
        tuned.setdefault(brief["situation"], brief["constraints"])
    for brief in payload["briefs"]:
        assert brief["constraints"] == tuned[brief["situation"]], brief["id"]
        assert set(brief["constraints"]) >= {"dimensions", "aspect", "background", "fill_pct"}


def test_a_white_matte_is_only_required_where_the_tuned_catalogue_requires_it(payload):
    white = {"white_background_main", "scale_reference", "bundle_multipack", "background_swap",
             "series_consistency"}
    for brief in payload["briefs"]:
        mode = (brief["constraints"].get("matte") or {}).get("mode", "any")
        if brief["situation"] in white:
            assert mode == "white_matte", brief["id"]
        else:
            assert mode == "any", f"{brief['situation']} must not demand a white matte"


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
