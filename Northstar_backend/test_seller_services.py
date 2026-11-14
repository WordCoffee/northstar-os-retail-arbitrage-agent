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
        # Five is the sample floor: fewer briefs than MIN_SCORED means no service can be
        # scored from this path however good the answer is.
        assert len(payload[name]) >= 5, f"{name} carries only {len(payload[name])} brief(s)"
    ppc = payload["ppc"][0]
    assert ppc["rows"][0][0] == "Product" and len(ppc["rows"]) >= 5
    assert {c["asin"] for c in payload["golden_goose"][0]["candidates"]} >= {
        "B0TEST0001", "B0TEST0003"}
    assert payload["research"][0]["corpus"]


def test_every_brief_of_a_path_is_its_own_situation():
    """No near-duplicates: a brief that only renames a colour is the same brief."""
    payload = svc.load_fixtures()
    for name in svc.PATHS:
        ids = [brief.get("id") for brief in payload[name]]
        assert len(ids) == len(set(ids)), f"{name} repeats an id: {ids}"
        if name == "listing":
            skus = [brief.get("sku") for brief in payload[name]]
            assert len(skus) == len(set(skus)), f"listing repeats a sku: {skus}"
        if name == "research":
            queries = [brief.get("query") for brief in payload[name]]
            assert len(queries) == len(set(queries)), f"research repeats a query: {queries}"


def test_each_path_names_the_one_service_that_produces_it():
    """Attribution is declared in the fixture and must match the registry's own tools."""
    attribution = svc.load_attribution()
    registry = json.loads((Path(svc.ROOT) / "ty" / "services.json").read_text(encoding="utf-8"))
    services = {row["id"]: row for row in registry["services"]}
    retired = registry.get("aliases") or {}
    #: The declared tool a path actually exercises. Only the paths whose production
    #: code IS that tool are listed: `offer_copy` is judged by listing_optimizer and
    #: `social_caption` runs social_pulse.generate_caption, and neither is a Bojo
    #: tool — their `why` says so rather than borrowing a tool they do not run.
    tool = {"listing": "compose_listing", "golden_goose": "golden_goose_scan",
            "scan": "scan_products", "caption": "write_content"}
    assert set(attribution) == set(svc.PATHS), "every path must be attributed or declared unowned"
    for name in svc.PATHS:
        entry = attribution[name]
        owner = entry.get("service")
        if owner is None:
            assert entry.get("why"), f"{name} is unowned with no stated reason"
            continue
        assert owner in services, f"{name} names {owner}, which is not in the registry"
        if name in tool:
            assert tool[name] in (services[owner].get("tools") or []), (
                f"{name} is attributed to {owner}, which does not declare {tool[name]}")
        for alias in entry.get("aliases") or []:
            if alias in services:
                assert (services[alias].get("tools") or []) == (services[owner].get("tools") or []), (
                    f"{alias} does not declare the same tool as {owner}")
                continue
            # A retired id: it must be a DECLARED alias of the same service, and it
            # must still route somewhere (a seller's bookmark is not a 404).
            assert alias in retired, f"{name} declares {alias} as an alias, which nothing declares"
            assert retired[alias]["of"] == owner, f"{alias} points at {retired[alias]['of']}"
            assert retired[alias]["route"].startswith("/")



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


def test_a_draft_claim_that_survives_the_proposal_fails_the_check(tmp_path):
    """Control: the compliance brief is measured, not assumed."""
    brief = next(b for b in svc.load_fixtures()["listing"] if b.get("must_not_keep"))
    kept = json.loads(json.dumps(brief))
    kept["recorded_proposal"]["bullets"][0] = (
        "BEST SLEEP SUPPLEMENT: " + kept["recorded_proposal"]["bullets"][0])
    row = svc.run_listing(kept, work_dir=tmp_path / "listing")
    assert row["passed"] is False
    assert "draft_claims_removed" in row["failed_checks"]


def test_a_brief_whose_own_draft_lacks_the_claim_fails_rather_than_passing_empty(tmp_path):
    """A stale brief must not score a check that never looked at anything."""
    brief = json.loads(json.dumps(svc.load_fixtures()["listing"][0]))
    brief["must_not_keep"] = ["best sleep supplement"]
    row = svc.run_listing(brief, work_dir=tmp_path / "listing")
    assert "draft_claims_removed" in row["failed_checks"]
    assert "does not carry it" in row["checks"]["draft_claims_removed"]["detail"]



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


# ── scan (Product Finder) ────────────────────────────────────────────────────

def _scan_payload(rows, *, ok=True, source="cache", cache="fresh",
                  live_requested=False, reason=None):
    return {
        "ok": ok,
        "tool": "scan_products",
        "reason": reason,
        "data": {
            "query": "ceramic mug",
            "keywords": ["ceramic mug"],
            "match_all": True,
            "live_requested": live_requested,
            "source": source,
            "cache": {"cache_status": cache},
            "count": len(rows),
            "candidates": rows,
            "search_error": None,
            "note": "fixture",
        },
    }


def test_the_scan_path_scores_product_finders_own_tool_offline(tmp_path):
    summary = svc.run_pass(only="scan", out_path=tmp_path / "proof.json",
                           work_dir=tmp_path / "work")
    assert summary["paths"]["scan"]["scored"] == 5
    assert summary["paths"]["scan"]["passed"] == 5
    assert summary["paths"]["scan"]["mean_score"] == 100.0
    assert summary["paths"]["scan"]["service"] == "product-finder"
    assert "none" in summary["network"]
    # The refusal brief is a scored check, not a refusal of the pass.
    assert summary["refused"] == 0


def test_the_scan_control_each_check_can_fail(tmp_path, monkeypatch):
    """A green suite that cannot show a red check proves nothing. One control per check."""
    import bojo_tools.sourcing_extra as sx  # noqa: PLC0415

    base = json.loads(json.dumps(svc.load_fixtures()["scan"][0]))
    matched = base["candidates"][:2]
    stray = base["candidates"][2]

    def run(brief, payload):
        monkeypatch.setattr(sx, "scan_products", lambda **kwargs: payload)
        return svc.run_scan(brief, work_dir=tmp_path / "scan")

    row = run(base, _scan_payload(matched, ok=False, reason="boom"))
    assert "scan_returned_rows" in row["failed_checks"]

    row = run(base, _scan_payload(matched + [stray]))
    assert "every_candidate_matches_the_query" in row["failed_checks"]

    limited = json.loads(json.dumps(base))
    limited["limit"] = 1
    row = run(limited, _scan_payload(matched))
    assert "respects_limit" in row["failed_checks"]

    row = run(base, _scan_payload(matched, cache="stale"))
    assert "cache_provenance_reported" in row["failed_checks"]

    row = run(base, _scan_payload(matched, source="live", live_requested=True))
    assert "source_is_the_cache" in row["failed_checks"]

    invented = [dict(matched[0]), dict(matched[1])]
    invented[0]["margin"] = 12.5
    row = run(base, _scan_payload(invented))
    assert "no_invented_fields" in row["failed_checks"]
    assert "margin" in row["checks"]["no_invented_fields"]["detail"]

    row = run(base, _scan_payload(matched + [stray]))
    assert "declared_non_match_excluded" in row["failed_checks"]


def test_the_scan_refusal_must_be_named_and_report_its_cache(tmp_path, monkeypatch):
    import bojo_tools.sourcing_extra as sx  # noqa: PLC0415

    brief = next(b for b in svc.load_fixtures()["scan"] if b["expect"].get("refusal"))
    monkeypatch.setattr(
        sx, "scan_products",
        lambda **kwargs: {"ok": False, "tool": "scan_products",
                          "reason": "the scanner fell over"})
    row = svc.run_scan(brief, work_dir=tmp_path / "scan")
    assert row["passed"] is False
    assert "refusal_is_named" in row["failed_checks"]
    assert "refusal_reports_the_cache" in row["failed_checks"]


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


def test_sources_that_agree_must_not_be_reported_as_a_conflict(tmp_path):
    """The other direction of the same check: a brief whose sources agree."""
    brief = next(b for b in svc.load_fixtures()["research"]
                 if (b.get("expect") or {}).get("conflict_values") == [])
    row = svc.run_research(brief, work_dir=tmp_path / "research")
    assert row["checks"]["numeric_conflict_surfaced"]["ok"] is True
    assert row["checks"]["numeric_conflict_surfaced"]["declared"] == "sources agree"
    # ... and a disagreement planted in that same corpus must be caught, not averaged.
    contradicted = json.loads(json.dumps(brief))
    contradicted["corpus"][2]["text"] = (
        "The freight cost per pallet from Shenzhen is 520 dollars at the current rate. "
        "The freight cost per pallet includes port handling.")
    row = svc.run_research(contradicted, work_dir=tmp_path / "research")
    assert row["checks"]["numeric_conflict_surfaced"]["ok"] is False
    assert "declared to agree" in row["checks"]["numeric_conflict_surfaced"]["detail"]



# ── the pass and the CLI ────────────────────────────────────────────────────

def test_the_pass_runs_only_the_paths_it_was_asked_for(tmp_path):
    summary = svc.run_pass(only="golden_goose", out_path=tmp_path / "proof.json",
                           work_dir=tmp_path / "work")
    assert summary["only"] == ["golden_goose"]
    assert summary["paths"]["golden_goose"]["measured"] is True
    assert summary["paths"]["ppc"]["measured"] is False
    assert summary["paths"]["ppc"]["scored"] == 0
    assert summary["scored"] == len(svc.load_fixtures()["golden_goose"])
    assert (tmp_path / "proof.json").is_file()


def test_every_existing_subcommand_still_parses():
    from tools.seller_tester.cli import build_parser

    parser = build_parser()
    for argv in (["catalog"], ["run", "--limit", "3"], ["escalate", "--brief", "ST-001"],
                 ["composite", "--limit", "1"], ["aplus", "--limit", "1"],
                 ["product", "--limit", "1", "--renderer", "drawn"],
                 ["packaging", "--limit", "1"], ["services", "--only", "research"]):
        assert parser.parse_args(argv).command == argv[0]
