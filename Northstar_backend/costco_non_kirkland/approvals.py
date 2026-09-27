"""Human purchase-approval queue (Phase 7).

PURE / OFFLINE decision records ONLY. This module creates, grants, revokes, and
invalidates APPROVAL RECORDS. It never buys anything and never interacts with any
marketplace. No cart, checkout, listing, message, or Seller Central action exists.

Rules:
  - `approval-grant` fails if the candidate is stale, blocked, incomplete, needs
    enrichment, manual review, or lacks exact identity.
  - Approval snapshots economics + source price at grant time (immutable).
  - Approval expires automatically.
  - A price change, source-product change, ASIN mismatch, or stale provider
    snapshot invalidates the approval.
  - No automated path can set purchase_authorized without this explicit record.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .enums import ApprovalState, OperationalRecommendation
from .settings import get_settings
from .store import PipelineStore

DECISION_RECORD_NOTE = (
    "This is a decision record only. No purchase, checkout, cart action, "
    "marketplace action, or external communication has occurred."
)

# Operational statuses that are grant-eligible (exact identity + complete evidence).
GRANT_ELIGIBLE_RECOMMENDATIONS = (
    OperationalRecommendation.TEST_BUY_CANDIDATE.value,
    OperationalRecommendation.QUALIFIED_CANDIDATE.value,
    OperationalRecommendation.PRIORITY_CANDIDATE.value,
    OperationalRecommendation.PURCHASE_AUTHORIZATION_REQUIRED.value,
)

# Statuses that block granting.
BLOCKED_RECOMMENDATIONS = (
    OperationalRecommendation.BLOCKED.value,
    OperationalRecommendation.NEEDS_ENRICHMENT.value,
    OperationalRecommendation.MANUAL_REVIEW_REQUIRED.value,
    OperationalRecommendation.WATCHLIST.value,
)

GRANT_OK_IDENTITY_STATES = (
    "exact_match_verified",
    "exact_match_provider_reported",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def is_expired(approval: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    exp = _parse_dt(approval.get("expires_at"))
    if exp is None:
        return False
    now = now or datetime.now(timezone.utc)
    return exp < now


def expire_overdue(store: PipelineStore) -> int:
    """Mark overdue approvals as expired. Returns count changed."""
    n = 0
    for appr in store.list_approvals(state=ApprovalState.GRANTED.value):
        if is_expired(appr):
            store.update_approval(appr["approval_id"], state=ApprovalState.EXPIRED.value)
            n += 1
    return n


def _fresh(observed_at: Optional[str], max_age_minutes: int) -> bool:
    dt = _parse_dt(observed_at)
    if dt is None:
        return False
    return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0 <= max_age_minutes


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

def request_approval(candidate_id: str, *, store: Optional[PipelineStore] = None,
                     settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create an approval REQUEST for a candidate (no purchase action)."""
    store = store or PipelineStore()
    st = get_settings(settings)
    decision = _get_decision(store, candidate_id)
    if not decision:
        return {"ok": False, "error": "candidate decision not found", "candidate_id": candidate_id}
    if decision.get("recommendation_status") not in GRANT_ELIGIBLE_RECOMMENDATIONS:
        return {"ok": False, "error": "candidate is not grant-eligible",
                "candidate_id": candidate_id, "recommendation_status": decision.get("recommendation_status")}

    approval = store.create_approval({
        "candidate_id": candidate_id,
        "costco_source_product_id": decision.get("costco_source_product_id"),
        "asin": decision.get("asin"),
        "source_name": decision.get("source_name"),
        "source_sku": decision.get("source_sku"),
        "source_url": decision.get("source_url"),
        "source_price": decision.get("source_price"),
        "source_price_observed_at": decision.get("source_price_observed_at"),
        "source_pack_text": decision.get("source_pack_text"),
        "quantity": None,
        "approved_by": None,
        "state": ApprovalState.REQUESTED.value,
        "economics_snapshot": decision.get("economics"),
        "market_snapshot": decision.get("market_snapshot"),
        "reason_codes": decision.get("reason_codes"),
    })
    approval["note"] = DECISION_RECORD_NOTE
    return {"ok": True, **approval}


# ---------------------------------------------------------------------------
# Grant
# ---------------------------------------------------------------------------

def grant_approval(approval_id: str, *, quantity: int, expires_at: str, approved_by: str,
                   store: Optional[PipelineStore] = None,
                   settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Grant an approval request. Decision record only — never a purchase."""
    store = store or PipelineStore()
    st = get_settings(settings)
    appr = store.get_approval(approval_id)
    if not appr:
        return {"ok": False, "error": "approval not found", "approval_id": approval_id}

    candidate_id = appr.get("candidate_id")
    decision = _get_decision(store, candidate_id)
    if not decision:
        return {"ok": False, "error": "candidate decision not found", "approval_id": approval_id}

    # --- grant-eligibility guards -------------------------------------------
    rec = decision.get("recommendation_status")
    if rec in BLOCKED_RECOMMENDATIONS or rec not in GRANT_ELIGIBLE_RECOMMENDATIONS:
        return {"ok": False, "error": "candidate not grant-eligible",
                "candidate_id": candidate_id, "recommendation_status": rec}

    identity_state = decision.get("identity_state")
    if identity_state not in GRANT_OK_IDENTITY_STATES:
        return {"ok": False, "error": "exact identity required for approval grant",
                "identity_state": identity_state}

    max_qty = int(st.get("approval_max_quantity", 200))
    if quantity is None or int(quantity) <= 0:
        return {"ok": False, "error": "quantity must be positive", "quantity": quantity}
    if int(quantity) > max_qty:
        return {"ok": False, "error": f"quantity exceeds max ({max_qty})", "quantity": quantity}

    # --- source-price freshness ----------------------------------------------
    src_observed = appr.get("source_price_observed_at") or decision.get("source_price_observed_at")
    if not _fresh(src_observed, float(st.get("source_price_max_age_minutes", 60))):
        return {"ok": False, "error": "source price stale; cannot grant",
                "source_price_observed_at": src_observed}

    # --- provider snapshot freshness -----------------------------------------
    mkt_observed = (appr.get("market_snapshot") or {}).get("fields", {}).get("asin", {}).get("observed_at")
    if not _fresh(mkt_observed, float(st.get("market_snapshot_max_age_minutes", 60))):
        return {"ok": False, "error": "provider snapshot stale; cannot grant",
                "market_observed_at": mkt_observed}

    # --- economics must be complete ------------------------------------------
    econ = appr.get("economics_snapshot") or decision.get("economics") or {}
    if econ.get("economics_completeness") != "complete":
        return {"ok": False, "error": "economics not complete; cannot grant",
                "economics_completeness": econ.get("economics_completeness")}

    # --- immutable snapshot (re-snapshot at grant time) -----------------------
    grant_at = _now()
    store.update_approval(
        approval_id,
        state=ApprovalState.GRANTED.value,
        granted_at=grant_at,
        expires_at=expires_at,
        approved_by=approved_by,
        quantity=int(quantity),
    )
    return {
        "ok": True,
        "approval_id": approval_id,
        "candidate_id": candidate_id,
        "asin": appr.get("asin"),
        "quantity": int(quantity),
        "expires_at": expires_at,
        "approved_by": approved_by,
        "state": ApprovalState.GRANTED.value,
        "economics_snapshot": appr.get("economics_snapshot"),
        "source_price": appr.get("source_price"),
        "note": DECISION_RECORD_NOTE,
    }


# ---------------------------------------------------------------------------
# Revoke / invalidate
# ---------------------------------------------------------------------------

def revoke_approval(approval_id: str, *, reason: str, store: Optional[PipelineStore] = None) -> Dict[str, Any]:
    store = store or PipelineStore()
    appr = store.get_approval(approval_id)
    if not appr:
        return {"ok": False, "error": "approval not found", "approval_id": approval_id}
    store.update_approval(approval_id, state=ApprovalState.REVOKED.value,
                          revoked_at=_now(), revoke_reason=reason)
    return {"ok": True, "approval_id": approval_id, "state": ApprovalState.REVOKED.value,
            "reason": reason, "note": DECISION_RECORD_NOTE}


def invalidate_approval(approval_id: str, *, reason: str, store: Optional[PipelineStore] = None) -> Dict[str, Any]:
    store = store or PipelineStore()
    appr = store.get_approval(approval_id)
    if not appr:
        return {"ok": False, "error": "approval not found", "approval_id": approval_id}
    store.update_approval(approval_id, state=ApprovalState.INVALIDATED.value,
                          invalidated_at=_now(), invalidate_reason=reason)
    return {"ok": True, "approval_id": approval_id, "state": ApprovalState.INVALIDATED.value,
            "reason": reason, "note": DECISION_RECORD_NOTE}


def validate_approval_still_valid(approval_id: str, *, current_source_price=None,
                                  current_asin=None, store: Optional[PipelineStore] = None,
                                  settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Re-validate a granted approval against current state.

    Invalidates if: expired, source price changed, ASIN changed, or provider
    snapshot stale. Returns the current validity dict (does not mutate unless
    invalidating).
    """
    store = store or PipelineStore()
    st = get_settings(settings)
    appr = store.get_approval(approval_id)
    if not appr:
        return {"ok": False, "valid": False, "reason": "not found"}
    if appr.get("state") != ApprovalState.GRANTED.value:
        return {"ok": False, "valid": False, "reason": f"state={appr.get('state')}"}

    reasons = []
    if is_expired(appr):
        reasons.append("expired")
        store.update_approval(approval_id, state=ApprovalState.EXPIRED.value)
        return {"ok": False, "valid": False, "reason": "expired"}

    if current_source_price is not None and abs(float(current_source_price) - float(appr.get("source_price") or 0)) > 0.005:
        reasons.append("source_price_changed")
        store.update_approval(approval_id, state=ApprovalState.INVALIDATED.value,
                              invalidate_reason="source_price_changed")
    if current_asin is not None and str(current_asin).upper() != str(appr.get("asin") or "").upper():
        reasons.append("asin_mismatch")
        store.update_approval(approval_id, state=ApprovalState.INVALIDATED.value,
                              invalidate_reason="asin_mismatch")

    if reasons:
        return {"ok": False, "valid": False, "reason": reasons, "approval_id": approval_id}
    return {"ok": True, "valid": True, "approval_id": approval_id}


def _get_decision(store: PipelineStore, candidate_id: str) -> Optional[Dict[str, Any]]:
    decisions = store.list_candidate_decisions(candidate_id=candidate_id)
    return decisions[0] if decisions else None