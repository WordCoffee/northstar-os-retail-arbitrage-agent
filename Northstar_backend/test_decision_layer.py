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
