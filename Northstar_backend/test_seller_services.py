"""Beyond images: the four service paths, exercised end to end and scored.

Each path is the one a seller walks: a listing proposal through the app's own
composer, a bulksheet through the PPC API, a Golden Goose scan through the real fee
stack, and a research query through the local corpus graph. Every test here runs
offline against the shipped fixtures, and every check has a control that proves it
can fail — a suite that only shows green checks cannot tell a passing path from a
check that never looked.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.seller_tester import services as svc


# ── fixtures ─────────────────────────────────────────────────────────────────

def test_the_fixture_file_carries_all_four_paths():
    payload = svc.load_fixtures()
    assert set(svc.PATHS) <= set(payload)
    for name in svc.PATHS:
        assert payload[name], f"{name} has no fixture"
    assert len(payload["listing"]) >= 2
    ppc = payload["ppc"][0]
    assert ppc["rows"][0][0] == "Product" and len(ppc["rows"]) >= 5
    assert {c["asin"] for c in payload["golden_goose"][0]["candidates"]} >= {
        "B0TEST0001", "B0TEST0003"}
    assert payload["research"][0]["corpus"]


def test_only_parsing_refuses_an_unknown_path_by_name():
    assert svc.parse_only("ppc") == ["ppc"]
    assert svc.parse_only(None) == list(svc.PATHS)
    assert svc.parse_only("research,listing") == ["listing", "research"]
    with pytest.raises(ValueError) as caught:
        svc.parse_only("ppc,images")
    assert "images" in str(caught.value)


# ── listing ──────────────────────────────────────────────────────────────────

def test_a_listing_brief_scores_through_the_apps_own_composer(tmp_path):
    brief = svc.load_fixtures()["listing"][0]
    row = svc.run_listing(brief, work_dir=tmp_path / "listing")
    assert row["score"] == 100.0, json.dumps(row["checks"], indent=1)
    assert row["passed"] is True and row["failed_checks"] == []
    # The app's deterministic steps are the ones being measured, and they were measured:
    assert row["checks"]["title_within_limit"]["ok"] is True
    assert row["checks"]["bullets_within_limit"]["ok"] is True
    assert row["checks"]["no_invented_numbers"]["ok"] is True
    assert row["checks"]["not_applied"]["ok"] is True
    artefact = Path(row["artefact"])
    assert artefact.is_file()
    assert json.loads(artefact.read_text(encoding="utf-8"))["result"]["data"]["applied"] is False


def test_a_prohibited_phrase_and_an_invented_number_are_both_caught(tmp_path):
    """The control: a proposal that breaks the app's own rules must not score 100."""
    brief = json.loads(json.dumps(svc.load_fixtures()["listing"][0]))
    proposed = brief["recorded_proposal"]
    proposed["title"] = "Best Seller Lions Mane Powder 500 mg"
    proposed["bullets"][0] = "GUARANTEED to dissolve, 500 mg of lion's mane per serving"
    row = svc.run_listing(brief, work_dir=tmp_path / "listing")
    assert row["passed"] is False
    assert "no_prohibited_phrase" in row["failed_checks"]
    # "500 mg" appears nowhere in the brief's facts, so it is an unsourced claim.
    assert "no_invented_numbers" in row["failed_checks"]
    assert "500 mg" in row["checks"]["no_invented_numbers"]["detail"]


def test_a_composer_that_returns_no_answer_is_a_named_refusal(tmp_path):
    brief = json.loads(json.dumps(svc.load_fixtures()["listing"][0]))
    brief["recorded_proposal"] = {}
    with pytest.raises(svc.ServiceRefused) as caught:
        svc.run_listing(brief, work_dir=tmp_path / "listing")
    assert "no model answer" in str(caught.value)


# ── ppc ─────────────────────────────────────────────────────────────────────

def test_the_ppc_path_ends_with_a_downloadable_bulk_file(tmp_path):
    brief = svc.load_fixtures()["ppc"][0]
    row = svc.run_ppc(brief, work_dir=tmp_path / "ppc")
    assert row["score"] == 100.0, json.dumps(row["checks"], indent=1)
    assert row["passed"] is True and row["failed_checks"] == []
    checks = row["checks"]
    assert checks["proposal_before_after"]["before"] == {"bid": "1.10"}
    assert checks["proposal_before_after"]["after"] == {"bid": "0.90"}
    assert checks["write_is_version_one"]["ok"] is True
    assert checks["second_write_is_a_new_file"]["version"] == 2
    assert checks["download_is_the_written_bytes"]["ok"] is True
    assert checks["original_untouched"]["ok"] is True
    bulk = Path(row["artefact"])
    assert bulk.is_file() and bulk.read_bytes()[:2] == b"PK"


def test_the_ppc_control_a_wrong_expected_bid_fails_the_check(tmp_path):
    brief = json.loads(json.dumps(svc.load_fixtures()["ppc"][0]))
    brief["expect"]["before_bid"] = "9.99"
    row = svc.run_ppc(brief, work_dir=tmp_path / "ppc")
    assert row["passed"] is False
    assert "proposal_before_after" in row["failed_checks"]


# ── golden goose ────────────────────────────────────────────────────────────

def test_a_golden_goose_scan_ranks_and_drops_the_reject_tier(tmp_path):
    brief = svc.load_fixtures()["golden_goose"][0]
    row = svc.run_golden_goose(brief, work_dir=tmp_path / "gg")
    assert row["score"] == 100.0, json.dumps(row["checks"], indent=1)
    assert row["row_count"] == 2, "the junk candidate must not be returned"
    assert row["checks"]["reject_tier_dropped"]["ok"] is True
    assert row["checks"]["economics_present"]["ok"] is True


def test_the_golden_goose_control_a_wrong_first_place_fails(tmp_path):
    brief = json.loads(json.dumps(svc.load_fixtures()["golden_goose"][0]))
    brief["expect"]["first_asin"] = "B0TEST0002"
    row = svc.run_golden_goose(brief, work_dir=tmp_path / "gg")
    assert row["passed"] is False
    assert "best_row_is_first" in row["failed_checks"]


# ── research ────────────────────────────────────────────────────────────────

def test_a_research_query_counts_sources_and_surfaces_the_conflict(tmp_path):
    brief = svc.load_fixtures()["research"][0]
    row = svc.run_research(brief, work_dir=tmp_path / "research")
    assert row["score"] == 100.0, json.dumps(row["checks"], indent=1)
    assert row["checks"]["sources_are_distinct"]["ok"] is True
    conflict = row["checks"]["numeric_conflict_surfaced"]
    assert conflict["ok"] is True
    values = json.dumps(conflict["conflicts"])
    assert "2.10" in values and "2.45" in values, "both figures must be in one conflict"
    assert row["checks"]["no_web_crawl_claimed"]["ok"] is True


def test_the_research_control_an_empty_corpus_is_no_evidence_not_an_answer(tmp_path):
    brief = json.loads(json.dumps(svc.load_fixtures()["research"][0]))
    brief["corpus"] = []
    row = svc.run_research(brief, work_dir=tmp_path / "research")
    assert row["passed"] is False
    assert "evidence_returned" in row["failed_checks"]
    assert "no passage" in row["checks"]["evidence_returned"]["detail"]


# ── the pass and the CLI ────────────────────────────────────────────────────

def test_the_pass_runs_only_the_paths_it_was_asked_for(tmp_path):
    summary = svc.run_pass(only="golden_goose", out_path=tmp_path / "proof.json",
                           work_dir=tmp_path / "work")
    assert summary["only"] == ["golden_goose"]
    assert summary["paths"]["golden_goose"]["measured"] is True
    assert summary["paths"]["ppc"]["measured"] is False
    assert summary["paths"]["ppc"]["scored"] == 0
    assert summary["scored"] == 1
    assert (tmp_path / "proof.json").is_file()


def test_every_existing_subcommand_still_parses():
    from tools.seller_tester.cli import build_parser

    parser = build_parser()
    for argv in (["catalog"], ["run", "--limit", "3"], ["escalate", "--brief", "ST-001"],
                 ["composite", "--limit", "1"], ["aplus", "--limit", "1"],
                 ["product", "--limit", "1", "--renderer", "drawn"],
                 ["packaging", "--limit", "1"], ["services", "--only", "research"]):
        assert parser.parse_args(argv).command == argv[0]
