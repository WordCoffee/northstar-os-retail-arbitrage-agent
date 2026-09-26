"""Batch C4 — Golden Goose decision controls (Phase 1C-03R)."""
from __future__ import annotations

from Northstar_backend.foundation.golden_goose_decision import (
    decide, PASS, FAIL, UNKNOWN, SCORER_VERSION, PURCHASE_READY, APPROVAL_REQUIRED,
    RESEARCH_REQUIRED, BLOCKED_ECONOMICS, BLOCKED_ELIGIBILITY, BLOCKED_DOCUMENTATION,
    BLOCKED_PACK_IDENTITY,
)

ALL_PASS = {
    "product_identity": PASS, "variation_identity": PASS, "pack_identity": PASS,
    "economics_complete": PASS, "cost_known": PASS, "fees_known": PASS,
    "eligibility": PASS, "sourcing_route": PASS, "documentation": PASS,
}
APPROVED = {"present": True, "expired": False, "revoked": False, "applicable": True,
            "state": "granted"}
ECON = "COMPLETE_VERIFIED"


def test_complete_without_approval_is_approval_required():
    r = decide(gate_inputs=ALL_PASS, economics_readiness=ECON, approval=None)
    assert r["decision_state"] == APPROVAL_REQUIRED
    assert r["purchase_ready"] is False
    assert r["scorer_version"] == SCORER_VERSION


def test_complete_with_approval_is_purchase_ready():
    r = decide(gate_inputs=ALL_PASS, economics_readiness=ECON, approval=APPROVED)
    assert r["decision_state"] == PURCHASE_READY
    assert r["purchase_ready"] is True


def test_expired_approval_blocks():
    r = decide(gate_inputs=ALL_PASS, economics_readiness=ECON,
               approval={**APPROVED, "expired": True})
    assert r["purchase_ready"] is False


def test_revoked_approval_blocks():
    r = decide(gate_inputs=ALL_PASS, economics_readiness=ECON,
               approval={**APPROVED, "revoked": True})
    assert r["purchase_ready"] is False


def test_cost_missing_blocks_economics():
    gates = {**ALL_PASS, "cost_known": FAIL, "economics_complete": FAIL}
    r = decide(gate_inputs=gates, economics_readiness="ACQUISITION_COST_MISSING",
               approval=APPROVED)
    assert r["decision_state"] == BLOCKED_ECONOMICS
    assert r["purchase_ready"] is False


def test_pack_unknown_is_research_required():
    gates = {**ALL_PASS, "pack_identity": UNKNOWN}
    r = decide(gate_inputs=gates, economics_readiness=ECON, approval=APPROVED)
    assert r["decision_state"] == RESEARCH_REQUIRED


def test_pack_fail_blocks_pack():
    gates = {**ALL_PASS, "pack_identity": FAIL}
    r = decide(gate_inputs=gates, economics_readiness=ECON, approval=APPROVED)
    assert r["decision_state"] == BLOCKED_PACK_IDENTITY


def test_confirmed_ineligible_blocks_and_approval_cannot_override():
    gates = {**ALL_PASS, "eligibility": FAIL}
    r = decide(gate_inputs=gates, economics_readiness=ECON, approval=APPROVED)
    assert r["decision_state"] == BLOCKED_ELIGIBILITY
    assert r["purchase_ready"] is False


def test_documentation_rejected_blocks():
    gates = {**ALL_PASS, "documentation": FAIL}
    r = decide(gate_inputs=gates, economics_readiness=ECON, approval=APPROVED)
    assert r["decision_state"] == BLOCKED_DOCUMENTATION


def test_missing_gates_default_to_unknown_not_pass():
    r = decide(gate_inputs={}, economics_readiness=ECON, approval=APPROVED)
    # nothing supplied -> all gates UNKNOWN -> research required, never purchase-ready
    assert all(v == UNKNOWN for v in r["mandatory_gates"].values())
    assert r["purchase_ready"] is False


def test_score_alone_cannot_create_purchase_ready():
    r = decide(gate_inputs={}, economics_readiness=ECON, approval=APPROVED,
               component_scores={"economics": 1.0, "demand": 1.0},
               component_weights={"economics": 0.5, "demand": 0.5})
    assert r["overall_score"] == 1.0
    assert r["purchase_ready"] is False  # gates unknown


def test_uncertainty_penalty_is_separate():
    r = decide(gate_inputs=ALL_PASS, economics_readiness=ECON, approval=APPROVED,
               component_scores={"economics": 1.0}, component_weights={"economics": 1.0},
               uncertainty_penalty=0.25, uncertainty_reasons=["seller count unknown"])
    assert r["overall_score"] == 0.75
    assert r["uncertainty_penalty"] == 0.25
    assert "seller count unknown" in r["uncertainty_reasons"]


def test_economics_formula_version_propagates():
    r = decide(gate_inputs=ALL_PASS, economics_readiness=ECON,
               economics_formula_version="economics-1.0.0", approval=APPROVED)
    assert r["economics_formula_version"] == "economics-1.0.0"


def test_legacy_qualified_is_review_not_purchase():
    r = decide(gate_inputs={**ALL_PASS, "documentation": UNKNOWN},
               economics_readiness=ECON, approval=None)
    assert r.get("qualified") is True or r["qualified"] is False
    assert r["purchase_ready"] is False  # legacy qualified never implies purchase auth


def test_component_availability_and_missing_information():
    r = decide(gate_inputs=ALL_PASS, economics_readiness=ECON, approval=APPROVED,
               component_availability={"economics": True, "demand": False})
    assert r["component_availability"]["demand"] is False
    assert "demand" in r["missing_information"]