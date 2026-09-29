"""Golden Goose decision controls (Phase 1C-03R Batch C4).

A versioned ranking/decision POLICY layer — NOT an economics engine. It consumes
canonical economics readiness + explicit compliance signals and decides an
opportunity's review/purchase state. A numeric score can never authorize
purchasing; mandatory gates and explicit approval control readiness.

Unknown stays distinct from zero; uncertainty is a separately labeled penalty.
No provider calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

SCORER_VERSION = "golden-goose-score-1.0.0"

# Gate values
PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "NOT_APPLICABLE"

# decision states
DISCOVERED = "DISCOVERED"
INCOMPLETE = "INCOMPLETE"
RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
ECONOMICS_COMPLETE = "ECONOMICS_COMPLETE"
QUALIFIED_FOR_REVIEW = "QUALIFIED_FOR_REVIEW"
BLOCKED_ECONOMICS = "BLOCKED_ECONOMICS"
BLOCKED_PACK_IDENTITY = "BLOCKED_PACK_IDENTITY"
BLOCKED_PRODUCT_IDENTITY = "BLOCKED_PRODUCT_IDENTITY"
BLOCKED_VARIATION_IDENTITY = "BLOCKED_VARIATION_IDENTITY"
BLOCKED_ELIGIBILITY = "BLOCKED_ELIGIBILITY"
BLOCKED_SOURCING = "BLOCKED_SOURCING"
BLOCKED_DOCUMENTATION = "BLOCKED_DOCUMENTATION"
BLOCKED_BRAND_PERMISSION = "BLOCKED_BRAND_PERMISSION"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
PURCHASE_READY = "PURCHASE_READY"

# Requirement level per gate: True = mandatory for purchase-readiness.
MANDATORY_GATES = {
    "product_identity": True,
    "variation_identity": True,
    "pack_identity": True,
    "economics_complete": True,
    "cost_known": True,
    "fees_known": True,
    "eligibility": True,
    "sourcing_route": True,
    "documentation": True,
    "brand_permission": False,  # only when applicable
}

_GATE_FAIL_STATE = {
    "product_identity": BLOCKED_PRODUCT_IDENTITY,
    "variation_identity": BLOCKED_VARIATION_IDENTITY,
    "pack_identity": BLOCKED_PACK_IDENTITY,
    "economics_complete": BLOCKED_ECONOMICS,
    "cost_known": BLOCKED_ECONOMICS,
    "fees_known": BLOCKED_ECONOMICS,
    "eligibility": BLOCKED_ELIGIBILITY,
    "sourcing_route": BLOCKED_SOURCING,
    "documentation": BLOCKED_DOCUMENTATION,
    "brand_permission": BLOCKED_BRAND_PERMISSION,
}


@dataclass
class GateResult:
    values: dict = field(default_factory=dict)
    mandatory: dict = field(default_factory=lambda: dict(MANDATORY_GATES))


def evaluate_gates(values: dict) -> dict:
    """Fill missing gates with UNKNOWN (never assumed PASS)."""
    out = {}
    for name in MANDATORY_GATES:
        v = (values or {}).get(name, UNKNOWN)
        out[name] = v if v in (PASS, FAIL, UNKNOWN, NOT_APPLICABLE) else UNKNOWN
    return out


def _approval_valid(approval: Optional[dict]) -> bool:
    if not approval:
        return False
    return bool(approval.get("present")) and not approval.get("expired") \
        and not approval.get("revoked") and bool(approval.get("applicable", True))


def decide(*, gate_inputs: Optional[dict] = None,
           economics_readiness: Optional[str] = None,
           economics_formula_version: Optional[str] = None,
           component_scores: Optional[dict] = None,
           component_availability: Optional[dict] = None,
           component_weights: Optional[dict] = None,
           uncertainty_penalty: float = 0.0,
           uncertainty_reasons: Optional[list] = None,
           approval: Optional[dict] = None,
           warnings: Optional[list] = None,
           sample: bool = False) -> dict:
    """Produce the structured, versioned decision-control output.

    A numeric score never sets PURCHASE_READY; mandatory gates + approval do."""
    gates = evaluate_gates(gate_inputs or {})
    w = warnings or []
    warns = list(w)

    econ_complete = (economics_readiness or "").startswith("COMPLETE")

    # FAIL dominates
    for name, mandatory in MANDATORY_GATES.items():
        if gates[name] == FAIL and mandatory:
            return _out(gates, _GATE_FAIL_STATE.get(name, BLOCKED_ECONOMICS),
                        econ_complete, economics_formula_version, component_scores,
                        component_availability, component_weights, uncertainty_penalty,
                        uncertainty_reasons, approval, warns, False)

    # economics must be complete for financial qualification
    if not econ_complete:
        return _out(gates, BLOCKED_ECONOMICS, False, economics_formula_version,
                    component_scores, component_availability, component_weights,
                    uncertainty_penalty, uncertainty_reasons, approval, warns, False)

    # required gates must be satisfied (no UNKNOWN among mandatory)
    unresolved = [n for n, m in MANDATORY_GATES.items()
                  if m and gates[n] in (UNKNOWN, NOT_APPLICABLE)]
    if unresolved:
        return _out(gates, RESEARCH_REQUIRED, True, economics_formula_version,
                    component_scores, component_availability, component_weights,
                    uncertainty_penalty, uncertainty_reasons, approval, warns, False)

    # all mandatory gates PASS + economics complete -> need approval
    if not _approval_valid(approval):
        return _out(gates, APPROVAL_REQUIRED, True, economics_formula_version,
                    component_scores, component_availability, component_weights,
                    uncertainty_penalty, uncertainty_reasons, approval, warns, False)

    if sample:
        # A labeled SAMPLE row can NEVER be promoted to PURCHASE_READY (P3-T4).
        return _out(gates, APPROVAL_REQUIRED, True, economics_formula_version,
                    component_scores, component_availability, component_weights,
                    uncertainty_penalty, uncertainty_reasons, approval, warns, False)

    return _out(gates, PURCHASE_READY, True, economics_formula_version,
                component_scores, component_availability, component_weights,
                uncertainty_penalty, uncertainty_reasons, approval, warns, True)


def _out(gates, state, econ_complete, econ_ver, comp_scores, comp_avail, comp_weights,
         unc_penalty, unc_reasons, approval, warns, purchase_ready):
    overall = None
    if comp_scores and comp_weights:
        total_w = sum(comp_weights.values()) or 1.0
        overall = round(sum(comp_scores.get(k, 0.0) * comp_weights.get(k, 0.0)
                            for k in comp_weights) / total_w - unc_penalty, 4)
    return {
        "scorer_version": SCORER_VERSION,
        "economics_formula_version": econ_ver,
        "overall_score": overall,
        "overall_confidence": None if not comp_avail else
            round(sum(1 for v in comp_avail.values() if v) / max(1, len(comp_avail)), 4),
        "decision_state": state,
        "component_scores": comp_scores or {},
        "component_availability": comp_avail or {},
        "component_weights": comp_weights or {},
        "mandatory_gates": gates,
        "uncertainty_penalty": unc_penalty,
        "uncertainty_reasons": unc_reasons or [],
        "missing_information": [k for k, v in (comp_avail or {}).items() if not v],
        "warnings": warns,
        "approval_required": state == APPROVAL_REQUIRED,
        "approval_state": (approval or {}).get("state", "none"),
        "purchase_ready": bool(purchase_ready),
        # legacy compatibility (deprecated): qualified-for-review, never purchase auth
        "qualified": state in (QUALIFIED_FOR_REVIEW, ECONOMICS_COMPLETE, APPROVAL_REQUIRED,
                               PURCHASE_READY),
    }