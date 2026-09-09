"""Unified Costco item-detail runner — provider redundancy + full-pull.

Operational successor to the removed Unwrangle detail path. Chooses between
gated free-tier detail providers in priority order:

  BRIGHTDATA_WEB_UNLOCKER  (primary)   Bright Data Web Unlocker — 5,000 free
                                       credits/month recurring (resets the
                                       1st), no card, 1 credit/request,
                                       hard stop at 0. Proven in this repo on
                                       the frozen discovery batch.
  FIRECRAWL                (fallback)  Firecrawl Scrape API — 1,000 free
                                       pages/month recurring on the $0 plan,
                                       no card. See firecrawl_costco.py.

Unwrangle is REMOVED (2026-09): its no-card free tier is gone; paid plans
start at $99/mo. See costco_api_client.py for the catalog-layer removal.

Failover rules (circuit breaker, never silent):
  - AUTO: start on the first enabled provider in priority order. On the FIRST
    HARD failure of the current provider (auth_error / http_error /
    transport_error / config_error / rate_limited / credits_exhausted /
    malformed_response — i.e. the provider's batch result is 'halted'), switch
    to the next enabled provider and REWIND the failed item onto it. If EVERY
    enabled provider hard-fails on the same item, halt the whole batch.
  - Provider budgets (--provider-budget NAME=N,...) cap how many items each
    provider serves; once a provider hits its budget the remaining items roll
    to the next provider. When all enabled providers are budget-exhausted,
    remaining items are recorded as skipped (budget_exhausted). When the
    circuit breaker halts the batch, not-yet-attempted items are recorded as
    skipped (halted) — never silently dropped. In every path
    items_requested == items_fetched + items_failed + len(skipped).
  - SOFT per-item failures (url_not_found / no_data_found) do NOT switch
    providers and do NOT halt — they are recorded and the batch continues.

Gates (fail-closed, per provider, default OFF): each is independently
enabled by its gate env AND key presence:
  BRIGHTDATA_COSTCO_DETAIL_ENABLED=1 + BRIGHTDATA_UNLOCKER_API_KEY
  FIRECRAWL_COSTCO_DETAIL_ENABLED=1  + FIRECRAWL_API_KEY
If no provider is enabled the runner returns a 'blocked' summary — zero
network calls.

Full pull:
  build-manifest --from-csv <master price capture CSV> turns the portfolio
  CSV (ASIN + Costco candidate item number/title/brand/pack columns) into a
  full-pull manifest. Rows without an item number land in `pending_lookup`
  (resolved by the separate gated bright_data_costco_lookup.py step — live,
  needs its own approval) rather than being fabricated.
  full-pull --manifest <json> runs the items with automatic failover, an
  optional --skip-fresh-days freshness window (against the merged
  data/costco-product-detail.json store), optional provider budgets, and a
  --dry-run planner (zero network). Evidence is written to the same frozen
  discovery run directory by default, so kirkland_costco_merge.py picks it up
  with its existing run_merge() call.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

import bright_data_costco
import firecrawl_costco

RUN_ID = bright_data_costco.RUN_ID
DEFAULT_RUN_DIR = bright_data_costco.DEFAULT_RUN_DIR

# Provider registry: display label -> (module, gate env, key env).
PROVIDER_ORDER: tuple = ("BRIGHTDATA_WEB_UNLOCKER", "FIRECRAWL")
_PROVIDER_MODULES = {
    "BRIGHTDATA_WEB_UNLOCKER": bright_data_costco,
    "FIRECRAWL": firecrawl_costco,
}
_PROVIDER_GATES = {
    "BRIGHTDATA_WEB_UNLOCKER": "BRIGHTDATA_COSTCO_DETAIL_ENABLED",
    "FIRECRAWL": "FIRECRAWL_COSTCO_DETAIL_ENABLED",
}
_PROVIDER_KEYS = {
    "BRIGHTDATA_WEB_UNLOCKER": "BRIGHTDATA_UNLOCKER_API_KEY",
    "FIRECRAWL": "FIRECRAWL_API_KEY",
}

SOFT_FAILURE_TYPES = ("url_not_found", "no_data_found")


# ---------------------------------------------------------------------------
# Provider status / gating (presence-only — never credential values)
# ---------------------------------------------------------------------------
def _key_present(provider: str) -> bool:
    return bool(os.getenv(_PROVIDER_KEYS[provider], "").strip())


def _gate_on(provider: str) -> bool:
    return os.getenv(_PROVIDER_GATES[provider], "0").strip().upper() == "1"


def _provider_enabled(provider: str) -> bool:
    return _gate_on(provider) and _key_present(provider)


def provider_status() -> List[Dict]:
    """Presence-only connectivity report for every known provider."""
    out = []
    for provider in PROVIDER_ORDER:
        out.append(
            {
                "provider": provider,
                "enabled": _provider_enabled(provider),
                "gate_env": _PROVIDER_GATES[provider],
                "gate": _gate_on(provider),
                "key_configured": _key_present(provider),
                "priority": PROVIDER_ORDER.index(provider) + 1,
            }
        )
    return out


def _active_providers(providers) -> List[str]:
    return [p for p in providers if p in _PROVIDER_MODULES and _provider_enabled(p)]


def _parse_budgets(spec) -> Dict[str, Optional[int]]:
    """Accept a dict or a 'NAME=N,NAME=M' string; returns name->int-or-None."""
    if spec is None:
        return {}
    if isinstance(spec, dict):
        def _to_int(v):
            if v is None or (isinstance(v, str) and not v.strip()):
                return None
            return int(v)
        return {str(k).strip(): _to_int(v) for k, v in spec.items()}
    budgets: Dict[str, Optional[int]] = {}
    for part in str(spec).split(","):
        part = part.strip().upper()
        if not part:
            continue
        if "=" in part:
            name, _, value = part.partition("=")
            name = name.strip()
            try:
                budgets[name] = int(value.strip()) if value.strip() else None
            except ValueError:
                raise ValueError(
                    "invalid provider budget %r (expected NAME=N)" % part
                )
        else:
            raise ValueError(
                "invalid provider budget %r (expected NAME=N,NAME=M)" % part
            )
    return budgets


# ---------------------------------------------------------------------------
# Detail refresh with provider failover
# ---------------------------------------------------------------------------
def refresh_product_details(
    item_ids: List[str],
    provider: str = "auto",
    providers: Optional[tuple] = None,
    budgets: Optional[Dict[str, Optional[int]]] = None,
    manifest_path: Optional[str] = None,
    run_dir: Optional[str] = None,
    delay: Optional[float] = None,
) -> Dict:
    """Fetch item details across gated providers with automatic failover.

    ``provider`` is "auto" (priority order, fail over on hard failure) or a
    specific provider name. ``budgets`` caps items per provider.
    """
    ids = [str(i).strip() for i in (item_ids or []) if str(i).strip()]
    ordered = list(providers or PROVIDER_ORDER)
    ordered = [p for p in ordered if p in _PROVIDER_MODULES]

    if provider != "auto":
        if provider not in _PROVIDER_MODULES:
            return {
                "status": "blocked",
                "reason": f"unknown provider {provider!r}",
                "provider": provider,
                "items_requested": len(ids),
                "items_fetched": 0,
                "items_failed": 0,
                "items": [],
                "failures": [],
                "evidence_paths": [],
                "failover_events": [],
                "skipped": [],
            }
        ordered = [provider]

    budgets = _parse_budgets(budgets)
    active = _active_providers(ordered)
    if not active:
        return {
            "status": "blocked",
            "reason": "no costco detail provider is enabled",
            "provider": provider,
            "gates": provider_status(),
            "items_requested": len(ids),
            "items_fetched": 0,
            "items_failed": 0,
            "items": [],
            "failures": [],
            "evidence_paths": [],
            "failover_events": [],
            "skipped": [],
        }

    delay = max(0.0, float(delay if delay is not None else 2.0))
    counts = {p: 0 for p in active}
    used: List[str] = []
    failover_events: List[Dict] = []
    items: List[Dict] = []
    failures: List[Dict] = []
    evidence_paths: List[str] = []
    skipped: List[Dict] = []
    halted_reason: Optional[str] = None
    total = len(ids)

    current_idx = 0  # first provider to try for the CURRENT item; advances on failover/budget
    for idx, item_id in enumerate(ids):
        if idx > 0:
            time.sleep(delay)

        resolved = False
        for attempt_idx in range(current_idx, len(active)):
            candidate = active[attempt_idx]
            budget = budgets.get(candidate)
            if budget is not None and counts[candidate] >= budget:
                # This provider is spent for the rest of the batch.
                current_idx = attempt_idx + 1
                failover_events.append(
                    {
                        "item_id": item_id,
                        "from": candidate,
                        "to": active[attempt_idx + 1] if attempt_idx + 1 < len(active) else None,
                        "reason": "budget_exhausted",
                    }
                )
                continue

            counts[candidate] += 1
            if candidate not in used:
                used.append(candidate)

            result = _PROVIDER_MODULES[candidate].refresh_product_details(
                [item_id],
                manifest_path=manifest_path,
                run_dir=run_dir,
                delay=None,  # runner owns pacing
            )

            if result.get("status") == "halted":
                # Current provider hard-failed. If it was the last active
                # provider, the item is genuinely unreachable -> halt.
                if attempt_idx == len(active) - 1:
                    failures.extend(result.get("failures") or [])
                    evidence_paths.extend(result.get("evidence_paths") or [])
                    stopped = (result.get("failures") or [{}])[0].get("failure_type")
                    halted_reason = (
                        f"all providers failed on item {item_id}: {stopped}"
                    )
                    print(halted_reason)
                    resolved = True  # halt below
                    break
                current_idx = attempt_idx + 1
                failed_type = (result.get("failures") or [{}])[0].get(
                    "failure_type", "hard_failure"
                )
                failover_events.append(
                    {
                        "item_id": item_id,
                        "from": candidate,
                        "to": active[attempt_idx + 1],
                        "reason": f"hard_failure:{failed_type}",
                    }
                )
                print(
                    f"[{idx + 1}/{total}] item {item_id} {failed_type} on "
                    f"{candidate} — failing over to {active[attempt_idx + 1]}."
                )
                continue

            items.extend(result.get("items") or [])
            evidence_paths.extend(result.get("evidence_paths") or [])
            resolved = True
            break

        if halted_reason:
            # Circuit breaker: record every NOT-yet-attempted item as explicitly
            # skipped so items_requested == items_fetched + items_failed +
            # len(skipped). The halted item itself is already counted in
            # `failures` (from the last provider that tried it).
            for _sid in ids[idx + 1:]:
                skipped.append({"item_id": str(_sid).strip(), "reason": "halted"})
            break
        if not resolved:
            skipped.append(
                {
                    "item_id": item_id,
                    "reason": "budget_exhausted",
                    "providers_available": active,
                }
            )

    status = "halted" if halted_reason else (
        "completed" if items or not skipped else "budget_exhausted"
    )
    summary = {
        "status": status,
        "provider": provider,
        "providers_active": active,
        "providers_used": used,
        "provider_counts": {
            p: counts.get(p, 0) for p in (ordered)
        },
        "failover_events": failover_events,
        "run_id": RUN_ID,
        "items_requested": total,
        "items_fetched": len(items),
        "items_failed": len(failures),
        "items_soft_failed": sum(
            1
            for it in items
            if it.get("identity_match_status") in SOFT_FAILURE_TYPES
        ),
        "items_budget_skipped": len(
            [s for s in skipped if s.get("reason") == "budget_exhausted"]
        ),
        "items_halted_skipped": len(
            [s for s in skipped if s.get("reason") == "halted"]
        ),
        "halted_reason": halted_reason,
        "gates": provider_status(),
        "items": items,
        "failures": failures,
        "skipped": skipped,
        "evidence_paths": evidence_paths,
    }
    return summary


# ---------------------------------------------------------------------------
# Full-pull manifest building + execution
# ---------------------------------------------------------------------------
_FULL_PULL_COLUMNS = {
    "item_number": "Costco candidate item number",
    "asin": "ASIN",
    "amazon_title": "Exact Amazon title",
    "amazon_brand": "Amazon brand",
    "costco_title": "Costco candidate title",
    "costco_pack": "Costco candidate pack / size / count",
}


def build_full_pull_manifest(
    csv_path: str,
    out_path: Optional[str] = None,
    max_items: Optional[int] = None,
) -> Dict:
    """Turn the master price capture CSV into a full-pull manifest.

    Rows with a Costco candidate item number become fetchable items (deduped
    by item id, mapped ASINs merged). Rows without one land in
    ``pending_lookup`` (they need the separate gated lookup step) and are
    NEVER fabricated here.
    """
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    items_by_id: Dict[str, Dict] = {}
    pending_lookup: List[Dict] = []

    for row in rows:
        item_id = str(row.get(_FULL_PULL_COLUMNS["item_number"]) or "").strip()
        asin = str(row.get(_FULL_PULL_COLUMNS["asin"]) or "").strip()
        amazon_title = str(row.get(_FULL_PULL_COLUMNS["amazon_title"]) or "").strip()
        amazon_brand = str(row.get(_FULL_PULL_COLUMNS["amazon_brand"]) or "").strip()
        costco_title = str(row.get(_FULL_PULL_COLUMNS["costco_title"]) or "").strip()
        costco_pack = str(row.get(_FULL_PULL_COLUMNS["costco_pack"]) or "").strip()

        if item_id:
            entry = items_by_id.setdefault(
                item_id,
                {
                    "item_id": item_id,
                    "requested_title": costco_title or amazon_title,
                    "requested_brand": (
                        "Kirkland Signature"
                        if "kirkland" in amazon_brand.lower()
                        else (amazon_brand or None)
                    ),
                    "requested_pack": costco_pack or None,
                    "mapped_asins": [],
                },
            )
            if not entry["requested_title"]:
                entry["requested_title"] = costco_title or amazon_title
            if asin and asin not in entry["mapped_asins"]:
                entry["mapped_asins"].append(asin)
        else:
            pending_lookup.append(
                {
                    "asin": asin,
                    "amazon_title": amazon_title,
                    "reason": "no_costco_item_number",
                }
            )

    items = list(items_by_id.values())
    if max_items is not None and max_items >= 0:
        items = items[:max_items]

    manifest = {
        "schema_version": 2,
        "kind": "costco_full_pull_manifest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": os.path.basename(csv_path),
        "count": len(items),
        "pending_lookup_count": len(pending_lookup),
        "items": items,
        "pending_lookup": pending_lookup,
    }

    if out_path:
        out_path = os.path.abspath(out_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        manifest["manifest_path"] = out_path
    return manifest


def _load_full_pull_manifest(manifest_path: str) -> Dict:
    with open(manifest_path, "r", encoding="utf-8-sig") as fh:
        manifest = json.load(fh)
    return manifest


def _freshness_store_paths() -> List[str]:
    """Merged layer-2 store candidates (repo root, then Northstar_backend)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(here, "..", "data", "costco-product-detail.json"),
        os.path.join(here, "data", "costco-product-detail.json"),
    ]


def _recent_capture_dates() -> Dict[str, str]:
    """item_id -> most recent captured_at (ISO) across the merged stores."""
    latest: Dict[str, str] = {}
    for path in _freshness_store_paths():
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                records = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue
        for rec in records or []:
            item_id = str(rec.get("costco_item_id") or "").strip()
            captured_at = str(rec.get("captured_at") or rec.get("fetched_at") or "")
            if item_id and captured_at:
                if item_id not in latest or captured_at > latest[item_id]:
                    latest[item_id] = captured_at
    return latest


def _fresh_run_dir() -> str:
    """A NEW timestamped evidence run dir (same base as DEFAULT_RUN_DIR but
    per-pull), so a full pull never mixes its evidence in with the frozen
    discovery run directory. The merge scans the whole
    data/costco-discovery-runs/ root, so it picks these up automatically."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return os.path.join("data", "costco-discovery-runs", ts)


def full_pull(
    manifest_path: str,
    provider: str = "auto",
    providers: Optional[tuple] = None,
    budgets: Optional[Dict[str, Optional[int]]] = None,
    skip_fresh_days: Optional[int] = None,
    dry_run: bool = False,
    run_dir: Optional[str] = None,
    delay: Optional[float] = None,
) -> Dict:
    """Run (or plan) a full pull from a full-pull manifest.

    ``skip_fresh_days`` skips items whose most recent capture in the merged
    layer-2 store is newer than N days. ``dry_run=True`` returns the plan with
    ZERO network calls. Evidence defaults to a NEW timestamped run dir per pull
    (``--run-dir`` overrides); latest-wins per item in the merge.
    """
    run_dir = run_dir or _fresh_run_dir()
    manifest = _load_full_pull_manifest(manifest_path)
    items = manifest.get("items") or []
    pending_lookup = manifest.get("pending_lookup") or []
    item_ids = [str(it.get("item_id", "")).strip() for it in items if it.get("item_id")]

    skipped_fresh: List[Dict] = []
    to_fetch = item_ids
    if skip_fresh_days is not None and skip_fresh_days > 0:
        recent = _recent_capture_dates()

        def _fresh(item_id: str) -> bool:
            captured = recent.get(item_id)
            if not captured:
                return False
            try:
                captured_dt = datetime.fromisoformat(captured.replace("Z", "+00:00"))
            except ValueError:
                return False
            age_days = (
                datetime.now(timezone.utc) - captured_dt
            ).total_seconds() / 86400.0
            return age_days <= float(skip_fresh_days)

        kept = []
        for item_id in item_ids:
            if _fresh(item_id):
                skipped_fresh.append({"item_id": item_id, "reason": "fresh_within_window"})
            else:
                kept.append(item_id)
        to_fetch = kept

    plan = {
        "manifest_path": manifest_path,
        "manifest_items": len(items),
        "pending_lookup_count": len(pending_lookup),
        "item_ids_in_manifest": item_ids,
        "to_fetch": to_fetch,
        "skipped_fresh": skipped_fresh,
        "providers": provider_status(),
        "active_providers": _active_providers(list(providers or PROVIDER_ORDER)),
        "budgets": _parse_budgets(budgets),
        "estimated_credits": {
            p: len(to_fetch) for p in _active_providers(list(providers or PROVIDER_ORDER))
        },
        "dry_run": bool(dry_run),
    }

    if dry_run:
        plan["status"] = "planned"
        plan["network_calls"] = 0
        return plan

    if not to_fetch:
        return {
            **plan,
            "status": "completed",
            "items_requested": len(to_fetch),
            "items_fetched": 0,
            "items_failed": 0,
            "items": [],
            "failures": [],
            "skipped": skipped_fresh,
            "evidence_paths": [],
            "failover_events": [],
        }

    summary = refresh_product_details(
        item_ids=to_fetch,
        provider=provider,
        providers=list(providers or PROVIDER_ORDER),
        budgets=budgets,
        manifest_path=manifest_path,
        run_dir=run_dir,
        delay=delay,
    )
    summary.update(
        {
            "manifest_path": manifest_path,
            "pending_lookup_count": len(pending_lookup),
            "skipped_fresh": skipped_fresh,
        }
    )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli(argv=None):
    parser = argparse.ArgumentParser(
        prog="costco_live_runner.py",
        description=(
            "Unified Costco item-detail runner: gated free-tier providers "
            "(BRIGHTDATA_WEB_UNLOCKER primary, FIRECRAWL fallback) with "
            "automatic failover, budgets, and full-pull orchestration."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show provider gates/key presence (read-only)")

    details = sub.add_parser("details", help="item-detail operations")
    details_sub = details.add_subparsers(dest="details_command", required=True)
    refresh = details_sub.add_parser("refresh", help="refresh item details (live, gated)")
    refresh.add_argument("--item-ids", nargs="+", required=True, help="Costco item numbers")
    refresh.add_argument(
        "--provider",
        default="auto",
        help="auto | BRIGHTDATA_WEB_UNLOCKER | FIRECRAWL",
    )
    refresh.add_argument(
        "--provider-budget",
        default=None,
        help="comma list NAME=N (e.g. BRIGHTDATA_WEB_UNLOCKER=100,FIRECRAWL=50)",
    )
    refresh.add_argument(
        "--expected-json",
        default=None,
        help="manifest-style JSON with requested_title/requested_brand/requested_pack",
    )
    refresh.add_argument(
        "--run-dir",
        default=None,
        help="evidence run directory (default: frozen 20260828T021658Z discovery run)",
    )
    refresh.add_argument("--delay", type=float, default=None)

    build = sub.add_parser("build-manifest", help="build a full-pull manifest from a CSV")
    build.add_argument("--from-csv", required=True, help="master price capture CSV path")
    build.add_argument("--out", default=None, help="output JSON path")
    build.add_argument("--max-items", type=int, default=None, help="cap item count (trial)")

    pull = sub.add_parser("full-pull", help="plan or run the full portfolio pull")
    pull.add_argument("--manifest", required=True, help="full-pull manifest JSON")
    pull.add_argument("--dry-run", action="store_true", help="plan only — zero network")
    pull.add_argument("--provider", default="auto", help="auto | provider name")
    pull.add_argument(
        "--provider-budget",
        default=None,
        help="comma list NAME=N (e.g. BRIGHTDATA_WEB_UNLOCKER=150,FIRECRAWL=50)",
    )
    pull.add_argument(
        "--skip-fresh-days",
        type=int,
        default=None,
        help="skip items captured within N days in the merged store",
    )
    pull.add_argument("--run-dir", default=None, help="evidence run directory")
    pull.add_argument("--delay", type=float, default=None)

    args = parser.parse_args(argv)

    if args.command == "status":
        print(json.dumps({"providers": provider_status()}, indent=2))
        return 0

    if args.command == "details":
        if args.details_command != "refresh":
            parser.error("only 'details refresh' is implemented")
        summary = refresh_product_details(
            item_ids=args.item_ids,
            provider=args.provider,
            budgets=_parse_budgets(args.provider_budget),
            manifest_path=args.expected_json,
            run_dir=args.run_dir,
            delay=args.delay,
        )
        print(json.dumps(summary, indent=2, default=str))
        return 0

    if args.command == "build-manifest":
        manifest = build_full_pull_manifest(
            csv_path=args.from_csv,
            out_path=args.out,
            max_items=args.max_items,
        )
        print(json.dumps(manifest, indent=2, default=str))
        return 0

    if args.command == "full-pull":
        if not os.path.exists(args.manifest):
            print("full-pull manifest not found: %s" % args.manifest, file=sys.stderr)
            return 2
        summary = full_pull(
            manifest_path=args.manifest,
            provider=args.provider,
            budgets=_parse_budgets(args.provider_budget),
            skip_fresh_days=args.skip_fresh_days,
            dry_run=args.dry_run,
            run_dir=args.run_dir,
            delay=args.delay,
        )
        print(json.dumps(summary, indent=2, default=str))
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())