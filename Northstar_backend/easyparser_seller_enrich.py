#!/usr/bin/env python
"""Bounded Easyparser seller-roster enrichment over the 245-ASIN PASS set.

The ONLY ASINs this runner may enrich are the items in
``sourcescout_compliant_manifest.json`` whose quantity match is PASS
(never the 470-ASIN discovery pool; FAIL/REVIEW excluded by the
quantity-match compliance gate).

Why this runner exists: the Bright Data Web Unlocker path structurally
cannot return seller data (``fba_sellers`` is None by construction, and
``total_sellers`` only when the page carries a "New (N) from" line). The
Easyparser OFFER operation returns the genuine per-seller roster
(seller id/name/rating, buybox_winner, is_fba/is_fbm, Prime, condition,
shipping) at ~1 credit per ASIN. Verified by a live 1-ASIN probe on
B00BH3HPZW: offer_count=69, 11 offers returned, buy-box winner +
FBA/FBM flags present, credits_used=1 with a provider-reported balance.

Live-safety gates (mirror brightdata_enrich_compliant.py, plus resume):
  - Every live command requires explicit ``--live`` AND finite
    ``--max-requests`` AND ``--max-credits``. Refuses before any network
    when caps/mode are missing or SCANNER_LIVE_ALLOWED is not opt-in.
  - Worst-case pre-request credit reservation plus post-call stop on the
    provider-reported usage (recorded verbatim, never replaced).
  - Provider-balance stop: when a call reports credits_remaining == 0 the
    runner stops BEFORE the next request (fail-closed, never spends into
    a rejected call).
  - No retries: one provider call per ASIN per run (the contract itself
    de-duplicates in-flight ASINs and serves its 24h cache with zero
    credits on repeats).
  - Resume: ``--resume-from RUN_ID`` reuses a run dir and skips ASINs
    with a normalized file already present (zero re-spend for those).
  - Crash-safe: the ledger streams to ledger.jsonl per iteration and
    summary.json is written in a finally block, so a kill always leaves
    a resumable run dir behind (the exact gap that orphaned the
    201/245 Bright Data run with no summary).
  - stdout is teed to run.log inside the run dir (shell timeouts must
    never again take the only copy of the log with them).

Exit codes:
  0  success (including provider-rejected/unavailable ASINs)
  2  usage / live-gate refusal
  3  run-directory collision or write failure
  4  manifest rejected (before any network path is reachable)
"""

import argparse
import io
import json
import os
import re
import secrets
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import live_gate
import offer_enrichment

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent
CATALOG_DIR = BACKEND_DIR / "data" / "catalog"
COMPLIANT_MANIFEST = CATALOG_DIR / "sourcescout_compliant_manifest.json"
RUNS_BASE_DIR = BACKEND_DIR / "data" / "enrich" / "easyparser-seller"

# Live probe: 1 credit per OFFER call. Reserve 2 per call so provider
# reporting drift can never overrun the operator-approved credit cap.
WORST_CASE_REQUEST_CREDITS = 2
ESTIMATED_CREDITS_PER_ASIN = 1.0

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_iso_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _make_run_id() -> str:
    return "easyparser-seller-%s-%s" % (_now_iso_compact(), secrets.token_hex(2))


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


class _Tee(io.TextIOBase):
    """Mirror stdout to run.log so a killed shell never takes the only log."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            s.write(data)
        return len(data)

    def flush(self):
        for s in self._streams:
            s.flush()


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
    print("easyparser estimated credits (1 per PASS ASIN): %.1f"
          % (len(selected) * ESTIMATED_CREDITS_PER_ASIN))
    print("total compliant-manifest items (incl. FAIL/REVIEW, never enriched): %d"
          % len(m.get("items") or []))
    print("")
    print("NOTE: Easyparser balance is provider-side and finite (probe showed "
          "credits_remaining=99). Size --max-requests/--max-credits against "
          "the live balance; the runner also stops on credits_remaining==0.")
    print("")
    print("planned ASINs (first 40 of %d):" % len(selected))
    for item in selected[:40]:
        print("  %s  %s" % (item.get("asin"), (item.get("title") or "")[:60]))
    if len(selected) > 40:
        print("  ... (+%d more)" % (len(selected) - 40))
    return 0


def run_probe(args) -> int:
    """One live call for exactly one explicitly-passed ASIN (a smoke probe)."""
    asin = (args.asin or "").strip().upper()
    if not ASIN_PATTERN.fullmatch(asin):
        print("probe: REJECTED - invalid/absent ASIN: %r" % (args.asin,))
        return 2
    if not live_gate.live_enabled():
        print("probe: REJECTED - SCANNER_LIVE_ALLOWED is not an explicit "
              "opt-in (1/true/yes/on). Zero network.")
        return 2
    print("probe: EASYPARSER seller roster for %s (exactly one request)" % asin)
    start = time.monotonic()
    payload = offer_enrichment.get_seller_offer_contract(asin)
    elapsed = round(time.monotonic() - start, 3)
    print("probe returned: status=%s offers=%s/%s fba=%s fbm=%s buybox=%s in %.3fs" % (
        payload.get("offer_data_status"), payload.get("offers_returned"),
        payload.get("total_sellers"), payload.get("fba_sellers"),
        payload.get("fbm_sellers"),
        (payload.get("buy_box") or {}).get("seller_name"), elapsed))
    print("credits_used: %s" % payload.get("credits_used"))
    print("credits_remaining: %s" % payload.get("credits_remaining"))
    return 0


def _summarize_and_index(run_dir: Path, run_id: str, selected_count: int,
                         budget: Dict, stop_reason: Optional[str],
                         ledger: List[Dict], args) -> Dict:
    outcome_summary = {
        "available": sum(1 for r in ledger if r["status"] == "available"),
        "partial": sum(1 for r in ledger if r["status"] == "partial"),
        "other": sum(1 for r in ledger if r["status"] not in ("available", "partial")),
    }
    summary = {
        "run_id": run_id,
        "generated_at": _now_iso(),
        "provider": "EASYPARSER",
        "scope": "sourcescout_compliant_manifest PASS only",
        "compliant_pass_count": selected_count,
        "requests_used": budget["requests_used"],
        "requests_cap": args.max_requests,
        "credits_used": round(budget["credits_used"], 1),
        "credits_reported": round(budget["credits_reported"], 1),
        "credits_cap": args.max_credits,
        "provider_credits_remaining_last": budget.get("provider_remaining"),
        "stop_reason": stop_reason,
        "outcome_counts": outcome_summary,
        "enriched_at": _now_iso(),
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
    return summary


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

    m, err = _load_manifest(Path(args.manifest))
    if err:
        print("error: manifest rejected - %s" % err)
        return 4
    selected = _pass_asins(m.get("items") or [])
    plan_err = _validate_plan(selected)
    if plan_err:
        print("error: %s" % plan_err)
        return 4

    if args.resume_from:
        run_id = args.resume_from
        run_dir = RUNS_BASE_DIR / run_id
        if not run_dir.is_dir():
            print("error: --resume-from run dir not found: %s" % run_dir)
            return 3
        print("resuming run dir: %s" % run_dir)
    else:
        run_id = _make_run_id()
        run_dir = RUNS_BASE_DIR / run_id
        if run_dir.exists():
            print("error: run directory already exists; refusing to overwrite: %s" % run_dir)
            return 3
        run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw").mkdir(exist_ok=True)
    (run_dir / "normalized").mkdir(exist_ok=True)

    log_path = run_dir / "run.log"
    log_file = open(log_path, "a", encoding="utf-8")
    old_stdout = sys.stdout
    sys.stdout = _Tee(old_stdout, log_file)
    try:
        return _run_batch_inner(args, run_id, run_dir, selected)
    finally:
        sys.stdout = old_stdout
        try:
            log_file.close()
        except OSError:
            pass


def _apply_asin_filter(order: List[str], args) -> List[str]:
    """Restrict to an explicit allowlist (targeted gap-fill); manifest order kept."""
    wanted = []
    if args.only_asins:
        wanted.extend(a.strip().upper() for a in str(args.only_asins).split(","))
    if args.asin_file:
        try:
            with open(args.asin_file, "r", encoding="utf-8") as f:
                wanted.extend(line.strip().upper() for line in f)
        except OSError as exc:
            return []
    if not wanted:
        return order
    allowed = {a for a in wanted if ASIN_PATTERN.fullmatch(a)}
    return [a for a in order if a in allowed]


def _run_batch_inner(args, run_id: str, run_dir: Path, selected: List[Dict]) -> int:
    print("=== EASYPARSER LIVE SELLER ENRICHMENT (compliant PASS set only) ===")
    print("manifest: %s" % args.manifest)
    print("compliant PASS ASINs (full scope, never >245): %d" % len(selected))
    print("caps: max_requests=%s max_credits=%s" % (args.max_requests, args.max_credits))
    print("run dir: %s" % run_dir)

    order = [str(item.get("asin")).strip().upper() for item in selected]
    order = _apply_asin_filter(order, args)
    if not order:
        print("error: ASIN allowlist (--only-asins/--asin-file) matched zero "
              "PASS ASINs; refusing before any provider call")
        return 2
    budget = {"requests_used": 0, "credits_used": 0.0, "credits_reported": 0.0,
              "provider_remaining": None}
    ledger: List[Dict] = []
    stop_reason: Optional[str] = None

    # Rebuild in-memory ledger tail from streamed ledger.jsonl on resume so
    # outcome counts and budget stay honest across restarts.
    ledger_path = run_dir / "ledger.jsonl"
    if ledger_path.exists():
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        row = json.loads(line)
                        ledger.append(row)
                        budget["requests_used"] += 1
                        try:
                            budget["credits_used"] += float(row.get("credits_this_call") or 0)
                        except (TypeError, ValueError):
                            pass
            print("resumed: %d ledger rows replayed" % len(ledger))
        except (OSError, ValueError) as exc:
            print("error: existing ledger.jsonl unreadable, refusing to continue blind: %s" % exc)
            return 3

    try:
        with open(ledger_path, "a", encoding="utf-8") as ledger_f:
            for idx, asin in enumerate(order, 1):
                if budget["requests_used"] >= args.max_requests:
                    stop_reason = "max_requests"
                    break
                if budget["credits_used"] + WORST_CASE_REQUEST_CREDITS > args.max_credits:
                    stop_reason = "max_credits"
                    break
                if budget.get("provider_remaining") == 0:
                    stop_reason = "provider_balance_exhausted"
                    break

                normalized_path = run_dir / "normalized" / ("%s.json" % asin)
                if normalized_path.exists():
                    continue  # resume skip: zero re-spend for finished ASINs

                started = time.monotonic()
                payload = offer_enrichment.get_seller_offer_contract(asin)
                budget["requests_used"] += 1
                used = payload.get("credits_used")
                credit_kind = "estimated"
                credits_this_call = ESTIMATED_CREDITS_PER_ASIN
                if isinstance(used, (int, float)) and not isinstance(used, bool) and used > 0:
                    budget["credits_used"] += float(used)
                    budget["credits_reported"] += float(used)
                    credits_this_call = float(used)
                    credit_kind = "reported"
                else:
                    budget["credits_used"] += ESTIMATED_CREDITS_PER_ASIN
                remaining = payload.get("credits_remaining")
                if isinstance(remaining, (int, float)) and not isinstance(remaining, bool):
                    budget["provider_remaining"] = remaining

                elapsed = round(time.monotonic() - started, 3)
                status = payload.get("offer_data_status") or "unknown"
                buy_box = payload.get("buy_box") or {}
                row = {
                    "seq": idx,
                    "asin": asin,
                    "started_at": _now_iso(),
                    "finished_at": _now_iso(),
                    "status": status,
                    "credit_basis": credit_kind,
                    "credits_this_call": credits_this_call,
                    "credits_remaining": budget["provider_remaining"],
                    "duration_sec": elapsed,
                }
                ledger.append(row)
                ledger_f.write(json.dumps(row, default=str) + "\n")
                ledger_f.flush()
                _atomic_write(normalized_path, payload)
                _atomic_write(run_dir / "raw" / ("%s.json" % asin), {
                    "asin": asin,
                    "status": status,
                    "offer_data_source": payload.get("offer_data_source"),
                    "fetched_at": payload.get("offer_data_fetched_at"),
                })
                print("  [%3d/%3d] %s -> %-12s sellers=%s fba=%s fbm=%s buybox=%s credits=%.1f bal=%s" % (
                    idx, len(order), asin, status, payload.get("total_sellers"),
                    payload.get("fba_sellers"), payload.get("fbm_sellers"),
                    buy_box.get("seller_name"), credits_this_call,
                    budget["provider_remaining"]))
                time.sleep(0.1)
    except Exception:
        stop_reason = "error: %s" % traceback.format_exc(limit=3).replace("\n", " | ")
        print("RUN ERROR (summary still written, run dir resumable): %s" % stop_reason)
    finally:
        # The 201/245 Bright Data orphan taught this: the summary is ALWAYS
        # written, even on kill-path exceptions, so a run dir is resumable.
        summary = _summarize_and_index(run_dir, run_id, len(selected),
                                       budget, stop_reason, ledger, args)
        print("")
        print("=== SUMMARY ===")
        print("run_id:  %s" % run_id)
        print("scope:   245-PASS compliant manifest (never 470)")
        print("requests/cap:    %d / %s" % (budget["requests_used"], args.max_requests))
        print("credits used/cap: %.1f / %s (reported=%.1f)"
              % (budget["credits_used"], args.max_credits, budget["credits_reported"]))
        print("provider balance last seen: %s" % budget.get("provider_remaining"))
        print("stop_reason: %s" % stop_reason)
        print("outcomes: %s" % summary["outcome_counts"])
        print("artifacts: %s" % run_dir)
        print("")
        print("STOP STATEMENT")
        print("Enriched data is market intelligence only. No ASIN is purchase-")
        print("authorized by this run; a separate invoice-legitimacy + sourcing")
        print("verification step is still required before any order.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Easyparser seller-roster enrichment over the 245-ASIN PASS "
                    "compliant manifest (never the 470 discovery pool).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dry = sub.add_parser("dry-run", help="validate + print plan (zero network)")
    p_dry.add_argument("--manifest", default=str(COMPLIANT_MANIFEST))

    p_probe = sub.add_parser("probe", help="one live seller roster for one ASIN")
    p_probe.add_argument("--asin", required=True)
    p_probe.add_argument("--manifest", default=str(COMPLIANT_MANIFEST))

    p_batch = sub.add_parser("run", help="live batch over the PASS set")
    p_batch.add_argument("--live", action="store_true")
    p_batch.add_argument("--manifest", default=str(COMPLIANT_MANIFEST))
    p_batch.add_argument("--max-requests", type=int, default=None)
    p_batch.add_argument("--max-credits", type=int, default=None)
    p_batch.add_argument("--resume-from", default=None,
                         help="run dir name under data/enrich/easyparser-seller to resume")
    p_batch.add_argument("--only-asins", default=None,
                         help="comma-separated ASIN allowlist (manifest order kept)")
    p_batch.add_argument("--asin-file", default=None,
                         help="path to a file with one ASIN per line (allowlist)")

    args = parser.parse_args(argv)
    if args.cmd == "dry-run":
        return run_dry_run(args)
    if args.cmd == "probe":
        return run_probe(args)
    return run_batch(args)


if __name__ == "__main__":
    sys.exit(main())
