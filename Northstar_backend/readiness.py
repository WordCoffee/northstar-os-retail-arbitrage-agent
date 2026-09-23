"""Data readiness runner (Phase A / A4).

Answers one question per service: *is every data point it needs live and fresh?*
Checks (offline unless ``live``):

  1. Provider key presence (by env var name only — never reads values).
  2. Warehouse stock counts (live rows, fresh rows, per-provider pulls).
  3. Field coverage — % of stocked rows carrying each required field.
  4. Freshness — rows within the service's ``min_freshness_hours``.
  5. Optional live probe (``--live``): fire the free-tier route once per service
     and report whether real non-null data comes back.

Emits a JSON report + a per-service PASS/FAIL. Pure and offline by default.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REQUIREMENTS_PATH = os.path.join(_REPO_ROOT, "shared", "data-requirements.json")

_PROVIDER_KEY_ENV = {
    "bright_data_web_unlocker": "BRIGHTDATA_UNLOCKER_API_KEY",
    "chocodata": "CHOCODATA_API_KEY",
    "scrapingdog": "SCRAPINGDOG_API_KEY",
    "scrapingbee": "SCRAPINGBEE_API_KEY",
    "scrapebadger": "SCRAPEBADGER_API_KEY",
    "amazonscraperapi": "AMAZONSCRAPERAPI_API_KEY",
    "apiclaw": "APICLAW_API_KEY",
    "firecrawl": "FIRECRAWL_API_KEY",
    "scrape_do": "SCRAPE_DO_API_KEY",
}


def load_requirements(path: Optional[str] = None) -> Dict[str, Any]:
    try:
        with open(path or _REQUIREMENTS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def provider_key_presence(route: Optional[str] = None) -> Dict[str, bool]:
    """Presence-only provider key check (never reads values)."""
    reqs = load_requirements()
    routes = reqs.get("providers", {})
    if route:
        ids = routes.get(route, [])
    else:
        ids = sorted({p for group in routes.values() for p in group})
    return {pid: bool(str(os.getenv(_PROVIDER_KEY_ENV.get(pid, ""), "") or "").strip()) for pid in ids}


def _freshness_cutoff(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _stock_stats() -> Dict[str, Any]:
    try:
        from live_catalog import get_stocked, _db
        db = _db()
        stocked = get_stocked(limit=100000, fresh_only=False)
        fresh = get_stocked(limit=100000, fresh_only=True)
        return {
            "live_rows": len(stocked),
            "fresh_rows": len(fresh),
            "pulls": db.live_pulls.count(),
            "rows": stocked,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"live_rows": 0, "fresh_rows": 0, "pulls": 0, "rows": [], "error": str(exc)}


def _field_coverage(rows: List[Dict[str, Any]], fields: List[str]) -> float:
    if not fields:
        return 1.0
    if not rows:
        return 0.0
    complete = 0
    for r in rows:
        if all(r.get(f) not in (None, "") for f in fields):
            complete += 1
    return round(complete / len(rows), 4)


def _fresh_fraction(rows: List[Dict[str, Any]], hours: float) -> float:
    if not rows:
        return 0.0
    cutoff = _freshness_cutoff(hours)
    fresh = sum(1 for r in rows if (r.get("fresh_until") or "") > cutoff)
    return round(fresh / len(rows), 4)


def check_service(name: str, spec: Dict[str, Any], stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Evaluate one service against its requirements (offline)."""
    stats = stats or _stock_stats()
    fields = list(spec.get("required_fields", []) or [])
    hours = float(spec.get("min_freshness_hours", 24))
    rows = stats.get("rows", [])
    coverage = _field_coverage(rows, fields)
    fresh = _fresh_fraction(rows, hours)

    # A service with no product requirements (e.g. AutothinK / Town Crier brand
    # voice) is "ready" by absence of data deps.
    if not fields:
        return {"service": name, "display": spec.get("display"), "ready": True,
                "reason": "no_product_data_required", "coverage": 1.0, "fresh": 1.0,
                "required_fields": fields}

    if stats.get("live_rows", 0) == 0:
        return {"service": name, "display": spec.get("display"), "ready": False,
                "reason": "no_stocked_live_rows", "coverage": coverage, "fresh": fresh,
                "required_fields": fields}
    if coverage < 1.0:
        return {"service": name, "display": spec.get("display"), "ready": False,
                "reason": "field_coverage_incomplete", "coverage": coverage, "fresh": fresh,
                "required_fields": fields, "missing_example": _missing_example(rows, fields)}
    if fresh < 1.0:
        return {"service": name, "display": spec.get("display"), "ready": False,
                "reason": "stale_stock", "coverage": coverage, "fresh": fresh,
                "required_fields": fields}
    return {"service": name, "display": spec.get("display"), "ready": True,
            "reason": "ok", "coverage": coverage, "fresh": fresh, "required_fields": fields}


def _missing_example(rows: List[Dict[str, Any]], fields: List[str]) -> List[str]:
    for r in rows:
        missing = [f for f in fields if r.get(f) in (None, "")]
        if missing:
            return missing
    return []


def check_all(live: bool = False) -> Dict[str, Any]:
    """Run the readiness check across every service. Offline by default."""
    reqs = load_requirements()
    stats = _stock_stats()
    services = reqs.get("services", {})
    results = [check_service(name, spec, stats) for name, spec in services.items()]

    keyed_routes = {route: provider_key_presence(route) for route in reqs.get("providers", {})}
    report = {
        "ready": all(r["ready"] for r in results),
        "services": results,
        "provider_keys": keyed_routes,
        "warehouse": {"live_rows": stats["live_rows"], "fresh_rows": stats["fresh_rows"],
                      "pulls": stats["pulls"]},
        "live_probe": bool(live),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if live:
        report["live_probe_result"] = live_probe()
    return report


def live_probe(queries: Optional[List[str]] = None) -> Dict[str, Any]:
    """Fire ONE free-tier route per seed query to prove the channel returns data.

    Real (free-tier) calls — caller must have the §3 envelope armed. Kept small;
    the full-scale pass lives in stock_runner. Returns per-query row counts.
    """
    import live_catalog
    seeds = queries or ["coffee beans", "kitchen gadgets"]
    out = []
    for q in seeds:
        res = live_catalog.stock(q, live=True)
        out.append({"query": q, "stocked": res.get("stocked"), "mode": res.get("mode")})
    return {"probes": out, "total_stocked": sum(p.get("stocked", 0) or 0 for p in out)}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Data readiness check")
    parser.add_argument("--live", action="store_true", help="Also fire a small live probe (§3 gated)")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report")
    args = parser.parse_args(argv)

    report = check_all(live=args.live)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"READY: {report['ready']}")
        for r in report["services"]:
            mark = "PASS" if r["ready"] else "FAIL"
            print(f"  [{mark}] {r['display']:16s} {r['reason']} (cov {r['coverage']}, fresh {r['fresh']})")
        print(f"  warehouse: {report['warehouse']}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
