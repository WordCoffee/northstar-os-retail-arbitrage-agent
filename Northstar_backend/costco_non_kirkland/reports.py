"""Reports and exports (Phase 8).

PURE / OFFLINE. Builds ranked / qualified / review / blocked / audit exports
(CSV + JSON) with full provenance, reason codes, and approval status.

Default ranking export:
  - includes only test_buy_candidate, qualified_candidate, priority_candidate,
    purchase_authorization_required
  - excludes stale, incomplete, blocked, needs_enrichment, manual-review by default
  - --include-review adds manual review + needs enrichment
  - --include-blocked only for audits
  - --include-stale only for diagnostics (prominently labeled)
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .enums import (
    OperationalRecommendation,
    PURCHASE_AUTHORIZATION_NOT_AUTHORIZED,
)
from .store import PipelineStore

RANKED_DEFAULT_STATUSES = (
    OperationalRecommendation.TEST_BUY_CANDIDATE.value,
    OperationalRecommendation.QUALIFIED_CANDIDATE.value,
    OperationalRecommendation.PRIORITY_CANDIDATE.value,
    OperationalRecommendation.PURCHASE_AUTHORIZATION_REQUIRED.value,
)

REVIEW_STATUSES = (
    OperationalRecommendation.MANUAL_REVIEW_REQUIRED.value,
    OperationalRecommendation.NEEDS_ENRICHMENT.value,
)

BLOCKED_STATUSES = (OperationalRecommendation.BLOCKED.value,)

STALE_STATUSES = (OperationalRecommendation.WATCHLIST.value,)

REPORT_COLUMNS = (
    "candidate_id", "costco_source_product_id", "asin", "product_title", "source_name",
    "source_sku", "source_price", "source_price_observed_at", "source_freshness",
    "provider", "provider_export_filename", "provider_export_sha256",
    "market_snapshot_observed_at", "market_snapshot_freshness",
    "identity_state", "split_pack_state", "amazon_retail_active", "brand_owner_seller_active",
    "active_fba_sellers", "active_mfn_sellers", "buy_box_price", "referral_fee", "fba_fee",
    "shipping_weight_lb", "fba_size_tier", "sellability_status", "restriction_status",
    "risk_flags", "net_profit", "roi_pct", "margin_pct", "maximum_buy_cost", "mfn_score",
    "recommendation_status", "reason_codes", "approval_status", "last_updated",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision_row(decision: Dict[str, Any], approval_status: str = "none") -> Dict[str, Any]:
    econ = decision.get("economics") or {}
    mkt = decision.get("market_snapshot") or {}
    marketplace = mkt.get("marketplace", {})
    fees = mkt.get("fees", {})
    size = mkt.get("size", {})
    risk = mkt.get("risk", {})
    identity = mkt.get("identity", {})
    asin_meta = mkt.get("fields", {}).get("asin", {})
    return {
        "candidate_id": decision.get("candidate_id"),
        "costco_source_product_id": decision.get("costco_source_product_id"),
        "asin": decision.get("asin"),
        "product_title": identity.get("title") or decision.get("asin"),
        "source_name": decision.get("source_name"),
        "source_sku": decision.get("source_sku"),
        "source_price": decision.get("source_price"),
        "source_price_observed_at": decision.get("source_price_observed_at"),
        "source_freshness": "unknown",
        "provider": mkt.get("provider"),
        "provider_export_filename": asin_meta.get("provider_export_filename"),
        "provider_export_sha256": asin_meta.get("provider_export_sha256"),
        "market_snapshot_observed_at": asin_meta.get("observed_at"),
        "market_snapshot_freshness": asin_meta.get("freshness_status"),
        "identity_state": decision.get("identity_state"),
        "split_pack_state": decision.get("split_pack_state"),
        "amazon_retail_active": marketplace.get("amazon_retail_active"),
        "brand_owner_seller_active": marketplace.get("brand_owner_seller_active"),
        "active_fba_sellers": marketplace.get("active_fba_seller_count"),
        "active_mfn_sellers": marketplace.get("active_mfn_seller_count"),
        "buy_box_price": marketplace.get("buy_box_price"),
        "referral_fee": fees.get("referral_fee_amount"),
        "fba_fee": fees.get("fba_fulfillment_fee"),
        "shipping_weight_lb": size.get("shipping_weight_lb"),
        "fba_size_tier": size.get("fba_size_tier"),
        "sellability_status": risk.get("asin_sellability_status"),
        "restriction_status": (risk.get("category_restriction_status")
                               or risk.get("product_restriction_status")
                               or risk.get("brand_restriction_status")),
        "risk_flags": ",".join(decision.get("risk_flags") or []),
        "net_profit": econ.get("net_profit"),
        "roi_pct": econ.get("roi_percent"),
        "margin_pct": econ.get("net_margin_percent"),
        "maximum_buy_cost": econ.get("maximum_buy_cost"),
        "mfn_score": decision.get("mfn_score"),
        "recommendation_status": decision.get("recommendation_status"),
        "reason_codes": ",".join(decision.get("reason_codes") or []),
        "approval_status": approval_status,
        "last_updated": decision.get("updated_at") or _now(),
    }


def _approval_status_map(store: PipelineStore, decision_ids: List[str]) -> Dict[str, str]:
    out = {}
    approvals = store.list_approvals(limit=5000)
    for appr in approvals:
        cid = appr.get("candidate_id")
        if cid in decision_ids:
            out[cid] = appr.get("state", "none")
    for cid in decision_ids:
        out.setdefault(cid, "none")
    return out


def _select_decisions(decisions: List[Dict[str, Any]], *, include_review: bool,
                      include_blocked: bool, include_stale: bool,
                      statuses: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    sel = []
    for d in decisions:
        rec = d.get("recommendation_status")
        if statuses is not None:
            if rec in statuses:
                sel.append(d)
            continue
        if rec in RANKED_DEFAULT_STATUSES:
            sel.append(d)
        elif rec in REVIEW_STATUSES and include_review:
            sel.append(d)
        elif rec in BLOCKED_STATUSES and include_blocked:
            sel.append(d)
        elif rec in STALE_STATUSES and include_stale:
            d = dict(d)
            d["_labeled_stale"] = True
            sel.append(d)
    return sel


def build_ranked_report(decisions: List[Dict[str, Any]], *, include_review: bool = False,
                        include_blocked: bool = False, include_stale: bool = False,
                        statuses: Optional[List[str]] = None,
                        store: Optional[PipelineStore] = None) -> List[Dict[str, Any]]:
    """Build ranked report rows (defaults exclude review/blocked/stale)."""
    store = store or PipelineStore()
    selected = _select_decisions(decisions, include_review=include_review,
                                 include_blocked=include_blocked, include_stale=include_stale,
                                 statuses=statuses)
    ids = [d.get("candidate_id") for d in selected]
    approval_map = _approval_status_map(store, ids)
    rows = []
    for d in selected:
        row = _decision_row(d, approval_status=approval_map.get(d.get("candidate_id"), "none"))
        if d.get("_labeled_stale"):
            row["_labeled_stale"] = True
        rows.append(row)
    rows.sort(key=lambda r: (r.get("mfn_score") is None, -(r.get("mfn_score") or 0)))
    return rows


def to_csv(rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> str:
    cols = columns or REPORT_COLUMNS
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def to_json(rows: List[Dict[str, Any]]) -> str:
    return json.dumps(rows, indent=2, default=str)


# ---------------------------------------------------------------------------
# Plain-language decision report
# ---------------------------------------------------------------------------

def plain_language_decision(row: Dict[str, Any]) -> str:
    """Produce a human-readable decision report for one candidate."""
    r = row
    return (
        f"Candidate: {r.get('product_title') or r.get('candidate_id')}\n"
        f"Recommendation: {r.get('recommendation_status')}\n"
        f"Why:\n"
        f"- ASIN {r.get('asin')}; identity {r.get('identity_state')}; split {r.get('split_pack_state')}.\n"
        f"- Provider: {r.get('provider')} snapshot {r.get('provider_export_filename') or 'n/a'} "
        f"(observed {r.get('market_snapshot_observed_at') or 'unknown'}).\n"
        f"- Amazon Retail: {r.get('amazon_retail_active')}; brand seller: {r.get('brand_owner_seller_active')}; "
        f"FBA sellers: {r.get('active_fba_sellers')}; MFN sellers: {r.get('active_mfn_sellers')} (provider-reported).\n"
        f"- Buy Box / expected sale price: {r.get('buy_box_price')}.\n"
        f"- Fees: referral {r.get('referral_fee')}, FBA {r.get('fba_fee')}.\n"
        f"- Weight: {r.get('shipping_weight_lb')} lb; tier {r.get('fba_size_tier')}.\n"
        f"- Sellability: {r.get('sellability_status')}; restriction: {r.get('restriction_status')}.\n"
        f"- Net profit: {r.get('net_profit')}; ROI: {r.get('roi_pct')}%; margin: {r.get('margin_pct')}%; "
        f"max buy cost: {r.get('maximum_buy_cost')}.\n"
        f"- MFN opportunity score: {r.get('mfn_score')}.\n"
        f"- Reason codes: {r.get('reason_codes')}.\n"
        f"- Risk flags: {r.get('risk_flags') or 'none'}.\n"
        f"- Decision status: human approval required. {PURCHASE_AUTHORIZATION_NOT_AUTHORIZED}."
    )


# ---------------------------------------------------------------------------
# Export sets
# ---------------------------------------------------------------------------

def export_set(decisions: List[Dict[str, Any]], *, statuses: List[str],
               store: Optional[PipelineStore] = None) -> List[Dict[str, Any]]:
    """Export a specific set of statuses (e.g., qualified/test-buy/blocked)."""
    return build_ranked_report(decisions, statuses=statuses, store=store)


def provider_import_report(import_result: Dict[str, Any]) -> str:
    """Render a provider import report as JSON text."""
    return json.dumps(import_result, indent=2, default=str)


def identity_validation_report(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        "candidate_id": d.get("candidate_id"), "asin": d.get("asin"),
        "identity_state": d.get("identity_state"), "split_pack_state": d.get("split_pack_state"),
        "reason_codes": ",".join(d.get("reason_codes") or []),
    } for d in decisions]


def economics_report(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        "candidate_id": d.get("candidate_id"), "asin": d.get("asin"),
        "economics_completeness": (d.get("economics") or {}).get("economics_completeness"),
        "net_profit": (d.get("economics") or {}).get("net_profit"),
        "roi_pct": (d.get("economics") or {}).get("roi_percent"),
        "margin_pct": (d.get("economics") or {}).get("net_margin_percent"),
        "maximum_buy_cost": (d.get("economics") or {}).get("maximum_buy_cost"),
        "calculation_class": (d.get("economics") or {}).get("calculation_class"),
    } for d in decisions]


def approval_queue(store: Optional[PipelineStore] = None) -> List[Dict[str, Any]]:
    store = store or PipelineStore()
    return [a for a in store.list_approvals(limit=5000) if a.get("state") in ("requested", "granted")]


def approval_audit(store: Optional[PipelineStore] = None) -> List[Dict[str, Any]]:
    store = store or PipelineStore()
    return store.list_approvals(limit=5000)


def source_options_report(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        "candidate_id": d.get("candidate_id"), "asin": d.get("asin"),
        "source_name": d.get("source_name"), "source_sku": d.get("source_sku"),
        "source_price": d.get("source_price"), "source_price_observed_at": d.get("source_price_observed_at"),
        "source_pack_text": d.get("source_pack_text"), "source_url": d.get("source_url"),
    } for d in decisions]