"""Controlled, resumable live enrichment for cached ASINs.

Easyparser is DEPRECATED and DISABLED. Live enrichment now routes through
the provider switch (--provider), defaulting to RapidAPI:

    python enrich_cached_asins.py --mode status
    python enrich_cached_asins.py --mode dry-run [--limit N]
    python enrich_cached_asins.py --mode preflight --live --provider rapidapi \
        --asin B0XXXXXXXXXX --limit 1 --max-requests 1 --max-credits N
    python enrich_cached_asins.py --mode batch --live --provider rapidapi \
        --limit N --max-requests N --max-credits N [--retries N]

- status / dry-run: zero network calls. They read the candidate cache and
  the snapshot store and plan the request/credit budget.
- preflight: exactly ONE live provider request for exactly one explicitly
  supplied ASIN, then an atomic per-ASIN snapshot save.
- batch: live mode only, always driven by the candidate cache with an
  explicit --limit (never defaults to all candidates). Every completed
  ASIN snapshot is saved atomically before continuing; resume skips fresh
  successful snapshots and re-attempts failed/partial records only when
  eligible under the bounded retry policy (attempts < 3, no permanent
  error). Runtime retries are opt-in via --retries (finite, recorded).

Live-safety gates: every live command must pass --live plus finite
--limit, --max-requests, and --max-credits. The run refuses to start
when any finite cap is absent, and stops as soon as a cap is reached.

Budget: requests and credits (CENTS for RapidAPI/DataForSEO) are counted
per request. Credit/cost usage is taken from the provider response when
returned; otherwise the provider's documented estimate constant is used.

Providers:
  rapidapi   -> rapidapi_client.get_rapidapi_offers (DEFAULT)
  dataforseo -> dataforseo_adapter.get_dataforseo_offers
  easyparser -> DISABLED (refuses with a clear data_gap; never calls network)

Exit codes: 0 success; 2 usage/cap refusal; 3 store/report write failure;
4 candidate cache missing/corrupt.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import amazon_search
import market_snapshot_store as store
import rapidapi_client
import dataforseo_adapter
# Easyparser is DEPRECATED/DISABLED. Imported only for the refusal path.
import easyparser_client

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")

ESTIMATED_CREDITS_PER_ASIN = 5.0

MODE_STATUS = "status"
MODE_DRY_RUN = "dry-run"
MODE_PREFLIGHT = "preflight"
MODE_BATCH = "batch"


class UsageError(Exception):
    pass


class StoreError(Exception):
    pass


class CacheError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_asins() -> List[str]:
    """Ordered, deduped ASIN list from the candidate cache (zero network)."""
    asins: List[str] = []
    seen = set()
    for c in amazon_search.load_cached_candidates():
        asin = c.get("asin")
        if isinstance(asin, str) and ASIN_PATTERN.fullmatch(asin) and asin not in seen:
            seen.add(asin)
            asins.append(asin)
    return asins


def _require_live_caps(args, mode: str) -> None:
    missing = []
    if not args.live:
        missing.append("--live")
    if args.limit is None or args.limit < 1:
        missing.append("--limit N (>= 1)")
    if args.max_requests is None or args.max_requests < 1:
        missing.append("--max-requests N (>= 1)")
    if args.max_credits is None or args.max_credits < 1:
        missing.append("--max-credits N (>= 1)")
    if missing:
        raise UsageError(
            "Live mode refused: every finite cap is required. Missing: "
            + ", ".join(missing)
            + ". Refusing to run without all caps."
        )


def _plan(asins: List[str], limit: Optional[int]) -> Dict[str, int]:
    snapshots = store.load_snapshots()
    planned = asins if limit is None or limit >= len(asins) else asins[:limit]
    fresh = 0
    retry_eligible = 0
    absent = 0
    for asin in planned:
        snap = snapshots.get(asin)
        if snap is None:
            absent += 1
        elif store.is_fresh_success(snap):
            fresh += 1
        elif store.is_retry_eligible(snap):
            retry_eligible += 1
    return {
        "planned": len(planned),
        "absent": absent,
        "fresh_skippable": fresh,
        "retry_eligible": retry_eligible,
    }


def _run_status(args) -> int:
    snapshots = store.load_snapshots()
    by_status: Dict[str, int] = {}
    fresh = 0
    stale = 0
    credits_reported = 0
    credits_reported_n = 0
    for snap in snapshots.values():
        if not isinstance(snap, dict):
            continue
        status = snap.get("data_status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        if store.snapshot_freshness_status(snap) == "fresh":
            fresh += 1
        else:
            stale += 1
        used = snap.get("credits_used")
        if isinstance(used, int) and not isinstance(used, bool) and used > 0:
            credits_reported += used
            credits_reported_n += 1
    report = store.read_run_report()
    print("snapshot_store:        %s" % store._store_path())
    print("snapshots:             %d" % len(snapshots))
    for status in sorted(by_status):
        print("  %-12s %d" % (status, by_status[status]))
    print("fresh / stale:         %d / %d" % (fresh, stale))
    print("credits_reported:      %d (from %d snapshots)" % (credits_reported, credits_reported_n))
    print("last_run:              %s" % (report.get("generated_at") if report else "none"))
    if report:
        print("last_run_mode:         %s" % report.get("mode"))
        print("last_run_counts:       %s" % json.dumps(report.get("counts", {})))
        print("last_run_stop_reason:  %s" % report.get("stop_reason"))
    return 0


def _run_dry_run(args) -> int:
    asins = _candidate_asins()
    if not asins:
        raise CacheError("candidate cache is missing or empty; nothing to plan")
    plan = _plan(asins, args.limit)
    limit_text = args.limit if args.limit else len(asins)
    requests = plan["planned"] - plan["fresh_skippable"]
    provider = getattr(args, "provider", "rapidapi")
    credits_est = requests * ESTIMATED_CREDITS_PER_ASIN
    print("mode:                  dry-run (zero network calls)")
    print("candidates:            %d" % len(asins))
    print("limit:                 %s" % limit_text)
    print("provider:              %s" % provider)
    print("planned:               %d" % plan["planned"])
    print("  absent snapshot:     %d" % plan["absent"])
    print("  fresh (skip):        %d" % plan["fresh_skippable"])
    print("  retry eligible:      %d" % plan["retry_eligible"])
    print("requests projected:    %d" % requests)
    print("credits projected:     ~%.0f (planning estimate; RapidAPI/DataForSEO use cents)" % credits_est)
    print("stages:                offers; sales not requested")
    report = {
        "mode": MODE_DRY_RUN,
        "generated_at": _now_iso(),
        "caps": {
            "live": bool(args.live),
            "limit": args.limit,
            "max_requests": args.max_requests,
            "max_credits": args.max_credits,
        },
        "counts": {
            "planned": plan["planned"],
            "absent": plan["absent"],
            "fresh_skippable": plan["fresh_skippable"],
            "retry_eligible": plan["retry_eligible"],
        },
        "credits": {
            "projected_requests": requests,
            "projected_estimated_credits": round(credits_est, 1),
        },
        "stop_reason": "dry_run",
    }
    ok, err = store.write_run_report(report)
    if not ok:
        raise StoreError(err)
    return 0


def _validate_preflight(args) -> str:
    if not args.asin:
        raise UsageError("Preflight requires exactly one --asin B0XXXXXXXXXX")
    if not ASIN_PATTERN.fullmatch(args.asin):
        raise UsageError("Invalid ASIN: expected exactly 10 alphanumeric characters")
    if args.limit != 1:
        raise UsageError("Preflight requires --limit 1")
    if args.max_requests != 1:
        raise UsageError("Preflight requires --max-requests 1")
    return args.asin


def _disabled_easyparser(asin: str) -> Dict:
    """Refusal shape for the deprecated Easyparser path. Never hits network."""
    return {
        "source": "easyparser",
        "asin": asin,
        "offers": [],
        "offers_returned_count": 0,
        "credits_used": 0,
        "data_gaps": [
            "Easyparser integration is DEPRECATED and DISABLED. "
            "Use --provider rapidapi or --provider dataforseo."
        ],
    }


def _fetch_once(asin: str, caps: Dict[str, int], budget: Dict[str, float],
                provider: str = "rapidapi") -> Dict:
    """One provider request, budget-aware. Never raises."""
    if budget["requests_used"] >= caps["max_requests"]:
        return {"skipped": "max_requests"}
    if budget["credits_used"] >= caps["max_credits"]:
        return {"skipped": "max_credits"}
    started = time.monotonic()
    if provider == "rapidapi":
        result = rapidapi_client.get_rapidapi_offers(asin)
    elif provider == "dataforseo":
        result = dataforseo_adapter.get_dataforseo_offers(asin)
    else:
        # Easyparser deprecated/disabled.
        result = _disabled_easyparser(asin)
    budget["requests_used"] += 1
    used = result.get("credits_used")
    if isinstance(used, int) and not isinstance(used, bool) and used > 0:
        budget["credits_used"] += used
        budget["credits_reported"] += used
    else:
        budget["credits_used"] += ESTIMATED_CREDITS_PER_ASIN
    budget["seconds"] += time.monotonic() - started
    return result


def _run_preflight(args) -> int:
    _require_live_caps(args, MODE_PREFLIGHT)
    asin = _validate_preflight(args)
    prior = store.get_snapshot(asin)
    prior_attempts = 0
    if isinstance(prior, dict) and isinstance(prior.get("attempts"), int):
        prior_attempts = prior["attempts"]

    caps = {
        "max_requests": args.max_requests,
        "max_credits": args.max_credits,
    }
    budget = {"requests_used": 0, "credits_used": 0.0, "credits_reported": 0, "seconds": 0.0}
    result = _fetch_once(asin, caps, budget, provider=args.provider)
    attempts = prior_attempts + 1
    snapshot = store.build_snapshot(asin, result, prior_attempts=prior_attempts)
    snapshot["attempts"] = attempts

    saved = None
    if snapshot["data_status"] in (store.DATA_STATUS_AVAILABLE, store.DATA_STATUS_PARTIAL):
        ok, err = store.save_snapshot(asin, snapshot)
        if not ok:
            raise StoreError(err)
        saved = snapshot["data_status"]
    elif prior is None:
        ok, err = store.save_snapshot(asin, snapshot)
        if not ok:
            raise StoreError(err)
    else:
        print("note:                   prior valid snapshot preserved; failure recorded in report")

    print("mode:                  preflight (exactly one %s request)" % args.provider)
    print("asin:                  %s" % asin)
    print("data_status:           %s" % snapshot["data_status"])
    print("offers_returned:       %s" % snapshot["offers_returned"])
    print("offers_complete:       %s" % snapshot["offers_complete"])
    print("buy_box_price:         %s" % snapshot["buy_box"]["price"])
    print("buy_box_seller:        %s" % snapshot["buy_box"]["seller_name"])
    print("credits_used:          %s" % snapshot["credits_used"])
    print("credits_remaining:     %s" % snapshot["credits_remaining"])
    print("requests_used:         %d" % budget["requests_used"])
    print("saved:                 %s" % (saved if saved else "not saved"))

    report = {
        "mode": MODE_PREFLIGHT,
        "generated_at": _now_iso(),
        "caps": {
            "live": True,
            "limit": 1,
            "max_requests": args.max_requests,
            "max_credits": args.max_credits,
            "asin": asin,
        },
        "counts": {
            "planned": 1,
            "attempted": 1,
            "succeeded": 1 if snapshot["data_status"] == store.DATA_STATUS_AVAILABLE else 0,
            "partial": 1 if snapshot["data_status"] == store.DATA_STATUS_PARTIAL else 0,
            "failed": 1 if snapshot["data_status"] in (store.DATA_STATUS_FAILED, store.DATA_STATUS_UNAVAILABLE) else 0,
            "skipped_fresh": 0,
            "skipped_cap": 0,
            "skipped_retry_ineligible": 0,
        },
        "credits": {
            "reported_used": budget["credits_reported"],
            "estimated_used": round(budget["credits_used"], 1),
            "remaining_cap": caps["max_credits"] - budget["credits_used"],
        },
        "stop_reason": "completed",
        "errors": [{"asin": asin, "error": snapshot["last_error"]}] if snapshot["last_error"] else [],
        "duration_seconds": round(budget["seconds"], 3),
    }
    ok, err = store.write_run_report(report)
    if not ok:
        raise StoreError(err)
    return 0


def _run_batch(args) -> int:
    _require_live_caps(args, MODE_BATCH)
    if args.asin:
        raise UsageError("--asin is only valid with --mode preflight; batch is cache-driven")
    asins = _candidate_asins()
    if not asins:
        raise CacheError("candidate cache is missing or empty; nothing to enrich")
    if args.retries < 0:
        raise UsageError("--retries must be >= 0")

    limit = args.limit if args.limit < len(asins) else len(asins)
    snapshots = store.load_snapshots()
    caps = {"max_requests": args.max_requests, "max_credits": args.max_credits}
    budget = {"requests_used": 0, "credits_used": 0.0, "credits_reported": 0, "seconds": 0.0}

    counts = {
        "planned": limit,
        "attempted": 0,
        "succeeded": 0,
        "partial": 0,
        "failed": 0,
        "skipped_fresh": 0,
        "skipped_cap": 0,
        "skipped_retry_ineligible": 0,
    }
    errors: List[Dict] = []
    stop_reason = "completed"

    for asin in asins[:limit]:
        if budget["requests_used"] >= caps["max_requests"]:
            stop_reason = "max_requests"
            break
        if budget["credits_used"] >= caps["max_credits"]:
            stop_reason = "max_credits"
            break

        prior = snapshots.get(asin)
        if store.is_fresh_success(prior):
            counts["skipped_fresh"] += 1
            continue
        if prior is not None and not store.is_retry_eligible(prior):
            counts["skipped_retry_ineligible"] += 1
            continue

        prior_attempts = 0
        if isinstance(prior, dict) and isinstance(prior.get("attempts"), int):
            prior_attempts = prior["attempts"]

        outcome = None
        last_error = None
        snapshot = None
        for attempt_index in range(1 + max(0, args.retries)):
            if attempt_index > 0:
                if budget["requests_used"] >= caps["max_requests"]:
                    stop_reason = "max_requests"
                    break
                if budget["credits_used"] >= caps["max_credits"]:
                    stop_reason = "max_credits"
                    break
            result = _fetch_once(asin, caps, budget, provider=args.provider)
            counts["attempted"] += 1
            snapshot = store.build_snapshot(
                asin, result, prior_attempts=prior_attempts + attempt_index
            )
            snapshot["attempts"] = prior_attempts + attempt_index + 1
            status = snapshot["data_status"]
            if status in (store.DATA_STATUS_AVAILABLE, store.DATA_STATUS_PARTIAL):
                outcome = status
                ok, err = store.save_snapshot(asin, snapshot)
                if not ok:
                    raise StoreError(err)
                break
            last_error = snapshot["last_error"] or "; ".join(snapshot["data_gaps"])
        if stop_reason in ("max_requests", "max_credits"):
            break

        if outcome == store.DATA_STATUS_AVAILABLE:
            counts["succeeded"] += 1
        elif outcome == store.DATA_STATUS_PARTIAL:
            counts["partial"] += 1
        else:
            counts["failed"] += 1
            errors.append({"asin": asin, "error": last_error or "no offer data"})
            if last_error and prior is None:
                ok, err = store.save_snapshot(asin, snapshot)
                if not ok:
                    raise StoreError(err)

    if stop_reason in ("max_requests", "max_credits"):
        counts["skipped_cap"] = (
            limit - counts["succeeded"] - counts["partial"] - counts["failed"]
            - counts["skipped_fresh"] - counts["skipped_retry_ineligible"]
        )

    report = {
        "mode": MODE_BATCH,
        "generated_at": _now_iso(),
        "caps": {
            "live": True,
            "limit": args.limit,
            "max_requests": args.max_requests,
            "max_credits": args.max_credits,
            "retries": args.retries,
        },
        "counts": counts,
        "credits": {
            "reported_used": budget["credits_reported"],
            "estimated_used": round(budget["credits_used"], 1),
            "remaining_cap": max(0, caps["max_credits"] - budget["credits_used"]),
        },
        "stop_reason": stop_reason,
        "errors": errors,
        "duration_seconds": round(budget["seconds"], 3),
    }
    ok, err = store.write_run_report(report)
    if not ok:
        raise StoreError(err)

    print("mode:                  batch (live %s)" % args.provider)
    print("planned:               %d" % counts["planned"])
    print("attempted:             %d" % counts["attempted"])
    print("succeeded:             %d" % counts["succeeded"])
    print("partial:               %d" % counts["partial"])
    print("failed:                %d" % counts["failed"])
    print("skipped_fresh:         %d" % counts["skipped_fresh"])
    print("skipped_cap:           %d" % counts["skipped_cap"])
    print("skipped_retry_inelig:  %d" % counts["skipped_retry_ineligible"])
    print("requests_used:         %d" % budget["requests_used"])
    print("credits_reported:      %d" % budget["credits_reported"])
    print("credits_estimated:     %.0f" % budget["credits_used"])
    print("stop_reason:           %s" % stop_reason)
    for entry in errors[:10]:
        print("  failed %s: %s" % (entry["asin"], entry["error"]))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Controlled live enrichment for cached ASINs "
        "(dry-run/status are zero-network; preflight/batch require all live caps). "
        "Easyparser is disabled; use --provider rapidapi (default) or dataforseo.",
    )
    parser.add_argument("--mode", choices=[MODE_STATUS, MODE_DRY_RUN, MODE_PREFLIGHT, MODE_BATCH],
                        default=MODE_DRY_RUN)
    parser.add_argument("--provider", choices=["rapidapi", "dataforseo"],
                        default="rapidapi",
                        help="live provider (Easyparser is deprecated/disabled)")
    parser.add_argument("--live", action="store_true", help="allow live provider requests")
    parser.add_argument("--asin", default=None, help="exactly one ASIN (preflight only)")
    parser.add_argument("--limit", type=int, default=None,
                        help="request budget limit (>= 1; required for live modes)")
    parser.add_argument("--max-requests", type=int, default=None,
                        help="hard cap on provider requests (required for live modes)")
    parser.add_argument("--max-credits", type=int, default=None,
                        help="hard cap on credits (required for live modes)")
    parser.add_argument("--retries", type=int, default=0,
                        help="opt-in finite retries per ASIN within a batch (default 0)")
    args = parser.parse_args(argv)

    try:
        if args.mode == MODE_STATUS:
            return _run_status(args)
        if args.mode == MODE_DRY_RUN:
            return _run_dry_run(args)
        if args.mode == MODE_PREFLIGHT:
            return _run_preflight(args)
        return _run_batch(args)
    except UsageError as e:
        print("error: %s" % e)
        return 2
    except StoreError as e:
        print("error: %s" % e)
        return 3
    except CacheError as e:
        print("error: %s" % e)
        return 4


if __name__ == "__main__":
    sys.exit(main())
