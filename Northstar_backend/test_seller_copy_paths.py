"""The three copy paths: OfferChisel, The Town Crier and SocialPulse, scored.

A scorer is only an instrument if it can fail. Every check that can go wrong in
production has a control here that makes it fail on purpose: a promotional title, a
fifth bullet, a brand-voice violation, a disease claim, too many hashtags, an answer
the room cannot parse. Without those, a green run would only prove the checks were
never asked a hard question.

Everything runs offline: `social_caption` is the app's own template fallback (the
local model is refused on purpose), and the other two judge recorded engine answers.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.seller_tester import copy as copy_paths
from tools.seller_tester import services as svc


# ── the fixtures and the ownership statement ────────────────────────────────


def test_all_three_copy_paths_carry_at_least_five_briefs():
    payload = svc.load_fixtures()
    for name in copy_paths.PATHS:
        assert payload[name], f"{name} has no fixture"
        assert len(payload[name]) >= 5, (
            f"{name} carries {len(payload[name])} brief(s); seller_scores.MIN_SCORED is 5")


def test_the_module_paths_and_the_fixture_paths_are_the_same_set():
    assert set(copy_paths.PATHS) == set(copy_paths.RUNNERS) == set(copy_paths.OWNERS)
    assert set(copy_paths.PATHS) <= set(svc.PATHS)
    assert set(copy_paths.RUNNERS) <= set(svc.RUNNERS)


def test_each_copy_path_is_owned_by_the_service_whose_product_it_is():
    attribution = svc.load_attribution()
    for path, owner in copy_paths.OWNERS.items():
        assert attribution[path]["service"] == owner, path
        assert len(attribution[path]["why"]) > 80, f"{path} must say why it is owned"


def test_a_scored_copy_brief_never_carries_a_model_call():
    payload = svc.load_fixtures()
    for name in ("offer_copy", "caption"):
        for brief in payload[name]:
            assert brief.get("recorded_answer"), f"{name}/{brief['id']} has no recorded answer"
            assert "provider" not in brief, f"{name}/{brief['id']} must not name a live provider"
    for brief in payload["social_caption"]:
        assert brief.get("product"), f"social_caption/{brief['id']} has no product"


# ── offerchisel ─────────────────────────────────────────────────────────────


def test_the_clean_offerchisel_briefs_score_100(tmp_path):
    payload = svc.load_fixtures()["offer_copy"]
    for brief in payload:
        row = copy_paths.run_offer_copy(brief, work_dir=tmp_path / "offer")
        if brief["id"] in ("OC-002", "OC-004"):
            continue  # the two deliberate defects, asserted below
        assert row["score"] == 100.0, (brief["id"], row["checks"])
        assert row["passed"] is True


def test_a_disease_claim_in_the_draft_is_caught_by_the_claims_lint(tmp_path):
    brief = next(b for b in svc.load_fixtures()["offer_copy"] if b["id"] == "OC-002")
    row = copy_paths.run_offer_copy(brief, work_dir=tmp_path / "offer")
    assert row["passed"] is False
    assert "no_disease_or_treatment_claim" in row["failed_checks"]
    assert "immune support" in row["checks"]["no_disease_or_treatment_claim"]["detail"]


def test_a_fifth_bullet_fails_the_room_s_own_shape(tmp_path):
    brief = next(b for b in svc.load_fixtures()["offer_copy"] if b["id"] == "OC-004")
    row = copy_paths.run_offer_copy(brief, work_dir=tmp_path / "offer")
    assert row["passed"] is False
    assert "exactly_four_bullets" in row["failed_checks"]
    assert row["checks"]["exactly_four_bullets"]["detail"].startswith("5 bullet")


def test_a_promotional_title_and_a_missing_keyword_both_fail(tmp_path):
    """The app's own rubric, not ours: audit_title and keyword_coverage decide."""
    brief = json.loads(json.dumps(svc.load_fixtures()["offer_copy"][0]))
    brief["recorded_answer"] = brief["recorded_answer"].replace(
        "TITLE: Word Coffee", "TITLE: Best Seller Word Coffee")
    brief["keywords"] = list(brief["keywords"]) + ["never written anywhere"]
    row = copy_paths.run_offer_copy(brief, work_dir=tmp_path / "offer")
    assert row["passed"] is False
    assert "title_audit_clean" in row["failed_checks"]
    assert "keyword_coverage_complete" in row["failed_checks"]
    assert "promotional claim" in row["checks"]["title_audit_clean"]["detail"]


def test_a_backend_line_over_the_byte_limit_fails(tmp_path):
    brief = json.loads(json.dumps(svc.load_fixtures()["offer_copy"][0]))
    brief["recorded_answer"] = brief["recorded_answer"].replace(
        "KEYWORDS: ", "KEYWORDS: " + ", ".join(["long tail search term"] * 20) + ", ")
    row = copy_paths.run_offer_copy(brief, work_dir=tmp_path / "offer")
    assert row["passed"] is False
    assert "backend_within_250_bytes" in row["failed_checks"]


def test_an_answer_without_sections_is_a_named_refusal(tmp_path):
    brief = json.loads(json.dumps(svc.load_fixtures()["offer_copy"][0]))
    brief["recorded_answer"] = "Sure! Here are some thoughts about your product."
    with pytest.raises(copy_paths.CopyRefused) as caught:
        copy_paths.run_offer_copy(brief, work_dir=tmp_path / "offer")
    assert "TITLE:" in str(caught.value)


# ── towncrier ───────────────────────────────────────────────────────────────


def test_the_clean_towncrier_briefs_score_100(tmp_path):
    for brief in svc.load_fixtures()["caption"]:
        row = copy_paths.run_caption(brief, work_dir=tmp_path / "caption")
        if brief["id"] in ("TC-002", "TC-003", "TC-004"):
            continue  # the three deliberate defects, asserted below
        assert row["score"] == 100.0, (brief["id"], row["checks"])


def test_the_brand_voice_rule_is_enforced(tmp_path):
    """'Word Coffee is NOT a beverage' is the room's own rule (TownCrier.jsx:19)."""
    brief = next(b for b in svc.load_fixtures()["caption"] if b["id"] == "TC-002")
    row = copy_paths.run_caption(brief, work_dir=tmp_path / "caption")
    assert row["passed"] is False
    assert "brand_rule_respected" in row["failed_checks"]
    assert "coffee beans" in row["checks"]["brand_rule_respected"]["detail"]


def test_five_hashtags_fail_the_three_to_four_rule(tmp_path):
    brief = next(b for b in svc.load_fixtures()["caption"] if b["id"] == "TC-003")
    row = copy_paths.run_caption(brief, work_dir=tmp_path / "caption")
    assert row["passed"] is False
    assert "hashtags_3_to_4" in row["failed_checks"]
    assert row["checks"]["hashtags_3_to_4"]["hashtags"] == 5


def test_a_treatment_claim_in_a_caption_is_caught(tmp_path):
    brief = next(b for b in svc.load_fixtures()["caption"] if b["id"] == "TC-004")
    row = copy_paths.run_caption(brief, work_dir=tmp_path / "caption")
    assert row["passed"] is False
    assert "no_disease_or_treatment_claim" in row["failed_checks"]
    assert "treats" in row["checks"]["no_disease_or_treatment_claim"]["detail"]


def test_a_caption_over_the_platform_limit_fails(tmp_path):
    brief = json.loads(json.dumps(svc.load_fixtures()["caption"][0]))
    brief["recorded_answer"] = ("A" * 300) + "\n#One #Two #Three"
    row = copy_paths.run_caption(brief, work_dir=tmp_path / "caption")
    assert row["passed"] is False
    assert "caption_within_platform_limit" in row["failed_checks"]


# ── socialpulse (real app code, not a fixture) ──────────────────────────────


def test_socialpulse_runs_the_apps_own_caption_pipeline(tmp_path):
    brief = svc.load_fixtures()["social_caption"][0]
    row = copy_paths.run_social_caption(brief, work_dir=tmp_path / "social")
    assert row["score"] == 100.0, row["checks"]
    artefact = json.loads(Path(row["artefact"]).read_text(encoding="utf-8"))
    result = artefact["result"]
    # The caption came from social_pulse's template fallback, and the app's own
    # score came with it: that is the difference between this path and a fixture.
    assert result["platform_spec"]["max_caption_length"] == 2200
    assert result["caption"].startswith("Quality you can trust.")
    assert isinstance(result["score"], int) and 0 <= result["score"] <= 100
    assert result["cta"]


def test_the_twitter_hashtag_cap_defect_is_measured_not_waived(tmp_path):
    """A real defect, kept: the pipeline honours the voice count, not the platform cap.

    `social_pulse._generate_hashtags` returns `hashtags_per_post` tags and never checks
    `platform_spec["max_hashtags"]` (twitter: 3). The check fails on the app's output;
    that is the instrument working on the product that exists.
    """
    brief = next(b for b in svc.load_fixtures()["social_caption"] if b["platform"] == "twitter")
    row = copy_paths.run_social_caption(brief, work_dir=tmp_path / "social")
    assert row["passed"] is False
    assert "hashtags_within_platform_cap" in row["failed_checks"]
    assert row["checks"]["hashtags_within_platform_cap"]["cap"] == 3
    assert row["checks"]["hashtags_within_platform_cap"]["hashtags"] > 3


def test_a_claim_pasted_into_the_product_title_is_caught(tmp_path):
    brief = json.loads(json.dumps(svc.load_fixtures()["social_caption"][0]))
    brief["product"]["title"] = "Harbor Body Oil that treats dry skin"
    brief["facts"] = []
    row = copy_paths.run_social_caption(brief, work_dir=tmp_path / "social")
    assert row["passed"] is False
    assert "no_disease_or_treatment_claim" in row["failed_checks"]


# ── the pass ────────────────────────────────────────────────────────────────


def test_the_three_paths_score_five_outputs_each_through_the_pass(tmp_path):
    summary = svc.run_pass(only="offer_copy,caption,social_caption",
                           out_path=tmp_path / "proof.json", work_dir=tmp_path / "work")
    for name, owner in copy_paths.OWNERS.items():
        row = summary["paths"][name]
        assert row["service"] == owner
        assert row["scored"] == 5, (name, row)
        assert row["refused"] == 0
        assert 0 < row["mean_score"] < 100, (
            f"{name} scored {row['mean_score']}: a sample where every brief passes proves "
            "the checks cannot fail")
