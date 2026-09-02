"""enricher.py — narrow, read-only integration layer for existing sources
and existing deterministic engines.

This module is intentionally NOT a policy engine and makes NO live provider
calls (no DataForSEO POST/GET, no RapidAPI, no Costco network). It:

  * reads existing waterfall run artifacts from disk (never mutates them),
  * extracts only fields actually present in those artifacts,
  * calls the FROZEN core engines (fee_engine, demand_estimator,
    product_analysis) as read-only dependencies,
  * identifies which fields are missing and would require a later,
    separately authorized live provider check (emitted as provider_gap
    records),
  * returns structured results to brain_orchestrator.py.

It never writes to the primary cache; only the Master Brain may do that,
and only after validation.
"""

import glob
import json
import os
from datetime import datetime, timezone

import fee_engine
import demand_estimator
import product_analysis
from waterfall_run import extract_product, map_sellers_result

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
WATERFALL_ROOT = os.path.join(BACKEND_DIR, "data", "enrich", "waterfall-runs")
MANIFEST_PATH = os.path.join(BACKEND_DIR, "data", "enrich", "live-10asin-manifest.json")
RUN_LOG_GLOB = "run-log.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def discover_latest_run(run_root: str = WATERFALL_ROOT) -> str:
    """Return the path to the newest completed waterfall run directory.

    Selection is by the run-log `started_at` timestamp (UTF-8 safe) when
    available, else by directory modification time. Never mutates anything.
    """
    if not os.path.isdir(run_root):
        raise SystemExit(f"no waterfall runs at {run_root}")
    candidates = []
    for d in sorted(os.listdir(run_root)):
        full = os.path.join(run_root, d)
        if not os.path.isdir(full) or not d.startswith("waterfall-"):
            continue
        log_path = os.path.join(full, RUN_LOG_GLOB)
        started = None
        if os.path.isfile(log_path):
            try:
                with open(log_path, encoding="utf-8") as fh:
                    log = json.load(fh)
                started = log.get("started_at")
            except (ValueError, OSError):
                started = None
        candidates.append((started or "", os.path.getmtime(full), full))
    if not candidates:
        raise SystemExit("no waterfall run directories found")
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return candidates[0][2]


def load_run_log(run_dir: str) -> dict:
    path = os.path.join(run_dir, RUN_LOG_GLOB)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:  # UTF-8: run-log may carry unicode
        return json.load(fh)


def load_cohort(asins: list = None) -> list:
    """The 10-ASIN benchmark cohort (canonical order from the frozen manifest)."""
    if asins:
        return list(asins)
    with open(MANIFEST_PATH, encoding="utf-8-sig") as fh:
        manifest = json.load(fh)
    order = manifest.get("canonical_asin_order")
    if order:
        return list(order)
    return [a.get("asin") for a in manifest.get("asins", [])]


def _load_raw(path: str):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return None


def extract_tier1(tier1_raw: dict) -> dict:
    """Product dict from a saved Tier-1 asin task_get response, else None."""
    if not isinstance(tier1_raw, dict):
        return None
    return extract_product(tier1_raw.get("get"))


def extract_tier2(tier2_raw: dict) -> dict:
    """Seller-roster dict from a saved Tier-2 sellers task_get response."""
    if not isinstance(tier2_raw, dict):
        return {"sellers_count": None, "sellers": [],
                "buybox_winner": "Unavailable", "is_fba": "Unavailable"}
    return map_sellers_result(tier2_raw.get("get"))


def load_asin_artifacts(run_dir: str, asin: str) -> dict:
    raw1 = _load_raw(os.path.join(run_dir, "raw", f"{asin}-tier1.json"))
    raw2 = _load_raw(os.path.join(run_dir, "raw", f"{asin}-tier2.json"))
    product = extract_tier1(raw1)
    sellers = extract_tier2(raw2)
    if product is None:
        return {"asin": asin, "present": False, "product": None, "sellers": sellers}
    from waterfall_run import map_asin_result
    obs = map_asin_result(product)
    return {
        "asin": asin,
        "present": True,
        "run_observed_at": _utc_now(),
        "title": obs.get("title"),
        "brand": obs.get("brand"),
        "price": obs.get("price"),
        "rating_value": obs.get("rating_value"),
        "reviews_count": obs.get("reviews_count"),
        "image_url": None,
        "seller_count": sellers.get("sellers_count"),
        "sellers": sellers.get("sellers", []),
        "tier2_present": raw2 is not None,
    }


def resolve_costco(title: str, asin: str) -> dict:
    return product_analysis.get_costco_price(title or "", amazon_asin=asin) or {}


def compute_economics(amazon_price, costco_cost, costco_basis) -> dict:
    return fee_engine.calculate_unit_economics(
        product={
            "amazon_price": amazon_price,
            "amazon_category": None,
            "browse_node": None,
            "category_source_hint": None,
            "package_weight_lbs": None,
            "item_weight_lbs": None,
            "package_dimensions_in": None,
            "listing_fba_fee": None,
        },
        costco={"costco_cost": costco_cost,
                "costco_cost_basis": costco_basis or "unavailable"},
    )


def compute_demand() -> dict:
    """Demand requires a verified BSR; artifacts have none, so this returns
    the honest 'unknown' estimate object (no fabrication)."""
    return demand_estimator.estimate_demand(None, None)


def identify_gaps(asin: str, extracted: dict, economics: dict,
                  costco: dict, policy: dict) -> list:
    """Emit provider_gap records for every field that is missing and would
    need a later, separately authorized live provider check. RapidAPI is
    explicitly NOT assumed usable (tested host was unsubscribed)."""
    gaps = []
    rapidapi_status = "tier3_host_unsubscribed"  # historical: tested host dead

    def gap(field, reason, recommended_source_class, paid_live_required):
        gaps.append({
            "field": field,
            "asin": asin,
            "reason": reason,
            "recommended_source_class": recommended_source_class,
            "paid_live_required": paid_live_required,
            "rapidapi_status": rapidapi_status,
            "auto_triggered": False,
            "note": "requires separate explicit authorization; not auto-dispatched",
        })

    if extracted.get("price") is None:
        gap("amazon_price", "DataForSEO asin task did not return a price",
            "live_dataforseo", True)
    if extracted.get("seller_count") is None:
        gap("seller_count", "DataForSEO sellers task missing",
            "live_dataforseo", True)
    gap("bsr", "BSR not returned by DataForSEO asin task",
        "live_dataforseo_or_future_authorized", True)
    gap("category", "category not returned by DataForSEO asin task",
        "live_dataforseo_or_future_authorized", True)
    gap("dimensions", "package dimensions not in artifacts",
        "amazon_revenue_calculator_or_manual", False)
    gap("buybox_winner", "seller roster did not expose Buy Box winner",
        "future_authorized_provider", True)
    gap("is_fba", "FBA flag not exposed by DataForSEO sellers task",
        "future_authorized_provider", True)
    gap("is_fbm", "FBM flag not exposed by DataForSEO sellers task",
        "future_authorized_provider", True)
    if economics.get("fba_fee") is None:
        gap("fba_fee", "FBA fee unavailable (no weight/dimensions)",
            "amazon_revenue_calculator_or_manual", False)
    if not (costco and costco.get("costco_cost") is not None):
        gap("costco_acquisition_price", "no Costco catalog match",
            "costco_catalog_internal", False)
    return gaps


def enrich_asin(asin: str, run_dir: str, policy: dict) -> dict:
    extracted = load_asin_artifacts(run_dir, asin)
    if not extracted.get("present"):
        return {
            "asin": asin,
            "present": False,
            "extracted": extracted,
            "engines": {"economics": {}, "demand": compute_demand(), "costco": {}},
            "gaps": [{
                "field": "all", "asin": asin,
                "reason": "Tier-1 asin artifact not present in this run",
                "recommended_source_class": "live_dataforseo",
                "paid_live_required": True, "rapidapi_status": "tier3_host_unsubscribed",
                "auto_triggered": False,
                "note": "requires separate explicit authorization",
            }],
        }
    costco = resolve_costco(extracted.get("title") or "", asin)
    economics = compute_economics(
        extracted.get("price"),
        costco.get("costco_cost"),
        costco.get("costco_cost_basis"),
    )
    demand = compute_demand()
    gaps = identify_gaps(asin, extracted, economics, costco, policy)
    return {
        "asin": asin,
        "present": True,
        "extracted": extracted,
        "engines": {"economics": economics, "demand": demand, "costco": costco},
        "gaps": gaps,
    }


def enrich_cohort(run_dir: str, asins: list, policy: dict) -> list:
    return [enrich_asin(asin, run_dir, policy) for asin in asins]


if __name__ == "__main__":
    run_dir = discover_latest_run()
    asins = load_cohort()
    print(f"latest run: {run_dir}")
    print(f"cohort size: {len(asins)}")
    for asin in asins:
        a = load_asin_artifacts(run_dir, asin)
        print(f"  {asin}: present={a.get('present')} price={a.get('price')} "
              f"sellers={a.get('seller_count')}")
