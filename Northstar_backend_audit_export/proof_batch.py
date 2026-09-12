"""Controlled 20-ASIN proof-batch envelope + fixture comparison support
(plan: docs/user-selected-20-asin-validation-run.md, Phase 4).

OFFLINE ONLY — zero network, zero provider clients, zero writes except the
explicit `--out` path of the fixture-run CLI (test/fixture artifacts only;
production snapshot files are NEVER written here).

Responsibilities:
  - Define the normalized run-result envelope (future guarded live run):
    run_id, asin, provider, requested_fields, provider_status,
    result_status, captured_at, snapshot (intel_schema.py shape), provenance
    + coverage, scrubbed error shape.
  - Validate envelopes: envelope-level rules + `intel_schema.validate_snapshot`
    on the snapshot; envelopes carrying secret-like keys are REJECTED.
  - Compare a stored (fixture or future live) envelope against the offline
    benchmark reference via benchmark_validation and build a batch
    coverage/drift report that never fabricates a universal accuracy
    percentage.
"""

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

import intel_schema
import benchmark_validation as bv

ENVELOPE_SCHEMA_VERSION = 1

VALID_PROVIDERS = (
    "EASYPARSER",
    "KEEPA",
    "COSTCO_CACHE",
    "INVOICE_MANUAL",
    "SELLER_CENTRAL_MANUAL",
)

PROVIDER_STATUSES = ("success", "partial", "error", "skipped_fresh", "deferred_budget")
RESULT_STATUSES = ("available", "partial", "provider_error", "unavailable", "fixture")

# Documented planning estimates (AGENTS.md / provider docs). None = unknown,
# never a guess.
PROVIDER_PROFILES = {
    "EASYPARSER": {
        "provides": ["seller_roster", "per_offer_price", "shipping", "fulfillment", "buy_box"],
        "credit_estimate": 5,
        "credit_estimate_source": "documented_estimate",
    },
    "KEEPA": {
        "provides": ["bsr", "category", "price_rank_history"],
        "credit_estimate": None,
        "credit_estimate_source": "unknown",
    },
    "COSTCO_CACHE": {
        "provides": ["discovery_cost"],
        "credit_estimate": 0,
        "credit_estimate_source": "zero_cost_cache",
    },
    "INVOICE_MANUAL": {
        "provides": ["purchase_authorized_cogs"],
        "credit_estimate": 0,
        "credit_estimate_source": "manual_input",
    },
    "SELLER_CENTRAL_MANUAL": {
        "provides": ["fee_confirmation", "restriction_confirmation"],
        "credit_estimate": 0,
        "credit_estimate_source": "manual_input",
    },
}

SECRET_KEY_RE = re.compile(r"key|token|secret|credential|password|api", re.IGNORECASE)

BATCH_CAP = 20

HUMAN_CONFIRMATION_LINE = "HUMAN CONFIRMATION REQUIRED — NO LIVE CALLS EXECUTED"


def contains_secret_like(obj: Any, _path: str = "") -> bool:
    """True when any dict KEY matches a secret-like pattern (recursive)."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if SECRET_KEY_RE.search(str(key)):
                return True
            if contains_secret_like(value, f"{_path}.{key}"):
                return True
    elif isinstance(obj, list):
        return any(contains_secret_like(item, _path) for item in obj)
    return False


def sanitize_error(error: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Error shape {code, message}; unknown/absent -> None. Never secrets."""
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    message = error.get("message")
    if code is None and message is None:
        return None
    return {
        "code": str(code) if code is not None else "unknown",
        "message": str(message)[:500] if message is not None else "no detail",
    }


def build_envelope(
    run_id: str,
    asin: str,
    provider: str,
    requested_fields: List[str],
    snapshot: Dict[str, Any],
    provider_status: str = "success",
    result_status: str = "available",
    captured_at: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Normalized run-result envelope. Never writes anything."""
    return {
        "envelope_schema_version": ENVELOPE_SCHEMA_VERSION,
        "run_id": run_id,
        "asin": str(asin).upper(),
        "provider": str(provider).upper(),
        "requested_fields": list(requested_fields),
        "provider_status": provider_status,
        "result_status": result_status,
        "captured_at": captured_at,
        "snapshot": snapshot,
        "provenance": {
            "source": str(provider).upper(),
            "coverage": (provenance or {}).get("coverage", "unknown"),
        },
        "error": sanitize_error(error),
    }


def validate_envelope(envelope: Dict[str, Any]) -> List[str]:
    """Envelope-level checks + intel_schema validation of the snapshot."""
    errors: List[str] = []
    if not isinstance(envelope, dict):
        return ["envelope must be a dict"]
    if contains_secret_like(envelope):
        errors.append("envelope contains secret-like keys; rejected")
    if envelope.get("envelope_schema_version") != ENVELOPE_SCHEMA_VERSION:
        errors.append(f"envelope_schema_version must be {ENVELOPE_SCHEMA_VERSION}")
    run_id = envelope.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        errors.append("run_id must be a non-empty string")
    asin = envelope.get("asin")
    if not isinstance(asin, str) or not intel_schema.ASIN_PATTERN.fullmatch(asin):
        errors.append("asin must be a 10-character alphanumeric string")
    provider = envelope.get("provider")
    if provider not in VALID_PROVIDERS:
        errors.append(f"provider must be one of {VALID_PROVIDERS}")
    if envelope.get("provider_status") not in PROVIDER_STATUSES:
        errors.append(f"provider_status must be one of {PROVIDER_STATUSES}")
    if envelope.get("result_status") not in RESULT_STATUSES:
        errors.append(f"result_status must be one of {RESULT_STATUSES}")
    if envelope.get("error") is None and envelope.get("provider_status") == "error":
        errors.append("provider_status error requires an error object")
    snapshot = envelope.get("snapshot")
    if not isinstance(snapshot, dict):
        errors.append("snapshot must be a dict")
    else:
        errors.extend(intel_schema.validate_snapshot(snapshot))
    return errors


def fixture_snapshot_for(bench: Dict[str, Any], drift_price: float, reviews_delta: int = 300) -> Dict[str, Any]:
    """Synthetic intel_schema-shaped snapshot built FROM a benchmark record.

    Fixture/test use only — never mistaken for live data. Values are derived
    from the benchmark canonical row so comparisons exercise real fields.
    """
    asin = bench["asin"]
    return {
        "schema_version": intel_schema.SCHEMA_VERSION,
        "asin": asin,
        "ingested_at": "2026-08-18T12:00:00+00:00",
        "sources": {"fixture": {"kind": "synthetic"}},
        "facts": {
            "identity": {
                "name": bench["title"],
                "reviews_count": (bench["reviews"] + reviews_delta) if bench["reviews"] is not None else None,
            },
            "cost": {"cost_status": "costco_online_discovery", "costco_cost": None},
            "fees": {"fba_fee": None, "fba_fee_status": "unavailable"},
            "demand": {
                "estimated_monthly_sales": None,
                "sales_estimation_method": "unknown",
                "sales_estimation_confidence": "unknown",
                "bsr": bench["bsr_rank_number"],
                "bsr_category": bench["bsr_category"],
            },
            "market": {
                "amazon_price": drift_price,
                "buy_box": {
                    "available": False, "price": None, "seller_name": None,
                    "seller_id": None, "fulfillment": None, "source": None,
                    "observed_at": None,
                },
                "seller_counts": {
                    "total_observed": None, "fba_observed": None, "fbm_observed": None,
                    "amazon_observed": None, "claimed_total": None,
                },
                "coverage": {
                    "offer_list_available": False,
                    "offers_complete_status": "unknown",
                    "coverage_reason": "fixture snapshot without offer roster",
                },
                "offers": [],
            },
            "economics": {
                "net_profit": None, "roi_pct": None,
                "economics_confidence": "unavailable",
                "economics_status": "missing_market_or_cost_inputs",
            },
            "provenance": {
                "identity.name": {"source": "fixture", "fetched_at": "2026-08-18T12:00:00+00:00"},
                "demand.bsr": {"source": "fixture", "fetched_at": "2026-08-18T12:00:00+00:00"},
                "demand.bsr_category": {"source": "fixture", "fetched_at": "2026-08-18T12:00:00+00:00"},
                "market.amazon_price": {"source": "fixture", "fetched_at": "2026-08-18T12:00:00+00:00"},
            },
        },
    }


def build_fixture_envelopes(benchmark_store: Dict[str, Any]) -> List[Dict[str, Any]]:
    """A small deterministic fixture set (labeled fixture) from the first two
    canonical benchmark rows. Test/CLI use only."""
    canonical = benchmark_store.get("canonical", {})
    asins = sorted(canonical)[:2]
    envelopes: List[Dict[str, Any]] = []
    for index, asin in enumerate(asins):
        bench = canonical[asin]
        base = bench["price"] if bench["price"] is not None else 10.0
        drift = base * (1.03 if index == 0 else 1.20)  # within-tolerance vs material
        snap = fixture_snapshot_for(bench, round(drift, 2))
        envelopes.append(
            build_envelope(
                run_id="fixture-run-001",
                asin=asin,
                provider="EASYPARSER",
                requested_fields=["market_offers"],
                snapshot=snap,
                provider_status="success",
                result_status="fixture",
                captured_at="2026-08-18T12:00:00+00:00",
            )
        )
    return envelopes


def compare_envelope(benchmark_store: Dict[str, Any], envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Compare a validated envelope's snapshot against the benchmark."""
    bench = benchmark_store.get("canonical", {}).get(envelope.get("asin", ""))
    if bench is None:
        return {
            "asin": envelope.get("asin"),
            "identity": {"asin_match": "fail"},
            "note": "no benchmark reference for this ASIN",
        }
    report = bv.compare_benchmark_record(bench, envelope.get("snapshot") or {})
    report["run_id"] = envelope.get("run_id")
    report["provider"] = envelope.get("provider")
    report["result_status"] = envelope.get("result_status")
    report["envelope_validation_errors"] = validate_envelope(envelope)
    return report


def build_batch_report(
    benchmark_store: Dict[str, Any], envelopes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Per-ASIN comparisons + batch coverage/drift metrics + limitations.

    Never produces a single universal accuracy percentage; measured metrics
    and coverage metrics are separate (benchmark_validation.summarize_batch
    already enforces this).
    """
    reports = [compare_envelope(benchmark_store, env) for env in envelopes]
    metrics = bv.summarize_batch(reports)
    mapping_mismatch_flags = [
        r["asin"]
        for r in reports
        if r.get("identity", {}).get("pack_mismatch_block")
        or r.get("identity", {}).get("title_status") == "mismatch"
        or (not r.get("bsr", {}).get("comparable") and r.get("bsr", {}).get("category_context") == "mismatch")
    ]
    return {
        "run_ids": sorted({r.get("run_id") for r in reports if r.get("run_id")}),
        "envelope_count": len(envelopes),
        "reports": reports,
        "metrics": metrics,
        "mapping_mismatch_flags": mapping_mismatch_flags,
        "limitations": {
            "capture_time_unknown": True,
            "note": "benchmark capture time unknown; reference only, not freshness proof",
            "market_drift_is_not_provider_error": True,
            "economics_demand_internally_validated": True,
            "no_universal_accuracy_percentage": True,
        },
    }


def _cli() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit(
            "usage:\n"
            "  python proof_batch.py fixture-run --out <path>   (fixture envelopes only)\n"
            "  python proof_batch.py report --benchmark <reference.json> --results <envelopes.json>"
        )
    command = args[0]
    if command == "fixture-run":
        out = None
        for i, arg in enumerate(args):
            if arg == "--out" and i + 1 < len(args):
                out = args[i + 1]
        if not out:
            raise SystemExit("fixture-run requires --out <path> (explicit fixture destination)")
        store_path = os.environ.get("BENCHMARK_REFERENCE_PATH")
        if store_path and os.path.isfile(store_path):
            import asin_benchmark_store

            benchmark_store = asin_benchmark_store.load_reference()
        else:
            benchmark_store = json.load(open("data/benchmarks/asin_benchmark_reference.json", encoding="utf-8"))
        envelopes = build_fixture_envelopes(benchmark_store)
        for env in envelopes:
            errors = validate_envelope(env)
            if errors:
                raise SystemExit(f"fixture envelope invalid: {errors}")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(
                {"kind": "fixture-envelopes", "note": "SYNTHETIC FIXTURE — not live data", "envelopes": envelopes},
                fh, indent=2, ensure_ascii=False,
            )
        print(f"fixture envelopes written: {out}")
        print(f"note: SYNTHETIC FIXTURE — not live data; no provider calls made")
    elif command == "report":
        opts = {}
        for i, arg in enumerate(args):
            if arg in ("--benchmark", "--results") and i + 1 < len(args):
                opts[arg] = args[i + 1]
        if "--benchmark" not in opts or "--results" not in opts:
            raise SystemExit("report requires --benchmark <reference.json> --results <envelopes.json>")
        benchmark_store = json.load(open(opts["--benchmark"], encoding="utf-8"))
        payload = json.load(open(opts["--results"], encoding="utf-8"))
        envelopes = payload.get("envelopes") if isinstance(payload, dict) else payload
        for env in envelopes:
            errors = validate_envelope(env)
            if errors:
                raise SystemExit(f"envelope invalid for {env.get('asin')}: {errors}")
        report = build_batch_report(benchmark_store, envelopes)
        print(json.dumps(report, indent=2, default=str))
    else:
        raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    _cli()