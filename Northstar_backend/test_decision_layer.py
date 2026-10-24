"""Decision layer: typed, closed-label decisions with explicit abstention."""

from __future__ import annotations

import json

import pytest

import decision_layer as dl


def test_clean_copy_passes():
    got = dl.audit_copy("Mogul Organics turmeric powder, 16 oz resealable pouch, "
                        "sourced from small farms and ground fresh.")
    assert got["value"] == "pass"
    assert got["backend"] == "rules"
    assert got["confidence"] >= 0.6
    assert got["escalate"] is False


def test_prohibited_term_blocks():
    got = dl.audit_copy("Best seller turmeric, guaranteed results, act now")
    assert got["value"] == "block"
    assert got["confidence"] >= 0.9
    assert any(f.startswith("prohibited:") for f in got["flags"])
    assert got["escalate"] is False


def test_health_claim_goes_to_review_not_block():
    got = dl.audit_copy("This blend supports your immune system and helps detox the body")
    assert got["value"] == "review"
    assert any("health_claim" in f for f in got["flags"])


def test_unverified_certification_is_flagged():
    got = dl.audit_copy("Organic turmeric powder in a 16 ounce pouch for daily cooking")
    assert "review_certification_unverified" in got["flags"]


def test_short_text_abstains():
    got = dl.audit_copy("turmeric")
    assert got["abstained"] is True
    assert got["escalate"] is True
    assert got["value"] == "review"


def test_laya_backend_reports_why_it_fell_back(monkeypatch):
    monkeypatch.delenv("LAYA_ROOT", raising=False)
    got = dl.decide("copy_audit", "A perfectly ordinary product description of sixteen ounces.", backend="laya")
    assert got["backend"] == "rules"
    assert "laya_not_configured" in got["reason"]


def test_laya_root_present_is_detected(monkeypatch, tmp_path):
    monkeypatch.setenv("LAYA_ROOT", str(tmp_path))
    assert dl._laya_available() == (True, "laya_ready")


def test_unknown_kind_is_a_programming_error():
    with pytest.raises(ValueError):
        dl.decide("make_me_a_sandwich", "x")


def test_duplicate_abstains_without_a_model():
    got = dl.decide("duplicate", "two listings")
    assert got["value"] == "unsure"
    assert got["abstained"] is True


def test_labels_are_closed_sets():
    for kind, labels in dl.KINDS.items():
        got = dl.decide(kind, "a reasonable product description for testing purposes")
        assert got["value"] in labels
        assert 0.0 <= got["confidence"] <= 1.0


def test_listing_proposal_carries_a_copy_audit():
    from adapters.reasoning_provider import MockReasoningProvider
    from reasoning_tasks import listing_proposal

    provider = MockReasoningProvider(response_text=json.dumps({
        "sku": "SKU-9",
        "proposed": {"title": "Best seller turmeric", "bullets": ["b"] * 5,
                     "description": "d", "attributes": {}},
        "reasons": [], "missing_evidence": [], "warnings": [],
    }))
    out = listing_proposal(sku="SKU-9", title="old", bullets=["a"] * 5,
                           description="old", provider=provider)
    assert out["copy_audit"]["value"] == "block"
    assert "copy_audit" in out
    assert any("audit" in w.lower() for w in out["warnings"])


def test_ad_copy_carries_a_copy_audit():
    from adapters.reasoning_provider import MockReasoningProvider
    from reasoning_tasks import ad_copy_proposal

    provider = MockReasoningProvider(response_text=json.dumps({
        "headlines": ["Guaranteed results"], "body": "100% cure for everything",
        "cta": "Buy", "brand_tone": "plain", "unsupported_claims": [], "warnings": [],
    }))
    out = ad_copy_proposal({"sku": "SKU-9", "title": "x"}, provider=provider)
    assert out["copy_audit"]["value"] == "block"


# --- Jev alignment: declarative decisions + consumer matching ---------------

def test_every_kind_has_a_declared_decision_with_matching_criteria():
    for kind, labels in dl.KINDS.items():
        spec = dl.DECISIONS[kind]
        assert spec["type"] in ("choice", "boolean")
        assert set(spec["criteria"].keys()) == set(labels)


def test_distribution_is_complete_and_peaks_on_the_answer():
    got = dl.audit_copy("Best seller turmeric, guaranteed results")
    dist = got["probabilities"]
    labels = dl.KINDS["copy_audit"]
    assert set(dist) == set(labels)
    assert abs(sum(dist.values()) - 1.0) < 0.001
    assert dist["block"] == max(dist.values())


def test_consumer_match_with_no_conditions_skips_everything():
    got = dl.consumer_match({"kind": "copy_audit", "probabilities": {"pass": 0.9}})
    assert got["matched"] == [] and got["needs_review"] is False


def test_consumer_match_matches_the_full_distribution_not_just_top():
    out = {"kind": "copy_audit",
           "probabilities": {"pass": 0.05, "review": 0.95, "block": 0.0}}
    got = dl.consumer_match(out, {"review": 0.5})
    assert got["matched"] == ["review"]


def test_unknown_consumer_label_is_needs_review_never_a_silent_remap():
    out = {"kind": "copy_audit",
           "probabilities": {"pass": 0.9, "review": 0.05, "block": 0.05}}
    got = dl.consumer_match(out, {"approved": 0.5})   # invented label
    assert got["matched"] == [] and got["needs_review"] is True
    assert got["unknown_labels"] == ["approved"]


def test_blocker_escalation_interrupts_on_live_lane_language():
    got = dl.decide("blocker_escalation", "hard failure on the live lane, all batches blocked")
    assert got["value"] == "now" and got["escalate"] is False


def test_blocker_escalation_sends_ideas_to_backlog():
    got = dl.decide("blocker_escalation", "nice to have: reorder the reports directory")
    assert got["value"] == "never"


def test_blocker_escalation_defaults_to_batched_report():
    got = dl.decide("blocker_escalation",
                    "The listing import regex misses the new bullet separator character.")
    assert got["value"] == "later"


def test_respond_now_is_typed_boolean():
    got = dl.decide("respond_now", "@assistant what did the last batch promote?",
                    facts={"addressed_to_agent": True})
    assert got["value"] in dl.KINDS["respond_now"]
    assert got["kind"] == "respond_now"
    assert dl.decide("respond_now", "thinking out loud about pricing", facts={})["value"] == "no"
