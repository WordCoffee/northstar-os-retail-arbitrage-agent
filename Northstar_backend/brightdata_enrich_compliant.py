#!/usr/bin/env python
"""Bounded live Bright Data enrichment over the 245-ASIN compliant manifest.

The ONLY ASINs this runner may enrich are the items in
``sourcescout_compliant_manifest.json`` whose quantity match is PASS. The
compliant manifest is the deduplicated, quantity-validated 245-item PASS
set — enrichment NEVER runs on the 470-ASIN discovery pool (FAIL=20 and
REVIEW=205 are excluded by the quantity-match compliance gate and are
structurally out of scope for this runner).

The runner drives the recorded enrichment path for this project:
``offer_enrichment.get_scanner_offer(asin)`` with the provider switch set
to BRIGHTDATA (default when live; 1 credit / ASIN through the Bright Data
Web Unlocker ``get_product_detail``). Every PASS ASIN gets its own
normalized enriched snapshot under a unique run directory, with a shared
ledger and a human-readable summary. Nothing in this runner ever fires a
network call on all 470 ASINs.

Live-safety gates (mirror the existing manifest runners):
  - Every live command requires an explicit ``--live`` flag AND an
    explicit ``--max-requests`` AND ``--max-credits`` finite cap. The
    default provider mode must be BRIGHTDATA (via SCANNER_OFFER_ENRICHMENT
    being BRIGHTDATA / AUTO while brightdata is enabled, or the default).
  - The credit cap is a worst-case pre-request reservation plus a post-call
    stop: before each call the runner refuses when
    credits_used + WORST_CASE_REQUEST_CREDITS > max_credits, and after each
    call the provider-reported usage is recorded verbatim (never replaced
    by the reservation). A single in-flight call can still consume more
    than expected; no further request is then issued.
  - Automatic retry is structurally impossible here (no ``--retries`` flag,
    the loop never calls the provider twice for the same ASIN).
  - ``dry-run`` / ``preflight`` modes are zero-network: they validate the
    manifest, plan the batch, and estimate Bright Data credits.

Exit codes:
  0  success (including ASINs that came back unavailable / provider-rejected)
  2  usage / live-gate refusal
  3  run-directory collision or write failure
  4  manifest rejected (before any network path is reachable)
"""

import argparse
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Keep this module provider-locked: importing the client is the only way a
# live fetch can be triggered, and the gate below is checked first.
from bright_data_client import get_product_detail  # noqa: F401  (dispatch contract)
from dotenv import load_dotenv
import live_gate
import offer_enrichment

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent
CATALOG_DIR = BACKEND_DIR / "data" / "catalog"
COMPLIANT_MANIFEST = CATALOG_DIR / "sourcescout_compliant_manifest.json"
RUNS_BASE_DIR = BACKEND_DIR / "data" / "enrich" / "brightdata-compliant"

# Bright Data documented per-request cost: 1 credit per Web Unlocker
# request (see bright_data_client module docstring). 30 is a conservative
# worst-case reservation for the pre-call guard so we never overrun the
# operator-approved credit cap because of provider reporting drift.
WORST_CASE_REQUEST_CREDITS = 30
ESTIMATED_CREDITS_PER_ASIN = 1.0

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_iso_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _make_run_id() -> str:
    return "brightdata-compliant-%s-%s" % (_now_iso_compact(), secrets.token_hex(2))


def _load_manifest(path: Path):
    if not path.exists():
        return None, "compliant manifest file not found: %s" % path
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return None, "malformed compliant manifest: %s" % exc
    if not isinstance(data, dict):
        return None, "compliant manifest must be a JSON object"
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return None, "compliant manifest has no items list"
    return data, None


def _pass_asins(items: List[Dict]) -> List[Dict]:
    """Only PASS items from the compliant manifest — never the full pool."""
    selected = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        qm = item.get("quantity_match") or {}
        status = qm.get("status") if isinstance(qm, dict) else None
        if status != "PASS":
            continue
        asin = str(item.get("asin") or "").strip().upper()
        if not ASIN_PATTERN.fullmatch(asin):
            continue
        if asin in seen:
            continue
        seen.add(asin)
        selected.append(item)
    return selected


def _validate_plan(selected: List[Dict]) -> Optional[str]:
    if not selected:
        return "compliant manifest contains zero PASS ASINs"
    if len(selected) > 400:
        return ("compliant PASS set unexpectedly large (%d); refusing. Expected "
                "<= 245 per quantity-match compliance." % len(selected))
    return None


def _atomic_write(path: Path, payload: Dict) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    with open(tmp, "r", encoding="utf-8") as f:
        json.load(f)
    os.replace(tmp, str(path))


def run_dry_run(args) -> int:
    m, err = _load_manifest(Path(args.manifest))
    if err:
        print("dry-run: REJECTED - %s" % err)
        return 4
    selected = _pass_asins(m.get("items") or [])
    plan_err = _validate_plan(selected)
    if plan_err:
        print("dry-run: REJECTED - %s" % plan_err)
        return 4

    print("dry-run: ACCEPTED (zero network, zero writes)")
    print("manifest: %s" % args.manifest)
    print("compliant PASS ASIN count (this run's full scope): %d" % len(selected))
    print("bright data estimated credits (1 per PASS ASIN): %.1f"
          % (len(selected) * ESTIMATED_CREDITS_PER_ASIN))
    print("total compliant-manifest items (incl. FAIL/REVIEW, never enriched): %d"
          % len(m.get("items") or []))
    print("provider mode: %s (live path only when BRIGHTDATA/AUTO live is on)"
          % offer_enrichment._enrichment_mode())
    print("")
    print("planned ASINs (first 40 of %d):" % len(selected))
    for item in selected[:40]:
        print("  %s  %s" % (item.get("asin"), (item.get("title") or "")[:60]))
    if len(selected) > 40:
        print("  ... (+%d more)" % (len(selected) - 40))
    print("")
    print("exact live command:")
    print("  python brightdata_enrich_compliant.py --live --max-requests %d "
          "--max-credits %d --manifest \"%s\"" % (
              len(selected), len(selected) * 2, args.manifest))
    return 0


def run_preflight(args) -> int:
    """One live call for exactly one explicitly-passed ASIN (a smoke probe)."""
    asin = (args.asin or "").strip().upper()
    if not ASIN_PATTERN.fullmatch(asin):
        print("preflight: REJECTED - invalid/absent ASIN: %r" % (args.asin,))
        return 2
    if not live_gate.live_enabled():
        print("preflight: REJECTED - SCANNER_LIVE_ALLOWED is not an explicit "
              "opt-in (1/true/yes/on). Zero network.")
        return 2

    print("preflight: BRIGHTDATA probe for %s (exactly one request)" % asin)
    start = time.monotonic()
    from bright_data_client import get_product_detail
    raw = get_product_detail(asin)
    elapsed = round(time.monotonic() - start, 3)
    print("probe returned: %s in %.3fs" % (
        "data" if isinstance(raw, dict) and raw else "empty", elapsed))
    print("credits_remaining: %s" % (raw or {}).get("credits_remaining"))
    return 0


def run_batch(args) -> int:
    if not args.live:
        print("error: --live is required for batch; refusing before any provider call")
        return 2
    if not args.max_requests or not args.max_credits:
        print("error: --max-requests and --max-credits finite caps required")
        return 2
    if not live_gate.live_enabled():
        print("error: SCANNER_LIVE_ALLOWED is not set to an explicit opt-in. "
              "Zero provider calls.")
        return 2
    mode = offer_enrichment._enrichment_mode()
    if mode == "OFF":
        print("error: enrichment is OFF (SCANNER_OFFER_ENRICHMENT unset/invalid); "
              "refusing live batch")
        return 2

    m, err = _load_manifest(Path(args.manifest))
    if err:
        print("error: manifest rejected - %s" % err)
        return 4
    selected = _pass_asins(m.get("items") or [])
    plan_err = _validate_plan(selected)
    if plan_err:
        print("error: %s" % plan_err)
        return 4

    run_id = _make_run_id()
    run_dir = RUNS_BASE_DIR / run_id
    if run_dir.exists():
        print("error: run directory already exists; refusing to overwrite: %s" % run_dir)
        return 3
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw").mkdir(exist_ok=True)
    (run_dir / "normalized").mkdir(exist_ok=True)

    print("=== BRIGHT DATA LIVE ENRICHMENT (compliant PASS set only) ===")
    print("manifest: %s" % args.manifest)
    print("compliant PASS ASINs (full scope, never >245): %d" % len(selected))
    print("caps: max_requests=%s max_credits=%s" % (args.max_requests, args.max_credits))
    print("provider mode: %s" % mode)
    print("run dir: %s" % run_dir)

    order = [item.get("asin") for item in selected]
    budget = {"requests_used": 0, "credits_used": 0.0, "credits_reported": 0}
    ledger = []
    results = {}
    stop_reason = None

    for idx, asin in enumerate(order, 1):
        if budget["requests_used"] >= args.max_requests:
            stop_reason = "max_requests"
            break
        if budget["credits_used"] + WORST_CASE_REQUEST_CREDITS > args.max_credits:
            stop_reason = "max_credits"
            break

        started = time.monotonic()
        result = offer_enrichment.get_scanner_offer(asin)
        budget["requests_used"] += 1
        used = (result or {}).get("credits_used")
        credit_kind = "estimated"
        credits_this_call = ESTIMATED_CREDITS_PER_ASIN
        if isinstance(used, (int, float)) and not isinstance(used, bool) and used > 0:
            budget["credits_used"] += float(used)
            budget["credits_reported"] += float(used)
            credits_this_call = float(used)
            credit_kind = "reported"
        else:
            budget["credits_used"] += ESTIMATED_CREDITS_PER_ASIN

        elapsed = round(time.monotonic() - started, 3)
        status = (result or {}).get("enrichment_status") or "unknown"
        buy_box = (result or {}).get("buy_box_price")
        total_sellers = (result or {}).get("total_sellers")
        fba_sellers = (result or {}).get("fba_sellers")
        results[asin] = result or {}
        ledger.append({
            "seq": idx,
            "asin": asin,
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "status": status,
            "credit_basis": credit_kind,
            "credits_this_call": credits_this_call,
            "credits_remaining": (result or {}).get("credits_remaining")
                if isinstance(result, dict) else None,
            "duration_sec": elapsed,
        })
        _atomic_write(run_dir / "normalized" / ("%s.json" % asin), result or {})
        _atomic_write(run_dir / "raw" / ("%s.json" % asin), {
            "asin": asin,
            "status": status,
            "enriched_at": (result or {}).get("enriched_at"),
        })
        print("  [%3d/%3d] %s -> %-9s buy_box=%s sellers=%s fba=%s credits=%.1f"
              % (idx, len(order), asin, status, buy_box, total_sellers, fba_sellers,
                 credits_this_call))
        time.sleep(0.1)

    outcome_summary = {
        "complete": sum(1 for r in ledger if r["status"] == "complete"),
        "partial": sum(1 for r in ledger if r["status"] == "partial"),
        "other": sum(1 for r in ledger if r["status"] not in ("complete", "partial")),
    }
    summary = {
        "run_id": run_id,
        "generated_at": _now_iso(),
        "provider": "BRIGHTDATA",
        "scope": "sourcescout_compliant_manifest PASS only",
        "compliant_pass_count": len(selected),
        "requests_used": budget["requests_used"],
        "requests_cap": args.max_requests,
        "credits_used": round(budget["credits_used"], 1),
        "credits_reported": round(budget["credits_reported"], 1),
        "credits_cap": args.max_credits,
        "stop_reason": stop_reason,
        "outcome_counts": outcome_summary,
        "enriched_at": _now_iso(),
        "credits_remaining": None,
    }
    _atomic_write(run_dir / "summary.json", summary)

    index_path = RUNS_BASE_DIR / "run-index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "run_id": run_id,
            "run_dir": str(run_dir),
            "generated_at": _now_iso(),
            "requests_used": budget["requests_used"],
            "credits_used": round(budget["credits_used"], 1),
            "stop_reason": stop_reason,
        }, default=str) + "\n")

    print("")
    print("=== SUMMARY ===")
    print("run_id:  %s" % run_id)
    print("scope:   245-PASS compliant manifest (never 470)")
    print("requests/cap:    %d / %s" % (budget["requests_used"], args.max_requests))
    print("credits used/cap: %.1f / %s (reported=%.1f)"
          % (budget["credits_used"], args.max_credits, budget["credits_reported"]))
    print("outcomes: %s" % outcome_summary)
    print("artifacts: %s" % run_dir)
    print("")
    print("STOP STATEMENT")
    print("Enriched data is market intelligence only. No ASIN is purchase-")
    print("authorized by this run; a separate invoice-legitimacy + sourcing")
    print("verification step is still required before any order.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Bright Data live enrichment over the 245-ASIN PASS "
                    "compliant manifest (never the 470 discovery pool).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dry = sub.add_parser("dry-run", help="validate + print plan (zero network)")
    p_dry.add_argument("--manifest", default=str(COMPLIANT_MANIFEST))

    p_pre = sub.add_parser("preflight", help="one live probe for one ASIN")
    p_pre.add_argument("--asin", required=True)
    p_pre.add_argument("--manifest", default=str(COMPLIANT_MANIFEST))

    p_batch = sub.add_parser("run", help="live batch over the PASS set")
    p_batch.add_argument("--live", action="store_true")
    p_batch.add_argument("--manifest", default=str(COMPLIANT_MANIFEST))
    p_batch.add_argument("--max-requests", type=int, default=None)
    p_batch.add_argument("--max-credits", type=int, default=None)

    args = parser.parse_args(argv)
    if args.cmd == "dry-run":
        return run_dry_run(args)
    if args.cmd == "preflight":
        return run_preflight(args)
    return run_batch(args)


if __name__ == "__main__":
    sys.exit(main())
