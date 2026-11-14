"""Seller-Tester output scores feed the scorecard (owner instruction 2026-11-08)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import seller_scores  # noqa: E402


BRIEFS = {"briefs": [
    {"id": "ST-001", "category": "supplement_pouch"},
    {"id": "ST-002", "category": "mug", "service": "listings"},
]}


def summary(rows):
    return {"generated_at": "2026-11-08T00:00:00+00:00", "scored": len(rows),
            "passed": sum(1 for row in rows if row.get("passed")), "results": rows}


def test_a_brief_without_a_service_belongs_to_design_studio():
    mapping = seller_scores.brief_services(BRIEFS)
    assert mapping["ST-001"] == "design-studio"
    assert mapping["ST-002"] == "listings"


def test_scores_are_averaged_per_service():
    data = summary([
        {"brief_id": "ST-001", "score": 20, "passed": False},
        {"brief_id": "ST-001", "score": 40, "passed": True},
        {"brief_id": "ST-002", "score": 90, "passed": True},
    ])
    built = seller_scores.build(summary=data, briefs=BRIEFS)
    assert built["services"]["design-studio"]["mean"] == 30.0
    assert built["services"]["design-studio"]["scored"] == 2
    assert built["services"]["listings"]["mean"] == 90.0


def test_a_service_without_output_scores_zero_with_a_reason():
    verdict = seller_scores.score_for("hub", data={"services": {}})
    assert verdict["score"] == 0.0
    assert "no Seller-Tester output" in verdict["evidence"]


def test_a_thin_sample_is_not_a_score():
    data = {"services": {"design-studio": {"mean": 95.0, "scored": 2, "passed": 2}}}
    verdict = seller_scores.score_for("design-studio", data=data)
    assert verdict["score"] == 0.0
    assert "only 2" in verdict["evidence"]


def test_a_full_sample_is_the_measured_mean():
    data = {"services": {"design-studio": {"mean": 41.5, "scored": 30, "passed": 3}}}
    verdict = seller_scores.score_for("design-studio", data=data)
    assert verdict["score"] == 41.5
    assert "30 Seller-Tester outputs" in verdict["evidence"]


def test_a_rebuild_keeps_adpilots_ad_copy_row():
    """Measured 2026-11-13: a `--write` rebuild dropped the 98.1 row it had not produced."""
    proof = {"mean": 98.1, "scored": 6, "passed": 5, "at": "2026-11-13T10:11:42+00:00"}
    built = seller_scores.build(ad_copy=proof)
    row = built["services"]["adpilot"]
    assert row["mean"] == 98.1
    assert row["scored"] == 6 and row["passed"] == 5
    assert row["path"] == "ad_copy"
    assert row["population"] == "service-path"
    # It is not a generated row, so it cannot enter the generated totals.
    generated = [r for r in built["services"].values() if r.get("population") == "generated"]
    if "pass" in built:
        assert built["pass"]["scored"] == sum(r["scored"] for r in generated)


def test_a_service_path_row_in_the_services_block_is_labelled_as_such():
    # adpilot's ad_copy score lives in the services block but is a service-path row.
    # The evidence must name the population the row declares, not call it a picture.
    data = {"services": {"adpilot": {
        "mean": 98.1, "scored": 6, "passed": 5,
        "population": "service-path", "path": "ad_copy",
    }}}
    verdict = seller_scores.score_for("adpilot", data=data)
    assert verdict["score"] == 98.1
    assert "service-path" in verdict["evidence"]
    assert "ad_copy" in verdict["evidence"]
    assert "generated/composite" not in verdict["evidence"]


def test_no_pass_on_disk_is_an_empty_result_not_a_crash():
    built = seller_scores.build(summary=None, briefs=BRIEFS)
    # None means "read from disk"; with no file the build reports the reason
    assert isinstance(built, dict)
    assert "services" in built


def test_the_live_file_matches_the_registry_shape():
    data = seller_scores._read(seller_scores.OUT)
    if not data:
        pytest.skip("no seller_scores.json in this checkout")
    assert "services" in data
    for service, row in data["services"].items():
        assert isinstance(service, str)
        assert 0.0 <= float(row["mean"]) <= 100.0
        assert int(row["scored"]) >= 1


# --------------------------------------------------------------- populations
def test_replayed_artefacts_are_context_and_never_the_published_mean():
    replay = {"generated_at": "2026-11-01T00:00:00+00:00", "generator": "stored",
              "results": [
                  {"brief_id": "ST-001", "score": 10, "passed": False},
                  {"brief_id": "ST-001", "score": 20, "passed": False},
    ]}
    made = {"generated_at": "2026-11-09T00:00:00+00:00", "generator": "composite", "results": [
        {"brief_id": "ST-001", "score": 90, "passed": True},
        {"brief_id": "ST-001", "score": 70, "passed": True},
        {"brief_id": "ST-001", "score": 80, "passed": True},
        {"brief_id": "ST-001", "score": 100, "passed": True},
        {"brief_id": "ST-001", "score": 60, "passed": False},
    ]}
    built = seller_scores.build(summary=replay, composite=made, briefs=BRIEFS)
    row = built["services"]["design-studio"]
    assert row["mean"] == 80.0          # generated only: (90+70+80+100+60)/5
    assert row["scored"] == 5
    assert row["replay"] == {"mean": 15.0, "scored": 2, "passed": 0}
    assert row["at"] == "2026-11-09T00:00:00+00:00"  # the pass that made the pictures
    assert built["pass"]["mean_score"] == 80.0
    assert built["pass"]["replay"]["mean_score"] == 15.0
    verdict = seller_scores.score_for("design-studio", data=built)
    assert verdict["score"] == 80.0
    assert "2 replayed artefact(s) excluded as context" in verdict["evidence"]


def test_a_row_population_marker_beats_the_summary_generator():
    row = {"brief_id": "ST-001", "score": 50, "population": "replay"}
    assert seller_scores.population_of(row, "composite") == "replay"
    made = {"brief_id": "ST-001", "score": 50,
            "generation": {"route": "composite"}}
    assert seller_scores.population_of(made, "stored") == "generated"


def test_many_replays_do_not_satisfy_the_generated_sample_floor():
    replay = {"generator": "stored", "results": [
        {"brief_id": "ST-001", "score": 30, "passed": False} for _ in range(40)]}
    made = {"generator": "composite", "results": [
        {"brief_id": "ST-001", "score": 100, "passed": True} for _ in range(3)]}
    built = seller_scores.build(summary=replay, composite=made, briefs=BRIEFS)
    verdict = seller_scores.score_for("design-studio", data=built)
    assert verdict["score"] == 0.0
    assert "only 3 generated/composite output(s)" in verdict["evidence"]
    assert "40 replayed artefact(s) are context only" in verdict["evidence"]


# --------------------------------------------------------------- the app path
def _app_pass(rows=None):
    return {"generated_at": "2026-11-11T00:00:00+00:00", "generator": "product_pipeline",
            "pipeline": "app", "plate_source": "drawn", "judge_enabled": True,
            "results": rows if rows is not None else [
                {"brief_id": "ST-001", "score": 100, "passed": True,
                 "generation": {"route": "product_picture"}},
                {"brief_id": "ST-001", "score": 90, "passed": True,
                 "generation": {"route": "product_picture"}},
                {"brief_id": "ST-001", "score": 80, "passed": True,
                 "generation": {"route": "product_picture"}},
                {"brief_id": "ST-001", "score": 95, "passed": True,
                 "generation": {"route": "product_picture"}},
                {"brief_id": "ST-001", "score": 85, "passed": True,
                 "generation": {"route": "product_picture"}},
            ]}


def test_the_app_path_pass_is_the_published_population():
    replay = {"generator": "stored", "results": [
        {"brief_id": "ST-001", "score": 10, "passed": False}]}
    harness = {"generator": "composite", "results": [
        {"brief_id": "ST-001", "score": 60, "passed": False} for _ in range(5)]}
    built = seller_scores.build(summary=replay, composite=harness,
                               product=_app_pass(), briefs=BRIEFS)
    row = built["services"]["design-studio"]
    assert row["mean"] == 90.0          # (100+90+80+95+85)/5, app path only
    assert row["scored"] == 5
    assert built["pipeline"]["same_pipeline"] is True
    assert built["pipeline"]["plate_source"] == "drawn"
    assert built["pipeline"]["judged"] is True
    assert "product_picture.build" in built["pipeline"]["rendered_by"]


def test_the_harness_pass_is_not_averaged_beside_the_app_pass():
    """Two pipelines over the same briefs are two pipelines, not one population."""
    harness = {"generator": "composite", "results": [
        {"brief_id": "ST-001", "score": 0, "passed": False} for _ in range(5)]}
    built = seller_scores.build(summary={"generator": "stored", "results": []},
                               composite=harness, product=_app_pass(), briefs=BRIEFS)
    assert built["services"]["design-studio"]["mean"] == 90.0
    assert built["pass"]["scored"] == 5


def test_without_an_app_pass_the_pipeline_is_named_as_the_harness():
    harness = {"generator": "composite", "results": [
        {"brief_id": "ST-001", "score": 50, "passed": False} for _ in range(5)]}
    built = seller_scores.build(summary={"generator": "stored", "results": []},
                               composite=harness, briefs=BRIEFS)
    assert built["pipeline"]["same_pipeline"] is False
    assert "harness pipeline" in built["pipeline"]["why_it_matters"]


# --------------------------------------------------------------- ceiling
def test_ceiling_counts_what_can_actually_be_judged():
    briefs = {"briefs": [
        {"id": "P-1", "source_mode": "prompt_only"},
        {"id": "R-1", "source_mode": "stored_reference",
         "reference": {"kind": "stored_asset", "path": "renders/smoke_main_2000.png"}},
        {"id": "R-2", "source_mode": "stored_reference",
         "reference": {"kind": "stored_asset", "path": "renders/does_not_exist.png"}},
        {"id": "U-1", "source_mode": "uploaded_reference",
         "reference": {"kind": "uploaded_file", "path": None,
                       "descriptor": {"filename": "x.jpg", "mime_type": "image/jpeg",
                                      "subject": "a mug"}}},
    ]}
    result = seller_scores.ceiling(briefs=briefs, generated_scored=1)
    assert result["briefs"] == 4
    assert result["reference_resolvable"] == 1
    assert result["resolvable_brief_ids"] == ["R-1"]
    assert result["prompt_only"] == 1
    assert result["unresolved_reference"] == 2
    assert result["coverage_of_catalog_pct"] == 25.0
    assert result["catalog_mean_if_every_scoreable_brief_passes"] == 25.0
    assert result["ceiling_generated_mean_if_all_scoreable_pass"] == 100.0


def test_the_live_catalog_ceiling_is_measured_not_guessed():
    """56 briefs: 12 stored references on disk, 32 prompt-only, 12 uploads with no copy."""
    result = seller_scores.ceiling()
    assert result["briefs"] == 56
    assert result["reference_resolvable"] == 12
    assert result["prompt_only"] == 32
    assert result["unresolved_by_mode"] == {"uploaded_reference": 12}
    assert result["coverage_of_catalog_pct"] == 21.4
    assert result["catalog_mean_if_every_scoreable_brief_passes"] == 21.4


def test_the_published_score_is_the_generated_population_of_the_live_passes():
    data = seller_scores._read(seller_scores.OUT) or {}
    row = (data.get("services") or {}).get("design-studio") or {}
    if not row:
        pytest.skip("no live seller_scores.json in this checkout")
    assert row.get("population") == "generated"
    assert "replay" in row
    assert data.get("pass", {}).get("population") == "generated"
    assert "replay" in (data.get("pass") or {})


# ------------------------------------------------------------- service paths
ATTRIBUTION = {
    "listing": {"service": "listingforge", "why": "compose_listing"},
    "golden_goose": {"service": "goldengoose", "aliases": ["golden-goose"], "why": "scan"},
    "research": {"service": None, "why": "no service calls research_graph"},
}


def _path_row(path, brief, score, passed=True):
    return {"path": path, "brief_id": brief, "status": "scored",
            "score": score, "passed": passed}


def _proof(rows):
    return {"generated_at": "2026-11-11T00:00:00+00:00",
            "command": "python -m tools.seller_tester services", "results": rows}


def _path_pass(rows=None):
    return _proof(rows if rows is not None else [
        _path_row("listing", f"LST-00{i}", 100.0, True) for i in range(1, 6)
    ])


def test_the_service_path_pass_is_bucketed_per_service_in_its_own_population():
    rows = [_path_row("listing", f"LST-00{i}", 100.0) for i in range(1, 6)]
    rows.append(_path_row("research", "RES-001", 100.0))
    block = seller_scores.service_path(_proof(rows), ATTRIBUTION)
    assert block["population"] == "service-path"
    listing = block["services"]["listingforge"]
    assert listing["scored"] == 5
    assert listing["mean"] == 100.0
    assert listing["paths"] == ["listing"]
    assert listing["population"] == "service-path"
    assert "research" in block["unattributed"]
    assert "listingforge" not in block["unattributed"]


def test_a_service_path_score_needs_the_same_sample_floor():
    rows = [_path_row("listing", f"LST-00{i}", 100.0) for i in range(1, 5)]  # four
    built = {"services": {},
             "service_path": seller_scores.service_path(_proof(rows), ATTRIBUTION)}
    verdict = seller_scores.score_for("listingforge", data=built)
    assert verdict["score"] == 0.0
    assert "only 4 service-path output(s)" in verdict["evidence"]


def test_a_full_service_path_sample_is_the_measured_mean_and_names_its_population():
    rows = [_path_row("listing", f"LST-00{i}", 100.0) for i in range(1, 5)]
    rows.append(_path_row("listing", "LST-005", 50.0, False))
    built = {"services": {},
             "service_path": seller_scores.service_path(_proof(rows), ATTRIBUTION)}
    verdict = seller_scores.score_for("listingforge", data=built)
    assert verdict["score"] == 90.0
    assert "5 Seller-Tester service-path outputs" in verdict["evidence"]
    assert "population: service-path" in verdict["evidence"]
    assert "4 passed" in verdict["evidence"]


def test_a_picture_sample_and_a_service_path_sample_are_never_added_up():
    """3 pictures + 3 listing briefs is two populations of three, so nothing is scored."""
    built = {"services": {"design-studio": {"mean": 90.0, "scored": 3, "passed": 3}},
             "service_path": seller_scores.service_path(
                 _proof([_path_row("listing", f"LST-00{i}", 100.0) for i in range(1, 4)]),
                 ATTRIBUTION)}
    # The picture service keeps its own (thin) sample and is not topped up by the path.
    verdict = seller_scores.score_for("design-studio", data=built)
    assert verdict["score"] == 0.0
    assert "only 3 generated/composite output(s)" in verdict["evidence"]
    # ... and the listing service is not lifted by the pictures either.
    listing = built["service_path"]["services"]["listingforge"]
    assert listing["scored"] == 3


def test_the_image_population_wins_when_it_is_the_services_own_output():
    built = {"services": {"design-studio": {"mean": 96.2, "scored": 32, "passed": 32}},
             "service_path": {"population": "service-path", "aliases": {}, "paths": {},
                              "services": {"design-studio": {
                                  "population": "service-path", "mean": 88.0,
                                  "scored": 5, "passed": 5, "paths": ["ppc"]}}}}
    verdict = seller_scores.score_for("design-studio", data=built)
    assert verdict["score"] == 96.2
    assert "5 service-path output(s) (mean 88.0) are a separate population" in verdict["evidence"]


def test_a_declared_alias_reads_the_same_bucket_and_says_so():
    built = {"services": {},
             "service_path": seller_scores.service_path(_path_pass(), ATTRIBUTION)}
    alias = seller_scores.score_for("golden-goose", data=built)
    real = seller_scores.score_for("goldengoose", data=built)
    assert alias["score"] == real["score"]
    assert "declared alias of 'goldengoose'" in alias["evidence"]
    assert "alias" not in real["evidence"]


def test_a_refused_path_is_recorded_and_is_not_a_sample():
    rows = [_path_row("listing", f"LST-00{i}", 100.0) for i in range(1, 5)]
    rows.append({"path": "ppc", "brief_id": "PPC-005", "status": "refused",
                 "score": 0.0, "passed": False, "reason": "write refused 422"})
    block = seller_scores.service_path(_proof(rows), ATTRIBUTION)
    assert block["refused"] == [{"path": "ppc", "brief_id": "PPC-005",
                                 "reason": "write refused 422"}]
    assert "ppc" not in block["services"].get("listingforge", {}).get("paths", [])
    assert "design-studio" not in block["services"]


def test_an_unowned_path_lends_its_sample_to_no_service():
    rows = [_path_row("research", f"RES-00{i}", 100.0) for i in range(1, 6)]
    block = seller_scores.service_path(_proof(rows), ATTRIBUTION)
    assert block["services"] == {}
    assert block["unattributed"] == ["research"]
    assert block["paths"]["research"]["scored"] == 5
    assert "no service calls research_graph" in block["paths"]["research"]["why_unattributed"]


def test_build_is_hermetic_when_a_caller_supplies_its_own_rows():
    """An injected pass must not pick up this machine's service-path proof."""
    built = seller_scores.build(summary={"generator": "stored", "results": []},
                                briefs=BRIEFS)
    assert built["service_path"]["services"] == {}
    assert "no service-path pass on disk" in built["service_path"]["reason"]


def test_the_live_service_path_block_matches_its_proof_file():
    data = seller_scores._read(seller_scores.OUT) or {}
    block = data.get("service_path") or {}
    if not block.get("services") and not block.get("paths"):
        pytest.skip("no service-path pass on disk in this checkout")
    assert block["population"] == "service-path"
    for service, row in block["services"].items():
        assert row["population"] == "service-path"
        assert 0.0 <= float(row["mean"]) <= 100.0
        assert int(row["scored"]) >= 1
        assert block["paths"][row["paths"][0]]["scored"] >= int(row["scored"])

