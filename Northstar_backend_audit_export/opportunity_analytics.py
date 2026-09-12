"""Opportunity analytics for the Product Scout (cache-only, read-only).

Pure, deterministic helpers that turn one scored row into explainable
opportunity fields: match evidence summary, verification tasks, match
readiness, data-completeness score, opportunity readiness, recommended
next step, opportunity score (with reasons), and freshness labels.

Rules of honesty (mirrored from the scanner contracts):
  - No network, no writes, no invented values. Every field stays
    None/Unknown when its input is missing; 0 is never used as a
    substitute for unknown.
  - A known conflict (mismatch) always beats title similarity: a
    mismatched row is Blocked and scores 0, never Tier/Pass/Scale.
  - A row missing price or COGS cannot be ranked: opportunity_score is
    None (never 0) and readiness says what is missing.
  - Freshness is display-only; it never triggers auto-refresh and never
    changes economics.
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

FRESH_DAYS = 7
AGING_DAYS = 30

# Display-only readiness vocabulary (never alters match_quality or the
# purchase gate).
MATCH_READINESS = {
    "exact": "exact_ready",
    "invoice_confirmed": "exact_ready",
    "high_confidence": "likely_verify_pack_upc",
    "candidate": "candidate_manual_review",
    "mismatch": "blocked_mismatch",
    "unknown": "no_costco_match",
}

_VERIFICATION_TASK_PRIORITY = [
    "blocked_mismatch",
    "no_costco_candidate",
    "verify_upc",
    "verify_pack",
    "verify_count",
    "verify_weight",
    "verify_variant",
    "verify_flavor",
    "verify_listing",
    "verify_costco_price",
    "verify_fba_fee",
    "enrich_sales",
    "enrich_sellers",
]

# (substring, task) hints mapped from the match_reason / status text.
_REASON_HINTS = [
    ("upc", "verify_upc"),
    ("ean", "verify_upc"),
    ("pack/count differs", "verify_count"),
    ("net weight differs", "verify_weight"),
    ("unit dimension differs", "verify_pack"),
    ("flavor differs", "verify_flavor"),
    ("variant", "verify_variant"),
    ("formula/flavor differs", "verify_variant"),
    ("title identity", "verify_listing"),
    ("mapping verification required", "verify_listing"),
    ("candidate", "verify_listing"),
]


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _age_days(value: Any) -> Optional[float]:
    ts = _parse_ts(value)
    if ts is None:
        return None
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0


def freshness_label(row: Dict[str, Any], cache_meta: Optional[Dict[str, Any]] = None) -> str:
    """Fresh | Aging | Stale | Unknown. Display-only basis, never an
    auto-refresh trigger. Basis order: enriched_at -> observed_at ->
    imported_at -> cache fetched_at."""
    basis = (
        row.get("enriched_at")
        or row.get("observed_at")
        or row.get("imported_at")
        or (cache_meta or {}).get("cache_fetched_at")
    )
    age = _age_days(basis)
    if age is None:
        return "Unknown"
    if age < FRESH_DAYS:
        return "Fresh"
    if age < AGING_DAYS:
        return "Aging"
    return "Stale"


def freshness_basis(row: Dict[str, Any], cache_meta: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Which timestamp the freshness label is based on (the same priority)."""
    for key in ("enriched_at", "observed_at", "imported_at"):
        if row.get(key):
            return key
    if (cache_meta or {}).get("cache_fetched_at"):
        return "cache_fetched_at"
    return None


def _reason_text(row: Dict[str, Any]) -> str:
    return " ".join(
        str(v)
        for v in (
            row.get("match_reason"),
            row.get("cost_match_reason"),
            row.get("economics_status"),
            row.get("economics_note"),
        )
        if v
    ).lower()


def verification_tasks(row: Dict[str, Any]) -> List[str]:
    """Ordered, de-duplicated list of verification tasks for this row."""
    tasks: List[str] = []
    match_quality = row.get("match_quality") or row.get("pack_match") or "unknown"

    if match_quality == "mismatch":
        return ["blocked_mismatch"]

    has_cost = row.get("costco_cost") is not None
    if not has_cost:
        tasks.append("no_costco_candidate")

    text = _reason_text(row)
    if match_quality == "candidate":
        tasks += ["verify_upc", "verify_pack"]
    elif match_quality in ("exact", "invoice_confirmed", "high_confidence", "unknown"):
        for hint, task in _REASON_HINTS:
            if hint in text and task not in tasks:
                tasks.append(task)

    if row.get("economics_confidence") in ("provisional",) or (
        row.get("economics_status") == "needs_fee_verification"
    ):
        tasks.append("verify_fba_fee")

    if row.get("monthly_sales_estimate") is None:
        tasks.append("enrich_sales")
    if row.get("total_sellers") is None or row.get("fba_sellers") is None:
        tasks.append("enrich_sellers")

    if not tasks:
        tasks.append("none")
    return tasks


def primary_verification_task(tasks: Optional[List[str]]) -> Optional[str]:
    """Highest-priority task from the list (blocked > no-match > verify >
    enrich > none)."""
    if not tasks:
        return None
    for priority in _VERIFICATION_TASK_PRIORITY:
        if priority in tasks:
            return priority
    return "none"


def match_readiness(row: Dict[str, Any]) -> str:
    quality = row.get("match_quality") or row.get("pack_match") or "unknown"
    return MATCH_READINESS.get(quality, "no_costco_match")


def data_completeness_score(row: Dict[str, Any], cache_meta: Optional[Dict[str, Any]] = None) -> int:
    """0-100, one point per present dimension (never 0 for missing data)."""
    dims = [
        bool(row.get("name")) and bool(row.get("asin") or row.get("product_url")),
        _number(row.get("amazon_price")) and row["amazon_price"] > 0,
        _number(row.get("costco_cost")) and row["costco_cost"] > 0,
        row.get("economics_confidence") in ("estimated", "provisional"),
        _number(row.get("fba_fee")) and row["fba_fee"] > 0,
        row.get("monthly_sales_estimate") is not None,
        row.get("total_sellers") is not None,
        row.get("fba_sellers") is not None,
        row.get("match_quality") in ("exact", "invoice_confirmed", "high_confidence"),
        freshness_basis(row, cache_meta) is not None,
    ]
    return sum(1 for present in dims if present) * 10


def opportunity_readiness(row: Dict[str, Any]) -> str:
    """Single honest label for the row's readiness to act on."""
    match_quality = row.get("match_quality") or row.get("pack_match") or "unknown"
    if match_quality == "mismatch":
        return "blocked_mismatch"
    if row.get("costco_cost") is None:
        return "needs_costco_match"
    if row.get("amazon_price") is None:
        return "needs_price"
    if row.get("economics_status") == "needs_fee_verification" or row.get("economics_confidence") == "provisional":
        return "economics_provisional"
    if match_quality == "candidate":
        return "needs_identity_verification"
    if row.get("monthly_sales_estimate") is None:
        return "needs_sales_data"
    if row.get("total_sellers") is None or row.get("fba_sellers") is None:
        return "needs_seller_data"
    if row.get("economics_confidence") == "estimated":
        return "complete_opportunity"
    return "insufficient_data"


def recommended_next_step(row: Dict[str, Any]) -> str:
    """One actionable next step, mirroring the readiness label."""
    readiness = opportunity_readiness(row)
    match_quality = row.get("match_quality") or row.get("pack_match") or "unknown"
    if readiness == "blocked_mismatch":
        return "reject_mismatch"
    if readiness == "needs_costco_match":
        return "find_costco_match"
    if readiness == "needs_price":
        return "await_data"
    if readiness == "economics_provisional":
        return "get_fba_fee_preview"
    if readiness == "needs_identity_verification":
        return "verify_upc_and_variant"
    if readiness == "needs_sales_data" or readiness == "needs_seller_data":
        return "enrich_sales_and_sellers"
    if match_quality == "high_confidence":
        return "verify_costco_pack_and_price"
    if readiness == "complete_opportunity":
        return "review_top_opportunity"
    return "await_data"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def opportunity_score(row: Dict[str, Any]) -> Any:
    """(score, reasons) or (None, reasons) when the row cannot be ranked.

    Design (decided in the hardening batch):
      economics  40 * clamp01(roi/100) + 30 * clamp01(net/30)
      sales      20 * clamp01(log1p(sales)/log1p(5000))
      competition 10 * (1 - min(fba_sellers,5)/5)
      match      25 exact/invoice_confirmed | 15 high_confidence | 5 candidate | 0 none
      then multiplied by the completeness factor (0.5 + 0.5 * completeness/100).
      Mismatch always scores 0 (blocked). Missing price/COGS -> None.
    """
    reasons: List[str] = []
    match_quality = row.get("match_quality") or row.get("pack_match") or "unknown"
    if match_quality == "mismatch":
        return 0.0, ["Blocked: %s" % (row.get("match_reason") or row.get("cost_match_reason") or "known mismatch")]

    if row.get("amazon_price") is None:
        return None, ["Missing Amazon price"]
    if row.get("costco_cost") is None:
        return None, ["Missing Costco COGS"]

    score = 0.0
    roi = row.get("roi_pct")
    net = row.get("net_profit")
    if _number(roi) and _number(net):
        score += 40.0 * _clamp01(roi / 100.0) + 30.0 * _clamp01(net / 30.0)
        reasons.append("economics (roi %.0f%%, net $%.2f)" % (roi, net))
    else:
        reasons.append("economics missing")

    sales = row.get("monthly_sales_estimate")
    if _number(sales) and sales >= 0:
        score += 20.0 * _clamp01(math.log1p(sales) / math.log1p(5000))
        reasons.append("sales velocity (est %.0f/mo)" % sales)
    else:
        reasons.append("sales velocity missing")

    fba_sellers = row.get("fba_sellers")
    if _number(fba_sellers) and fba_sellers >= 0:
        score += 10.0 * (1.0 - min(fba_sellers, 5) / 5.0)
        reasons.append("competition (%d FBA sellers)" % fba_sellers)
    else:
        reasons.append("seller data missing")

    score += {"exact": 25.0, "invoice_confirmed": 25.0, "high_confidence": 15.0, "candidate": 5.0}.get(match_quality, 0.0)
    if match_quality in ("exact", "invoice_confirmed"):
        reasons.append("match (%s)" % match_quality)
    elif match_quality in ("high_confidence", "candidate"):
        reasons.append("match (%s)" % match_quality)

    completeness = data_completeness_score(row)
    factor = 0.5 + 0.5 * completeness / 100.0
    if factor < 1.0:
        reasons.append("completeness x%.2f (%d/100)" % (factor, completeness))
    return round(score * factor, 1), reasons


def opportunity_fields(row: Dict[str, Any], cache_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assemble the allowlisted opportunity fields for one row. Pure and
    read-only; merges into the scanner result row."""
    tasks = verification_tasks(row)
    score, reasons = opportunity_score(row)
    return {
        "match_evidence": _match_evidence(row),
        "verification_tasks": tasks,
        "primary_verification_task": primary_verification_task(tasks),
        "match_readiness": match_readiness(row),
        "data_completeness_score": data_completeness_score(row, cache_meta),
        "opportunity_readiness": opportunity_readiness(row),
        "recommended_next_step": recommended_next_step(row),
        "opportunity_score": score,
        "opportunity_score_reasons": reasons,
        "freshness_label": freshness_label(row, cache_meta),
        "freshness_basis": freshness_basis(row, cache_meta),
        "freshness_as_of": (
            row.get("enriched_at")
            or row.get("observed_at")
            or row.get("imported_at")
            or (cache_meta or {}).get("cache_fetched_at")
        ),
    }


def _match_evidence(row: Dict[str, Any]) -> Dict[str, Any]:
    """Display-only evidence summary. Never gates economics or purchases:
    it re-states the match decision and its supporting signals, and marks
    anything the decision did not use as absent."""
    evidence = row.get("match_evidence") or {}
    if isinstance(evidence, dict) and evidence:
        return evidence
    return {
        "match_quality": row.get("match_quality") or row.get("pack_match") or "unknown",
        "match_reason": row.get("match_reason") or row.get("cost_match_reason"),
        "evidence": None,
    }