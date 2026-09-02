"""Controlled enrichment preflight planner (dry-run, batch <= 20).

PURE / OFFLINE ONLY — zero network, zero file writes, no provider client
imports, no secrets. Planning scaffolding for
docs/asin-market-data-completeness-plan.md (Phase 4). Nothing in the
server imports this yet; this is the operator-facing planning artifact
that must be reviewed before ANY live enrichment run is approved.

Guarantees enforced here:
  - Batch size hard cap MAX_ENRICHMENT_BATCH_SIZE (default 20, clamped 1..20).
  - ASINs validated (10-character alphanumeric).
  - ASINs with a fresh cached snapshot are skipped at zero cost.
  - A budget stop (max_credits) truncates the plan; over-budget ASINs are
    deferred, never silently dropped.
  - Credit estimates are per-provider documented estimates; providers
    without a documented per-request cost report credit_estimate=None
    (unknown), never a guess.
  - Every plan requires human confirmation before execution.
"""

import os
import re
from typing import Any, Dict, List, Optional

from intel_schema import ASIN_PATTERN

DEFAULT_MAX_BATCH = 20
HARD_BATCH_CAP = 20

# Documented per-request credit estimates (from AGENTS.md / provider docs;
# these are estimates for planning, not provider-quoted prices).
CREDIT_ESTIMATES = {
    "EASYPARSER": 5,
    "CHOCODATA": 5,
    "BRIGHTDATA": 1,
    "UNWRANGLE": 1,
    "SCAVIO": None,  # no documented per-request cost
}

FRESHNESS_NOTE = {
    "fresh": "cached snapshot is fresh; skipped at zero cost",
    "stale": "cached snapshot is stale; 1 request planned",
    "absent": "no cached snapshot; 1 request planned",
}


def missing_field_groups(snapshot: Dict[str, Any]) -> List[str]:
    """Which required fact groups are absent from a normalized snapshot.

    Pure read of the snapshot only; never fills values.
    """
    facts = snapshot.get("facts") or {}
    missing: List[str] = []

    identity = facts.get("identity") or {}
    if identity.get("pack_match") not in ("exact", "invoice_confirmed"):
        missing.append("identity_pack")

    cost = facts.get("cost") or {}
    if cost.get("costco_cost") is None:
        missing.append("source_cost")

    market = facts.get("market") or {}
    coverage = market.get("coverage") or {}
    if coverage.get("offer_list_available") is not True or not isinstance(market.get("offers"), list):
        missing.append("market_offers")

    fees = facts.get("fees") or {}
    if fees.get("fba_fee") is None:
        missing.append("fees")

    demand = facts.get("demand") or {}
    if demand.get("estimated_monthly_sales") is None:
        missing.append("demand")

    return missing


def plan_enrichment(
    asins: List[str],
    cache_statuses: Optional[Dict[str, str]] = None,
    snapshots: Optional[Dict[str, Any]] = None,
    provider: str = "EASYPARSER",
    max_credits: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a dry-run enrichment plan. Never performs network or writes.

    cache_statuses: {asin: 'fresh'|'stale'|'absent'} from the read-only
      cache freshness check the operator runs first.
    snapshots: optional {asin: snapshot} for missing-field planning.
    """
    cache_statuses = cache_statuses or {}
    snapshots = snapshots or {}
    provider = (provider or "EASYPARSER").upper()

    env_batch = os.environ.get("MAX_ENRICHMENT_BATCH_SIZE", "")
    try:
        max_batch = int(env_batch) if env_batch else DEFAULT_MAX_BATCH
    except ValueError:
        max_batch = DEFAULT_MAX_BATCH
    max_batch = max(1, min(max_batch, HARD_BATCH_CAP))

    invalid = [a for a in asins if not (isinstance(a, str) and ASIN_PATTERN.fullmatch(a))]
    valid_asins = [a for a in asins if isinstance(a, str) and ASIN_PATTERN.fullmatch(a)]
    selected = valid_asins[:max_batch]
    deferred_batch = valid_asins[max_batch:]

    requests_planned = 0
    skipped_fresh: List[str] = []
    planned_requests: List[Dict[str, Any]] = []
    over_budget: List[str] = []

    for asin in selected:
        status = cache_statuses.get(asin, "absent")
        if status == "fresh":
            skipped_fresh.append(asin)
            continue
        requests_planned += 1
        planned_requests.append(
            {
                "asin": asin,
                "cache_status": status,
                "note": FRESHNESS_NOTE.get(status, "absent"),
                "field_groups_sought": missing_field_groups(snapshots[asin])
                if snapshots.get(asin)
                else [],
            }
        )

    credit_estimate = CREDIT_ESTIMATES.get(provider, None)
    credit_estimate_source = "documented_estimate" if credit_estimate else "unknown"
    estimated_credits = (
        credit_estimate * requests_planned if credit_estimate is not None else None
    )

    if max_credits is not None and estimated_credits is not None and estimated_credits > max_credits:
        affordable = max_credits // credit_estimate if credit_estimate else 0
        over_budget = [r["asin"] for r in planned_requests[affordable:]]
        planned_requests = planned_requests[:affordable]
        requests_planned = len(planned_requests)
        estimated_credits = credit_estimate * requests_planned

    return {
        "provider": provider,
        "asins_input": len(asins),
        "asins_invalid": invalid,
        "asins_selected": [r["asin"] for r in planned_requests],
        "asins_skipped_fresh": skipped_fresh,
        "asins_deferred_batch": deferred_batch,
        "asins_deferred_budget": over_budget,
        "requests_planned": requests_planned,
        "planned_requests": planned_requests,
        "credit_estimate": estimated_credits,
        "credit_estimate_source": credit_estimate_source,
        "max_credits": max_credits,
        "budget_stop": max_credits is not None,
        "dry_run": True,
        "requires_human_confirmation": True,
        "notes": [
            "dry-run plan only; zero requests issued",
            "credits are planning estimates, not provider quotes",
        ],
    }