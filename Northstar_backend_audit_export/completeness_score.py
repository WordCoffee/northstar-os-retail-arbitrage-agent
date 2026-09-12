"""ASIN Data Completeness Score (0-100) + decision status taxonomy.

PURE / OFFLINE ONLY — no network, no file IO, no writes, no provider
imports. Canonical completeness logic for
docs/asin-market-data-completeness-plan.md (Phase 3) and the scanner
completeness contract (docs/completeness-ui-implementation-report.md).

NULL-FIRST SEMANTICS (never 0 for missing):
  - A category score is null (never 0) when that category has NO evaluated
    input — no field that could earn or disprove points. If any evaluated
    input exists, the category computes a real number, which may
    legitimately be 0 points when the evidence disproves it.
  - score = sum of computable-category points; score_max = sum of the maxes
    of computable categories (100 only when all six are computable).
    score is null when zero categories are computable.
  - status is "not_computable" when score is null (computed, impossible);
    an absent completeness block in a response is "unknown" (UI level).
  - A genuine 0 is allowed only when all computable categories earn 0 from
    evaluated evidence.

Honesty rules (mirrors the rest of Northstar):
  - Missing inputs score nothing and are never fabricated from price/title/
    seller counts.
  - Partial seller-offer coverage caps the market category at 10/20.
  - Provisional fees (FBA fee excluded) cap the fees category at 8/20.
  - The score is a prioritization signal; the STATUS is the decision gate.
  - `ready_for_test_buy` is unreachable without BOTH all data gates AND
    explicit account/sourcing review approval (scanner rows never carry
    approval, so scanner rows can reach at most "blocked
    (requires_account_review)").
  - `purchase_authorized` mirrors product_analysis rules, never weakened.
"""

from typing import Any, Dict, List, Optional, Tuple

CATEGORY_WEIGHTS = {
    "identity_mapping": 15,
    "source_cost": 15,
    "market_coverage": 20,
    "fees_economics": 20,
    "demand": 15,
    "invoice_readiness": 15,
}
TOTAL_MAX = 100

STATUSES = (
    "not_computable",
    "unknown",
    "discovery_only",
    "blocked",
    "needs_mapping",
    "needs_market_data",
    "needs_fee_verification",
    "needs_demand_data",
    "needs_invoice_confirmation",
    "ready_for_test_buy",
)

PACK_MATCH_OK = ("exact", "invoice_confirmed")
INVOICE_COST_STATUSES = ("business_center_invoice_confirmed", "distributor_invoice_confirmed")

PARTIAL_COVERAGE_MARKET_CAP = 10
PROVISIONAL_FEES_CAP = 8

# Fields that, if present, make each category computable (for
# missing_inputs reporting).
CATEGORY_INPUTS = {
    "identity_mapping": ("name", "pack_match"),
    "source_cost": ("costco_cost", "costco_cost_basis"),
    "market_coverage": (
        "amazon_price",
        "buy_box_available",
        "buy_box_price",
        "offers_present",
        "coverage_full",
        "seller_counts_observed",
    ),
    "fees_economics": (
        "referral_fee",
        "fba_fee",
        "fba_fee_status",
        "economics_confidence",
        "net_profit",
        "roi_pct",
    ),
    "demand": ("est_monthly_sales", "sales_method"),
    "invoice_readiness": ("costco_cost_basis",),
}


def _normalize_cost_basis(basis: Optional[str]) -> Optional[str]:
    """Map any cost-basis vocabulary to: invoice | online | estimated |
    unavailable | None (absent). None means the row carries no basis at
    all (category not computable)."""
    if basis is None:
        return None
    b = str(basis).lower()
    if b in INVOICE_COST_STATUSES or b == "invoice_confirmed":
        return "invoice"
    if b in ("costco_online", "costco_online_discovery"):
        return "online"
    if b == "estimated":
        return "estimated"
    return "unavailable"


def _evidence_from_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    facts = snapshot.get("facts") or {}
    identity = facts.get("identity") or {}
    cost = facts.get("cost") or {}
    market = facts.get("market") or {}
    fees = facts.get("fees") or {}
    demand = facts.get("demand") or {}
    economics = facts.get("economics") or {}
    buy_box = market.get("buy_box") or {}
    coverage = market.get("coverage") or {}
    counts = market.get("seller_counts") or {}
    offers = market.get("offers")

    offers_present: Optional[bool] = None
    if isinstance(offers, list):
        offers_present = bool(offers)

    coverage_full: Optional[bool] = None
    cov_status = coverage.get("offers_complete_status")
    if cov_status == "full":
        coverage_full = True
    elif cov_status in ("partial", "unknown"):
        coverage_full = False

    counts_observed: Optional[bool] = None
    if "total_observed" in counts and "fba_observed" in counts:
        counts_observed = counts.get("total_observed") is not None and counts.get("fba_observed") is not None

    return {
        "name": identity.get("name"),
        "pack_match": identity.get("pack_match"),
        "amazon_price": market.get("amazon_price"),
        "buy_box_available": buy_box.get("available") if isinstance(buy_box.get("available"), bool) else None,
        "buy_box_price": buy_box.get("price"),
        "offers_present": offers_present,
        "coverage_full": coverage_full,
        "seller_counts_observed": counts_observed,
        "costco_cost": cost.get("costco_cost"),
        "costco_cost_basis": _normalize_cost_basis(cost.get("cost_status")),
        "referral_fee": fees.get("referral_fee"),
        "fba_fee": fees.get("fba_fee"),
        "fba_fee_status": fees.get("fba_fee_status"),
        "economics_confidence": economics.get("economics_confidence"),
        "net_profit": economics.get("net_profit"),
        "roi_pct": economics.get("roi_pct"),
        "est_monthly_sales": demand.get("estimated_monthly_sales"),
        "sales_method": demand.get("sales_estimation_method"),
    }


def _evidence_from_scanner_row(row: Dict[str, Any]) -> Dict[str, Any]:
    offers_returned = row.get("offers_returned")
    offers_complete = row.get("offers_complete")
    offers_present: Optional[bool] = None
    if isinstance(offers_returned, (int, float)) and not isinstance(offers_returned, bool):
        offers_present = offers_returned > 0
    coverage_full: Optional[bool] = None
    if isinstance(offers_complete, bool):
        coverage_full = offers_complete

    observed_total = row.get("observed_total_sellers")
    observed_fba = row.get("observed_fba_sellers")
    counts_observed: Optional[bool] = None
    if observed_total is not None or observed_fba is not None:
        counts_observed = observed_total is not None and observed_fba is not None

    return {
        "name": row.get("name"),
        "pack_match": row.get("pack_match"),
        "amazon_price": row.get("amazon_price"),
        "buy_box_available": row.get("observed_buy_box_available")
        if isinstance(row.get("observed_buy_box_available"), bool)
        else None,
        "buy_box_price": row.get("observed_buy_box_price")
        if row.get("observed_buy_box_price") is not None
        else row.get("buy_box_price"),
        "offers_present": offers_present,
        "coverage_full": coverage_full,
        "seller_counts_observed": counts_observed,
        "costco_cost": row.get("costco_cost") if row.get("costco_cost") is not None else row.get("costco_cogs"),
        "costco_cost_basis": _normalize_cost_basis(row.get("costco_cost_basis")),
        "referral_fee": row.get("referral_fee"),
        "fba_fee": row.get("fba_fee"),
        "fba_fee_status": row.get("fba_fee_status"),
        "economics_confidence": row.get("economics_confidence"),
        "net_profit": row.get("net_profit"),
        "roi_pct": row.get("roi_pct"),
        "est_monthly_sales": row.get("monthly_sales_estimate")
        if row.get("monthly_sales_estimate") is not None
        else row.get("estimated_monthly_sales"),
        "sales_method": row.get("sales_estimation_method"),
    }


def _compute_categories(evidence: Dict[str, Any]) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
    """Score every category that has evaluated input; null categories are
    omitted from the result (callers report them as null)."""
    scores: Dict[str, int] = {}
    reasons: Dict[str, List[str]] = {}

    # --- identity / mapping (15) ---
    if evidence.get("name") is not None or evidence.get("pack_match") is not None:
        pts = 0
        r: List[str] = []
        if isinstance(evidence.get("name"), str) and evidence["name"]:
            pts += 5
        pack = evidence.get("pack_match")
        if pack in PACK_MATCH_OK:
            pts += 10
        elif pack == "candidate":
            pts += 3
            r.append("pack_match is candidate; verification required")
        elif pack == "mismatch":
            r.append("pack_match is mismatch; product is not equivalent")
        elif pack is None:
            r.append("pack_match unknown; mapping verification required")
        scores["identity_mapping"] = pts
        reasons["identity_mapping"] = r

    # --- source cost (15) ---
    if evidence.get("costco_cost") is not None or evidence.get("costco_cost_basis") is not None:
        pts = 0
        r = []
        if evidence.get("costco_cost") is not None:
            pts += 10
        basis = evidence.get("costco_cost_basis")
        if basis == "invoice":
            pts += 5
        elif basis == "online":
            pts += 3
        elif basis == "estimated":
            pts += 2
        elif basis is not None:
            r.append("cost basis not invoice/online; treat as estimated only")
        scores["source_cost"] = pts
        reasons["source_cost"] = r

    # --- market / offer coverage (20) ---
    market_anchors = [
        evidence.get(k) is not None
        for k in ("amazon_price", "buy_box_available", "buy_box_price", "offers_present", "coverage_full", "seller_counts_observed")
    ]
    if any(market_anchors):
        pts = 0
        r = []
        if evidence.get("amazon_price") is not None:
            pts += 4
        else:
            r.append("no amazon_price")
        if evidence.get("buy_box_available") is True and evidence.get("buy_box_price") is not None:
            pts += 4
        elif evidence.get("buy_box_available") is False:
            r.append("buy box unavailable per provider")
        else:
            r.append("no buy box price")
        if evidence.get("offers_present") is True:
            pts += 4
        elif evidence.get("offers_present") is False:
            r.append("explicit zero-offer evidence")
        else:
            r.append("no observed offer list")
        if evidence.get("coverage_full") is True:
            pts += 4
            if evidence.get("seller_counts_observed") is True:
                pts += 4
            elif evidence.get("seller_counts_observed") is False:
                r.append("seller counts incomplete")
            else:
                r.append("seller counts unknown")
        else:
            if evidence.get("coverage_full") is False:
                r.append("seller-offer coverage not full")
            else:
                r.append("offer coverage unknown")
        if evidence.get("coverage_full") is False:
            pts = min(pts, PARTIAL_COVERAGE_MARKET_CAP)
        scores["market_coverage"] = pts
        reasons["market_coverage"] = r

    # --- fees / economics (20) ---
    fee_anchors = [
        evidence.get(k) is not None
        for k in ("referral_fee", "fba_fee", "fba_fee_status", "economics_confidence", "net_profit", "roi_pct")
    ]
    if any(fee_anchors):
        pts = 0
        r = []
        if evidence.get("referral_fee") is not None:
            pts += 4
        else:
            r.append("no referral fee")
        fba_status = evidence.get("fba_fee_status")
        if evidence.get("fba_fee") is not None:
            if fba_status == "verified_seller_central":
                pts += 6
            elif fba_status == "estimated":
                pts += 4
            elif fba_status == "provisional":
                pts += 2
            else:
                pts += 1
        else:
            r.append("no FBA fee")
        confidence = evidence.get("economics_confidence")
        if confidence == "estimated":
            pts += 6
        elif confidence == "provisional":
            pts += 3
            r.append("economics provisional; FBA fee excluded, verify before purchasing")
        elif confidence == "unavailable":
            r.append("economics unavailable; net/ROI null")
        if evidence.get("net_profit") is not None and evidence.get("roi_pct") is not None:
            pts += 4
        else:
            r.append("no net/ROI")
        if fba_status == "provisional":
            pts = min(pts, PROVISIONAL_FEES_CAP)
        scores["fees_economics"] = pts
        reasons["fees_economics"] = r

    # --- demand (15) ---
    if evidence.get("est_monthly_sales") is not None or evidence.get("sales_method") is not None:
        pts = 0
        r = []
        if evidence.get("est_monthly_sales") is not None:
            pts += 9
            method = evidence.get("sales_method")
            if method == "provider_verified":
                pts += 6
            elif method == "internal_estimate":
                pts += 3
            else:
                r.append("demand estimation method unknown; treat as low confidence")
        else:
            r.append("no monthly sales estimate; never fabricated")
        scores["demand"] = pts
        reasons["demand"] = r

    # --- invoice / procurement readiness (15) ---
    if evidence.get("costco_cost_basis") is not None:
        pts = 0
        r = []
        basis = evidence.get("costco_cost_basis")
        if basis == "invoice":
            pts += 15
        elif basis == "online":
            pts += 5
            r.append("discovery-only cost; Business Center invoice required to authorize")
        elif basis == "estimated":
            pts += 2
            r.append("estimated cost; invoice required to authorize")
        else:
            r.append("no cost basis")
        scores["invoice_readiness"] = pts
        reasons["invoice_readiness"] = r

    return scores, reasons


def _classify_status(evidence: Dict[str, Any], computable: List[str], account_review_approved: bool) -> Tuple[str, str]:
    if not computable:
        return "not_computable", "no evaluated inputs; completeness cannot be computed"

    pack_match = evidence.get("pack_match")
    if pack_match == "mismatch":
        return "blocked", "pack_match is mismatch; product equivalence disproven"

    if pack_match not in PACK_MATCH_OK:
        return "needs_mapping", "pack/variant fingerprint must be exact or invoice-confirmed"

    if evidence.get("amazon_price") is None or evidence.get("offers_present") is not True:
        return "needs_market_data", "amazon price or seller-offer roster missing"

    fba_status = evidence.get("fba_fee_status")
    if fba_status not in ("verified_seller_central", "estimated"):
        return "needs_fee_verification", "FBA fee must be verified or estimated; provisional is not enough"

    if evidence.get("est_monthly_sales") is None:
        return "needs_demand_data", "no monthly demand estimate"

    if evidence.get("costco_cost_basis") != "invoice":
        return "needs_invoice_confirmation", "cost must be invoice-confirmed before any purchase authorization"

    if not account_review_approved:
        return "blocked", "requires_account_review: all data gates pass, explicit approval outstanding"

    if evidence.get("economics_confidence") != "estimated":
        return "blocked", "economics not estimated-tier; verify fees and re-run analysis"

    return "ready_for_test_buy", "all data gates pass and account/sourcing review approved"


def _next_action(status: str, status_reason: str) -> str:
    if status == "not_computable":
        return "Collect scanner market data to compute completeness"
    if status == "blocked":
        if "mismatch" in status_reason:
            return "Skip: product equivalence disproven"
        if "requires_account_review" in status_reason:
            return "Account/sourcing review pending"
        return "Verify economics tier and re-run analysis"
    if status == "needs_mapping":
        return "Verify pack/variant equivalence (pack_match)"
    if status == "needs_market_data":
        return "Load seller details / refresh market data"
    if status == "needs_fee_verification":
        return "Verify FBA fee in Seller Central"
    if status == "needs_demand_data":
        return "Add monthly demand estimate"
    if status == "needs_invoice_confirmation":
        return "Confirm Costco invoice (invoices import)"
    return "Eligible for test buy after review"


def _roi_readiness(evidence: Dict[str, Any]) -> Dict[str, Any]:
    confidence = evidence.get("economics_confidence")
    has_net = evidence.get("net_profit") is not None and evidence.get("roi_pct") is not None
    if confidence is None and not has_net:
        return {"ready": None, "reason": None}
    if confidence == "estimated" and has_net:
        return {"ready": True, "reason": "net/ROI computed on estimated fee stack"}
    if confidence == "provisional":
        return {"ready": False, "reason": "FBA fee excluded; verify fees before purchasing"}
    if confidence == "unavailable":
        return {"ready": False, "reason": "economics unavailable; net/ROI null"}
    if has_net:
        return {"ready": True, "reason": "net/ROI present but confidence tier not estimated"}
    return {"ready": False, "reason": "net/ROI not computable from available fields"}


def _completeness_result(
    evidence: Dict[str, Any],
    scores: Dict[str, int],
    reasons: Dict[str, List[str]],
    account_review_approved: bool,
) -> Dict[str, Any]:
    computable = list(scores.keys())
    score_max = sum(CATEGORY_WEIGHTS[c] for c in computable)
    score: Optional[int] = sum(scores.values()) if computable else None
    status, status_reason = _classify_status(evidence, computable, account_review_approved)

    category_scores = {cat: (scores.get(cat) if cat in scores else None) for cat in CATEGORY_WEIGHTS}
    category_reasons = {cat: reasons.get(cat, []) for cat in CATEGORY_WEIGHTS}

    missing_inputs = {
        cat: [f for f in CATEGORY_INPUTS[cat] if evidence.get(f) is None]
        for cat in CATEGORY_WEIGHTS
        if cat not in scores
    }

    roi = _roi_readiness(evidence)

    cost_basis = evidence.get("costco_cost_basis")
    pack_match = evidence.get("pack_match")
    purchase_authorized = (
        cost_basis == "invoice"
        and pack_match in PACK_MATCH_OK
        and evidence.get("amazon_price") is not None
        and evidence.get("economics_confidence") == "estimated"
    )

    return {
        "score": score,
        "score_max": score_max,
        "status": status,
        "status_reason": status_reason,
        "category_scores": category_scores,
        "category_reasons": category_reasons,
        "missing_inputs": missing_inputs,
        "roi_readiness": roi,
        "next_action": _next_action(status, status_reason),
        "purchase_authorized": purchase_authorized,
    }


def compute_completeness(snapshot: Dict[str, Any], account_review_approved: bool = False) -> Dict[str, Any]:
    """Score one normalized snapshot (snapshot-path entry point)."""
    evidence = _evidence_from_snapshot(snapshot)
    scores, reasons = _compute_categories(evidence)
    return _completeness_result(evidence, scores, reasons, account_review_approved)


def compute_scanner_completeness(row: Dict[str, Any]) -> Dict[str, Any]:
    """Score one scanner row (scan-row entry point). Scanner rows never
    carry account-review approval, so the best reachable status is
    'blocked' with reason 'requires_account_review'."""
    if not isinstance(row, dict):
        return _empty_result("not_computable", "row is not a dict")
    evidence = _evidence_from_scanner_row(row)
    scores, reasons = _compute_categories(evidence)
    return _completeness_result(evidence, scores, reasons, account_review_approved=False)


def _empty_result(status: str, reason: str) -> Dict[str, Any]:
    return {
        "score": None,
        "score_max": 0,
        "status": status,
        "status_reason": reason,
        "category_scores": {cat: None for cat in CATEGORY_WEIGHTS},
        "category_reasons": {cat: [] for cat in CATEGORY_WEIGHTS},
        "missing_inputs": {cat: list(CATEGORY_INPUTS[cat]) for cat in CATEGORY_WEIGHTS},
        "roi_readiness": {"ready": None, "reason": None},
        "next_action": "Collect scanner market data to compute completeness",
        "purchase_authorized": False,
    }