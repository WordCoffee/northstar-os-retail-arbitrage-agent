#!/usr/bin/env python
"""Populate the Scout candidate cache + market snapshot store from real
API-retrieved enrichment run-dir data. ZERO network, zero credentials.

Builds:
  1. data/amazon-market-snapshots.json  (the SCANNER_LOCAL_SNAPSHOT_MERGE
     store) from the Easyparser seller-run normalized files, keyed by ASIN.
  2. The scanner candidate cache (data/scanner-search-cache.json) via
     manual_import.run_import(..., replace=True), so every 245-PASS ASIN
     carries the manual-import marker (``imported_at``) that activates the
     offline candidate overlay in offer_enrichment._offline_offer_from_candidate.

Overlay sources (all local files, never state-changed):
  - Easyparser runs:  data/enrich/easyparser-seller/*/normalized/B<ASIN>.json
                     (seller roster detail: offers, buy_box, seller counts,
                     titles, credits).
  - BrightData runs: data/enrich/brightdata-compliant/*/normalized/B<ASIN>.json
                     (prices, FBA fee, monthly sales, category, browse node).

The merged candidate row uses whatever real values exist; absent values stay
None (never invented). Rows always come from the 245-PASS compliant manifest,
so the Scout pool is exactly the purchase-qualified set.

Usage:
    python populate_scout_offline.py [--dry-run]
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import amazon_search
import manual_import
import market_snapshot_store

_BACKEND = Path(__file__).resolve().parent
_MANIFEST = _BACKEND / "data" / "catalog" / "sourcescout_compliant_manifest.json"
_EP_GLOB = str(_BACKEND / "data" / "enrich" / "easyparser-seller" / "*" / "normalized" / "*.json")
_BD_GLOB = str(_BACKEND / "data" / "enrich" / "brightdata-compliant" / "*" / "normalized" / "*.json")
_CANDIDATES = _BACKEND / "data" / "offline-scout-candidates.json"
SOURCE_LABEL = "offline_import_brightdata_easyparser_2026-09-14"


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _num(value):
    """Non-negative number or None (never invents)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value if value > 0 else None
    try:
        value = float(value)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _int_count(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    try:
        value = int(float(value))
        return value if value >= 0 else None
    except (TypeError, ValueError):
        return None


def _text(value, max_len=400):
    if isinstance(value, str) and value.strip():
        return value.strip()[:max_len]
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Snapshot store (Easyparser roster data via market_snapshot_store)
# ---------------------------------------------------------------------------

def _ep_result_to_snapshot_arc(ep: dict) -> dict:
    """Map an Easyparser normalized file onto market_snapshot_store's
    expected result-fields. The store's build_snapshot() computes observed
    seller counts from returned offer rows only; claimed counts stay claimed.
    """
    buy_box = ep.get("buy_box") if isinstance(ep.get("buy_box"), dict) else {}
    fulfillment = (buy_box.get("fulfillment") or "").strip().upper()
    return {
        "observed_at": ep.get("observed_at"),
        "offers": ep.get("offers") or [],
        "data_gaps": ep.get("data_gaps") or [],
        "buy_box_price": _num(ep.get("buy_box_price") or buy_box.get("price")),
        "buy_box_seller": _text(buy_box.get("seller_name")) or _text(ep.get("buy_box_seller")),
        "buy_box_is_fba": fulfillment == "FBA",
        "buy_box_is_fbm": fulfillment == "FBM",
        "buy_box_condition": buy_box.get("condition"),
        "buy_box_is_prime": buy_box.get("prime"),
        "offers_returned_count": _int_count(ep.get("offers_returned")),
        "offer_count": _int_count(ep.get("offer_count")),
        "observed_fba_offer_count": _int_count(ep.get("fba_sellers")),
        "observed_fbm_offer_count": _int_count(ep.get("fbm_sellers")),
        "observed_amazon_offer_count": _int_count(ep.get("amazon_sellers")),
        "title": _text(ep.get("title"), max_len=500) or None,
        "source": "easyparser",
        "credits_used": _num(ep.get("credits_used")),
        "credits_remaining": _num(ep.get("credits_remaining")),
    }


def _best_ep_file(asin: str) -> dict:
    """Best Easyparser normalized file for an ASIN: prefer fullest roster
    (most offers returned), then newest observed_at."""
    files = sorted(
        glob.glob(str(_BACKEND / "data" / "enrich" / "easyparser-seller" / "*" / "normalized" / f"{asin}.json"))
    )
    best = None
    best_key = None
    for path in files:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                ep = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(ep, dict):
            continue
        returned = _int_count(ep.get("offers_returned")) or 0
        observed = str(ep.get("observed_at") or "")
        key = (returned, len(ep.get("offers") or []), observed)
        if best_key is None or key > best_key:
            best_key = key
            best = ep
    return best or {}


def _best_bd_file(asin: str) -> dict:
    """Newest BrightData normalized file for an ASIN (keyed by filename:
    the payload carries asin: null inside)."""
    files = sorted(
        glob.glob(str(_BACKEND / "data" / "enrich" / "brightdata-compliant" / "*" / "normalized" / f"{asin}.json"))
    )
    best = None
    best_enriched = None
    for path in files:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                bd = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(bd, dict):
            continue
        enriched = str(bd.get("enriched_at") or "")
        if best_enriched is None or enriched > best_enriched:
            best_enriched = enriched
            best = bd
    return best or {}


def _build_snapshot_store(manifest_items: list, dry_run: bool) -> dict:
    """Persist per-ASIN snapshots into the market snapshot store.

    Returns a stats dict: total, saved, skipped, failed.
    """
    stats = {"total": 0, "saved": 0, "skipped": 0, "failed": 0, "details": []}
    for item in manifest_items:
        asin = str(item.get("asin") or "").strip().upper()
        if len(asin) != 10:
            stats["skipped"] += 1
            continue
        ep = _best_ep_file(asin)
        if not ep:
            stats["skipped"] += 1
            continue
        stats["total"] += 1
        if dry_run:
            stats["saved"] += 1
            continue
        arc = _ep_result_to_snapshot_arc(ep)
        snapshot = market_snapshot_store.build_snapshot(asin, arc)
        ok, error = market_snapshot_store.save_snapshot(asin, snapshot)
        if ok:
            stats["saved"] += 1
        else:
            stats["failed"] += 1
            stats["details"].append({"asin": asin, "error": error})
    return stats


# ---------------------------------------------------------------------------
# Candidate cache overlay (manual_import pipeline)
# ---------------------------------------------------------------------------

def _build_candidates(manifest_items: list) -> tuple:
    """One candidate row per 245-PASS ASIN: manifest identity + real overlay
    values from Easyparser and BrightData normalized runs.

    Returns (candidates, overlay_stats)."""
    candidates = []
    stats = {
        "price": 0, "buy_box": 0, "fba_fee": 0, "monthly_sales": 0,
        "total_sellers": 0, "fba_sellers": 0, "category": 0,
        "ep_roster": 0,
    }
    for item in manifest_items:
        asin = str(item.get("asin") or "").strip().upper()
        if len(asin) != 10:
            continue
        bd = _best_bd_file(asin)
        ep = _best_ep_file(asin)

        title = (
            _text(bd.get("title"), max_len=500)
            or _text(ep.get("title"), max_len=500)
            or _text(item.get("title"), max_len=500)
        )
        row = {
            "asin": asin,
            "name": title or asin,
            "product_url": _text(item.get("product_url") or item.get("url")),
        }

        # --- BrightData overlay (real values only) ---
        bd_price = _num(bd.get("amazon_price"))
        bd_buybox = _num(bd.get("buy_box_price"))
        if bd_price is not None:
            row["amazon_price"] = bd_price
            stats["price"] += 1
        if bd_buybox is not None:
            row["buy_box_price"] = bd_buybox
            stats["buy_box"] += 1
        bd_fee = _num(bd.get("fba_fee"))
        if bd_fee is not None:
            row["fba_fee"] = bd_fee
            stats["fba_fee"] += 1
        bd_sales = _num(bd.get("monthly_sales_estimate"))
        if bd_sales is not None:
            row["monthly_sales_estimate"] = bd_sales
            row["monthly_sales_estimated"] = bool(bd.get("monthly_sales_estimated", True))
            stats["monthly_sales"] += 1
        bd_total = _int_count(bd.get("total_sellers"))
        bd_fba = _int_count(bd.get("fba_sellers"))
        if bd_total is not None or bd_fba is not None:
            row["total_sellers"] = bd_total
            row["fba_sellers"] = bd_fba
            if bd_total is not None:
                stats["total_sellers"] += 1
            if bd_fba is not None:
                stats["fba_sellers"] += 1
        bd_category = _text(bd.get("amazon_category"), max_len=120)
        bd_node = _int_count(bd.get("browse_node_id"))
        if bd_category or bd_node is not None:
            row["amazon_category"] = bd_category
            row["browse_node_id"] = bd_node
            row["category_source_hint"] = (
                _text(bd.get("category_source_hint"), max_len=60)
                or "structured_category"
            )
            stats["category"] += 1

        # --- Easyparser roster overlay (only where BrightData is silent) ---
        ep_total, ep_fba = _int_count(ep.get("total_sellers")), _int_count(ep.get("fba_sellers"))
        if "total_sellers" not in row and ep_total is not None:
            row["total_sellers"] = ep_total
            stats["total_sellers"] += 1
        if "fba_sellers" not in row and ep_fba is not None:
            row["fba_sellers"] = ep_fba
            stats["fba_sellers"] += 1
        bb = ep.get("buy_box") if isinstance(ep.get("buy_box"), dict) else {}
        if "buy_box_price" not in row:
            bb_price = _num(ep.get("buy_box_price") or bb.get("price"))
            if bb_price is not None:
                row["buy_box_price"] = bb_price
                stats["buy_box"] += 1
        if not bd and len(ep.get("offers") or []) > 0:
            stats["ep_roster"] += 1

        # observed_at: newest real observation available
        observed = [o for o in
                    (_text(bd.get("enriched_at")), _text(ep.get("observed_at")))
                    if o]
        if observed:
            row["observed_at"] = max(observed)

        candidates.append(row)
    return candidates, stats


def _write_candidates(candidates: list, dry_run: bool) -> str:
    path = str(_CANDIDATES)
    if dry_run:
        return path
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"candidates": candidates}, f, indent=2, ensure_ascii=False)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="validate/plan without writing any files")
    args = parser.parse_args()

    if not _MANIFEST.exists():
        print("error: compliant manifest missing: %s" % _MANIFEST)
        return 4
    manifest = _load_json(_MANIFEST)
    items = manifest.get("items") or []
    if not items:
        print("error: manifest has no items")
        return 4
    print("manifest items:           %d" % len(items))

    # --- 1. Snapshot store ---
    snap_stats = _build_snapshot_store(items, args.dry_run)
    print("snapshot store:           total=%d saved=%d skipped=%d failed=%d" % (
        snap_stats["total"], snap_stats["saved"], snap_stats["skipped"], snap_stats["failed"]))
    if snap_stats["details"] and not args.dry_run:
        for d in snap_stats["details"][:5]:
            print("  snapshot save failed:   %s -> %s" % (d["asin"], d["error"]))

    # --- 2. Candidate cache ---
    candidates, overlay = _build_candidates(items)
    print("candidate rows:           %d" % len(candidates))
    print("overlay (real values):    price=%d buy_box=%d fba_fee=%d monthly_sales=%d "
          "total_sellers=%d fba_sellers=%d category=%d ep_roster_only=%d" % (
        overlay["price"], overlay["buy_box"], overlay["fba_fee"],
        overlay["monthly_sales"], overlay["total_sellers"],
        overlay["fba_sellers"], overlay["category"], overlay["ep_roster"]))

    path = _write_candidates(candidates, args.dry_run)
    if args.dry_run:
        print("dry-run: no files written. Candidates staged at %s" % path)
        return 0

    report = manual_import.run_import(
        input_path=path,
        source_label=SOURCE_LABEL,
        replace=True,
    )
    counts = report.get("counts") or {}
    print("manual_import status:     %s" % report.get("status"))
    print("input_rows:               %d" % counts.get("input_rows", 0))
    print("accepted:                 %d" % counts.get("accepted", 0))
    print("rejected:                 %s" % report.get("rejected_rows", []))
    if report.get("status") != "ok":
        print("notes:                    %s" % "; ".join(report.get("notes", [])))
        return 2

    # --- 3. Verify ---
    snapshots = market_snapshot_store.load_snapshots()
    print("snapshot store verified:  %d ASINs" % len(snapshots))
    cache = amazon_search._read_cache_file()
    if isinstance(cache, dict):
        print("candidate cache verified: %d products (source=%r)" % (
            cache.get("candidate_count"), cache.get("source")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())