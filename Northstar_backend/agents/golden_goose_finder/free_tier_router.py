"""Golden Goose Finder — free-tier waterfall router.

Routes each pipeline task (Costco search, Sam's Club search, Amazon search /
product / offers, generic scrape) to the cheapest available free provider,
falling down the DISPATCH_ORDER when a provider is exhausted, keyless, or
fails. Every attempt is recorded in an audit trail so credit spend is
accountable.

§3 gate: routing a LIVE call requires ``live_armed=True`` (named operator
approval, mirroring the ``GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1`` envelope).
Without it, ``run_task`` returns a BLOCKED result and performs zero network
calls. In blocked / exhausted cases nothing is ever billed.

``caller`` is a callable the pipeline supplies to perform the actual
provider request::

    def caller(provider: FreeTierProvider, task_type: str) -> Any:
        ...  # live adapter call; raise on failure

The router selects + debits the provider, calls ``caller``, and on failure
refunds the credits (best-effort) and tries the next provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .free_tier_registry import (
    ALL_TASKS,
    FreeTierLedger,
    FreeTierProvider,
    TASK_AMAZON_OFFERS,
    TASK_AMAZON_PRODUCT,
    TASK_AMAZON_SEARCH,
    TASK_COSTCO_SEARCH,
    TASK_GENERIC_SCRAPE,
    TASK_SAMS_SEARCH,
    get_provider,
    load_default_ledger,
)

# Envelope env var that must equal "1" for live routing (named approval, §3).
LIVE_GATE_ENV = "GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED"

# Task types the router understands.
SUPPORTED_TASKS = frozenset(ALL_TASKS)

# Dispatch order: cheapest / most-reliable first, free fallbacks after.
DISPATCH_ORDER: Dict[str, List[str]] = {
    TASK_COSTCO_SEARCH: [
        "openwebninja_free",
        "bright_data_web_unlocker",
        "firecrawl",
        "scrape_do",
    ],
    TASK_SAMS_SEARCH: [
        "apify_sams",
        "outscraper",
        "bright_data_web_unlocker",
    ],
    TASK_AMAZON_SEARCH: [
        "bright_data_web_unlocker",
        "chocodata",
        "scavio",
        "scrapingdog",
        "scrapingbee",
        "amazonscraperapi",
        "apiclaw",
        "rapidapi_pool",
    ],
    TASK_AMAZON_PRODUCT: [
        "bright_data_web_unlocker",
        "scrapingdog",
        "scrapingbee",
        "amazonscraperapi",
        "flybyapis",
        "apiclaw",
        "rapidapi_pool",
        "scavio",
        "canopy",
        "firecrawl",
        "scrape_do",
    ],
    TASK_AMAZON_OFFERS: [
        "bright_data_web_unlocker",
        "scrapebadger",
        "easyparser",
        "scrapingdog",
        "apiclaw",
    ],
    TASK_GENERIC_SCRAPE: [
        "firecrawl",
        "scrape_do",
        "bright_data_web_unlocker",
    ],
}


@dataclass
class RouteAttempt:
    """One provider attempt within a route."""

    provider_id: str
    status: str  # selected | no_key | exhausted | failed | ok | blocked
    cost: Optional[float] = None
    error: Optional[str] = None
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RouteResult:
    """Outcome of one routed task."""

    task_type: str
    mode: str  # "live" | "blocked" | "exhausted" | "invalid_task"
    ok: bool
    chosen_provider_id: Optional[str] = None
    result: Any = None
    attempts: List[RouteAttempt] = field(default_factory=list)
    error: Optional[str] = None


class AuditTrail:
    """In-memory audit log of routed calls (survives for the run/scan)."""

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def record(self, entry: Dict[str, Any]) -> None:
        self.entries.append(entry)

    def entries_list(self) -> List[Dict[str, Any]]:
        return list(self.entries)


_audit = AuditTrail()


def get_audit_trail() -> List[Dict[str, Any]]:
    """Audit trail of all routed calls this process (for reports)."""
    return _audit.entries_list()


def is_live_approved() -> bool:
    """§3 gate: True only when the operator-named envelope is set to 1."""
    return os.getenv(LIVE_GATE_ENV, "").strip() == "1"


def provider_for_task(
    task_type: str,
    *,
    ledger: Optional[FreeTierLedger] = None,
) -> Optional[FreeTierProvider]:
    """Pick the first usable provider for a task (key present + credits).

    Returns None when every provider for the task is keyless or exhausted.
    Does NOT perform network calls.
    """
    candidates = DISPATCH_ORDER.get(task_type, [])
    for provider_id in candidates:
        provider = get_provider(provider_id)
        if provider is None or not provider.has_key:
            continue
        cost = provider.cost_for(task_type)
        if cost is None:
            continue
        if ledger is not None and not ledger.can_debit(provider_id, cost):
            continue
        return provider
    return None


def run_task(
    task_type: str,
    caller: Callable[[FreeTierProvider, str], Any],
    *,
    live_armed: Optional[bool] = None,
    ledger: Optional[FreeTierLedger] = None,
    audit: Optional[AuditTrail] = None,
) -> RouteResult:
    """Route one task through the free-provider waterfall.

    Args:
        task_type: one of SUPPORTED_TASKS.
        caller: performs the actual provider request; raises on failure.
        live_armed: §3 named approval. None → read the envelope env var.
        ledger: credit ledger; a default is loaded when omitted.
        audit: audit trail; the module-global is used when omitted.

    Returns a RouteResult describing the outcome. No network call is ever
    made for blocked, invalid, or exhausted routes.
    """
    if task_type not in SUPPORTED_TASKS:
        return RouteResult(
            task_type=task_type, mode="invalid_task", ok=False,
            error=f"unknown task type: {task_type}",
        )

    armed = is_live_approved() if live_armed is None else bool(live_armed)
    if not armed:
        result = RouteResult(
            task_type=task_type, mode="blocked", ok=False,
            error="§3 gate: live calls need named operator approval "
                  f"({LIVE_GATE_ENV}=1)",
        )
        result.attempts.append(
            RouteAttempt(provider_id="__gate__", status="blocked",
                         error="live dispatch not armed")
        )
        _record_audit(audit, result)
        return result

    ledger = ledger or load_default_ledger()
    attempts: List[RouteAttempt] = []

    for provider_id in DISPATCH_ORDER.get(task_type, []):
        provider = get_provider(provider_id)
        if provider is None:
            continue
        if not provider.has_key:
            attempts.append(RouteAttempt(provider_id=provider_id, status="no_key"))
            continue
        cost = provider.cost_for(task_type)
        if cost is None:
            attempts.append(RouteAttempt(provider_id=provider_id, status="failed",
                                         error="no cost mapped for task"))
            continue
        if not ledger.can_debit(provider_id, cost):
            attempts.append(RouteAttempt(provider_id=provider_id, status="exhausted",
                                         cost=cost))
            continue
        try:
            outcome = caller(provider, task_type)
        except Exception as exc:  # noqa: BLE001 - provider failure → fallback
            attempts.append(RouteAttempt(provider_id=provider_id, status="failed",
                                         cost=cost, error=str(exc)))
            continue
        # Caller succeeded — debit credits and record success.
        ledger.debit(provider_id, cost)
        attempts.append(RouteAttempt(provider_id=provider_id, status="ok", cost=cost))
        result = RouteResult(
            task_type=task_type, mode="live", ok=True,
            chosen_provider_id=provider_id, result=outcome, attempts=attempts,
        )
        _record_audit(audit, result)
        return result

    result = RouteResult(
        task_type=task_type, mode="exhausted", ok=False,
        error="no provider available (keys/credits/failures)",
        attempts=attempts,
    )
    _record_audit(audit, result)
    return result


def _record_audit(audit: Optional[AuditTrail], result: RouteResult) -> None:
    trail = audit or _audit
    trail.record(
        {
            "task_type": result.task_type,
            "mode": result.mode,
            "ok": result.ok,
            "chosen_provider": result.chosen_provider_id,
            "attempts": [
                {
                    "provider_id": a.provider_id,
                    "status": a.status,
                    "cost": a.cost,
                    "error": a.error,
                }
                for a in result.attempts
            ],
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )