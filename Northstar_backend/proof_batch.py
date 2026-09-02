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

# The FIXED validation batch source: exactly the 20 ASINs the user supplied
# in the Rank file (file B, source_rank 1..20). This is NOT a candidate
# selection — it is the user's own fixed set, derived deterministically.
VALIDATION_SET_SOURCE_FILE = "Rank-Product-ASIN-Reviews-Price-BSR.csv"

# market_snapshot_store freshness policy (offers 7d / sales 30d / identity
# 90d) — only a fresh snapshot row may skip its provider request.
FRESH_OFFERS_DAYS = 7
FRESH_SALES_DAYS = 30
FRESH_IDENTITY_DAYS = 90


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
    preflight_fingerprint: Optional[str] = None,
    requested_asin: Optional[str] = None,
    request_index: Optional[int] = None,
    mapping_state: Optional[str] = None,
    mapping_reason: Optional[str] = None,
    credits_used_reported: Optional[int] = None,
    credits_used_estimated: Optional[float] = None,
) -> Dict[str, Any]:
    """Normalized run-result envelope. Never writes anything.

    Optional guard keys (preflight_fingerprint, requested_asin,
    request_index, mapping_state, mapping_reason, credit accounting) are
    included only when supplied — existing envelopes keep their exact
    shape, so the contract is unchanged for older consumers.
    """
    envelope = {
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
            **{
                key: (provenance or {}).get(key)
                for key in ("provider_request_id", "credit_accounting_status", "adapter")
                if (provenance or {}).get(key) is not None
            },
        },
        "error": sanitize_error(error),
    }
    if preflight_fingerprint is not None:
        envelope["preflight_fingerprint"] = preflight_fingerprint
    if requested_asin is not None:
        envelope["requested_asin"] = str(requested_asin).upper()
    if request_index is not None:
        envelope["request_index"] = request_index
    if mapping_state is not None:
        envelope["mapping_state"] = mapping_state
    if mapping_reason is not None:
        envelope["mapping_reason"] = mapping_reason
    if credits_used_reported is not None:
        envelope["credits_used_reported"] = credits_used_reported
    if credits_used_estimated is not None:
        envelope["credits_used_estimated"] = round(float(credits_used_estimated), 2)
    return envelope


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
    report = bv.compare_benchmark_record(
        bench, envelope.get("snapshot") or {},
        conflicts=benchmark_store.get("conflicts"),
    )
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


def resolve_validation_set(benchmark_store: Dict[str, Any]) -> List[str]:
    """The fixed 20-ASIN validation batch, in the user's own file-B order.

    Deterministic (no ranking, no candidate selection): canonical ASINs whose
    source_files include the Rank file, sorted by source_rank. Returns []
    when the reference artifact is absent/empty — never fabricates.
    """
    canonical = benchmark_store.get("canonical") or {}
    rows = [
        (asin, row)
        for asin, row in canonical.items()
        if isinstance(row, dict) and VALIDATION_SET_SOURCE_FILE in (row.get("source_files") or [])
    ]
    rows.sort(
        key=lambda kv: (
            kv[1].get("source_rank") if isinstance(kv[1].get("source_rank"), int) else 999,
            kv[0],
        )
    )
    return [asin for asin, _ in rows]


def _field_availability(row: Dict[str, Any]) -> Dict[str, Any]:
    """Benchmark field availability per ASIN — unknown stays null/unavailable,
    never 0 (a user benchmark may simply lack a field)."""
    fields = {
        "price": row.get("price"),
        "reviews": row.get("reviews"),
        "prime_fba": row.get("prime_fba"),
        "bsr_rank_number": row.get("bsr_rank_number"),
        "bsr_category": row.get("bsr_category"),
    }
    present = sorted(name for name, value in fields.items() if value is not None)
    unavailable = sorted(name for name, value in fields.items() if value is None)
    return {
        "benchmark_fields_present": present,
        "benchmark_fields_unavailable": unavailable,
    }


def build_preflight(
    benchmark_store: Dict[str, Any],
    scanner_cache: Optional[Dict[str, Any]] = None,
    generated_at: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Zero-network preflight for the fixed 20-ASIN validation batch.

    Pure local computation over the benchmark reference + local cache
    metadata. Reads nothing from providers; builds nothing live; never
    writes. The caller (CLI) writes ONLY the explicit --out path.
    """
    import datetime

    generated_at = generated_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = run_id or f"proof-batch-preflight-{stamp}"

    asins = resolve_validation_set(benchmark_store)
    canonical = benchmark_store.get("canonical") or {}
    conflicts = benchmark_store.get("conflicts") or []

    validation_set = []
    conflict_asin_set = {
        c.get("asin") for c in conflicts if isinstance(c, dict) and c.get("field") == "title"
    }
    for asin in asins:
        row = canonical[asin]
        cache_row = None
        if scanner_cache and isinstance(scanner_cache.get("products"), list):
            for product in scanner_cache["products"]:
                if isinstance(product, dict) and product.get("asin") == asin:
                    cache_row = product
                    break
        entry = {
            "asin": asin,
            "source_rank": row.get("source_rank"),
            "title": row.get("title"),
            "title_conflict": bool(row.get("title_conflict")) or asin in conflict_asin_set,
            "price_conflict": bool(row.get("price_conflict")),
            "review_conflict": bool(row.get("review_conflict")),
            "price": row.get("price"),
            "reviews": row.get("reviews"),
            "prime_fba": row.get("prime_fba"),
            "bsr_rank_number": row.get("bsr_rank_number"),
            "bsr_category": row.get("bsr_category"),
            "capture_time_status": row.get("capture_time_status", "unknown"),
            "observation_count": row.get("observation_count"),
            "conflict_note": (
                "cross-file title disagreement — canonical title kept per "
                "CANONICAL_RULES; mapping review required before any use"
                if (bool(row.get("title_conflict")) or asin in conflict_asin_set)
                else None
            ),
            **_field_availability(row),
            "local_cache": {
                "in_scanner_search_cache": cache_row is not None,
                "cached_amazon_price": cache_row.get("amazon_price") if cache_row else None,
                "cached_reviews_count": cache_row.get("reviews_count") if cache_row else None,
                "cache_note": (
                    "scanner search-page cache only — does NOT satisfy offer/"
                    "BSR provider requests; enrichment requests still planned"
                    if cache_row
                    else "not present in the local scanner cache"
                ),
            },
        }
        validation_set.append(entry)

    title_conflicts = [e["asin"] for e in validation_set if e["title_conflict"]]
    unavailable_counts = {}
    for name in ("price", "reviews", "prime_fba", "bsr_rank_number", "bsr_category"):
        unavailable_counts[name] = sum(
            1 for e in validation_set if name in e["benchmark_fields_unavailable"]
        )

    cache_info = None
    if scanner_cache and isinstance(scanner_cache, dict):
        cache_info = {
            "file": "data/scanner-search-cache.json",
            "fetched_at": scanner_cache.get("fetched_at"),
            "source": scanner_cache.get("source"),
            "schema_version": scanner_cache.get("schema_version"),
            "candidate_count": scanner_cache.get("candidate_count"),
        }

    requested_fields = ["market_offers"]
    total_requests = len(asins) * 1  # Easyparser OFFER: 1 request per ASIN

    return {
        "kind": "proof-batch-preflight",
        "schema_version": 1,
        "run_id": run_id,
        "generated_at": generated_at,
        "purpose": "provider_data_contract_validation",
        "hard_caps": {
            "max_asins": 20,
            "max_requests": total_requests,
            "max_requests_note": (
                "exact number required by the approved provider plan "
                "(Easyparser OFFER: 1 request per ASIN; Keepa not approved in this preflight)"
            ),
            "max_credits": None,
            "max_credits_note": (
                "must be explicitly entered and approved by human — no default "
                "spending authorization"
            ),
        },
        "selection": {
            "selected_count": len(validation_set),
            "max_selected_count": 20,
            "asins": validation_set,
        },
        "benchmark_summary": {
            "total_canonical_asins": len(canonical),
            "validation_set_count": len(asins),
            "matched_count": len(asins),
            "unmatched_count": 0,
            "title_conflict_count": len(title_conflicts),
            "title_conflict_asins": title_conflicts,
            "price_conflict_count": sum(1 for e in validation_set if e["price_conflict"]),
            "review_conflict_count": sum(1 for e in validation_set if e["review_conflict"]),
            "benchmark_fields_unavailable": unavailable_counts,
            "capture_time_note": (
                "reference capture time unknown — price/BSR/review differences "
                "may be legitimate market drift and must not automatically be "
                "called provider errors"
            ),
        },
        "cache_and_snapshot_state": {
            "scanner_search_cache": cache_info,
            "market_snapshot_store": {"file": "data/amazon-market-snapshots.json", "present": False},
            "enriched_offer_cache": {"file": "data/enriched-offer-cache.json", "present": False},
            "seller_offer_cache": {"file": "data/seller-offer-cache.json", "present": False},
            "freshness_policy": {
                "offers_fresh_days": FRESH_OFFERS_DAYS,
                "sales_fresh_days": FRESH_SALES_DAYS,
                "identity_fresh_days": FRESH_IDENTITY_DAYS,
                "note": (
                    "only a fresh market-snapshot row (offers <=7d, sales <=30d, "
                    "identity <=90d per market_snapshot_store) may skip its "
                    "provider request; no snapshot rows exist locally"
                ),
            },
            "expected_cache_skips": 0,
        },
        "provider_plan": {
            "providers": [
                {
                    "provider": "EASYPARSER",
                    "status": "planned",
                    "fields_owned": [
                        "offer/seller roster",
                        "offer price",
                        "shipping",
                        "fulfillment",
                        "Buy Box when available",
                    ],
                    "requests_per_asin": 1,
                    "credit_estimate_per_asin": 5,
                    "credit_estimate_source": "documented_estimate",
                },
                {
                    "provider": "KEEPA",
                    "status": "not_approved_not_available",
                    "fields_owned": ["BSR/category/history"],
                    "requests_per_asin": 0,
                    "credit_estimate_per_asin": None,
                    "credit_estimate_source": "unknown",
                    "note": (
                        "BSR/category/history ONLY if separately approved AND "
                        "available; no Keepa client exists in this project — "
                        "credit estimate null: requires provider plan confirmation"
                    ),
                },
                {
                    "provider": "COSTCO_CACHE",
                    "status": "planned_zero_cost",
                    "fields_owned": ["discovery cost only — NOT purchase-authorized COGS"],
                    "requests_per_asin": 0,
                    "credit_estimate_per_asin": 0,
                    "credit_estimate_source": "zero_cost_cache",
                    "note": "no local Costco discovery cache rows exist in this environment",
                },
                {
                    "provider": "SELLER_CENTRAL_MANUAL",
                    "status": "manual_zero_cost",
                    "fields_owned": [
                        "eligibility",
                        "restrictions",
                        "invoice legitimacy",
                        "actual fees",
                    ],
                    "requests_per_asin": 0,
                    "credit_estimate_per_asin": 0,
                    "credit_estimate_source": "manual_input",
                },
            ],
            "requested_fields_per_asin": requested_fields,
            "request_count_per_asin": 1,
            "request_count_total": total_requests,
            "keepa_credit_estimate": None,
            "keepa_credit_estimate_note": "requires provider confirmation — never guessed",
            "easyparser_credit_estimate_total": len(asins) * 5,
            "easyparser_credit_estimate_source": "documented_estimate",
        },
        "stop_conditions": [
            "hard request cap (20) or human-entered credit cap reached — stop immediately",
            "provider response/error (HTTP or provider failure)",
            "schema validation failure (intel_schema.validate_snapshot) for any returned envelope",
            "wrong ASIN returned (returned ASIN != requested ASIN)",
            "product/title/pack mapping mismatch (title mismatch, pack mismatch block, BSR category mismatch)",
            "malformed or impossible field values (invalid numeric/currency parse, forbidden zeros, negative price)",
            "unexpected secret-like key in provider output",
            "persistence failure (atomic snapshot write failed)",
            "cache-only containment failure (provider call outside the explicit guarded run)",
            "credit estimate/budget-stop enforcement failure",
        ],
        "human_confirmation": HUMAN_CONFIRMATION_LINE,
    }


def _cli() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit(
            "usage:\n"
            "  python proof_batch.py fixture-run --out <path>   (fixture envelopes only)\n"
            "  python proof_batch.py report --benchmark <reference.json> --results <envelopes.json>\n"
            "  python proof_batch.py preflight --out <path> [--run-id <id>] [--cache <cache.json>]"
        )
    command = args[0]
    if command == "preflight":
        opts = {}
        for i, arg in enumerate(args):
            if arg in ("--out", "--run-id", "--cache") and i + 1 < len(args):
                opts[arg] = args[i + 1]
        if "--out" not in opts:
            raise SystemExit("preflight requires --out <path> (explicit preflight destination)")
        store_path = os.environ.get("BENCHMARK_REFERENCE_PATH")
        if store_path and os.path.isfile(store_path):
            import asin_benchmark_store

            benchmark_store = asin_benchmark_store.load_reference()
        else:
            benchmark_store = json.load(open("data/benchmarks/asin_benchmark_reference.json", encoding="utf-8"))
        cache = None
        cache_path = opts.get("--cache") or "data/scanner-search-cache.json"
        if os.path.isfile(cache_path):
            cache = json.load(open(cache_path, encoding="utf-8"))
        preflight = build_preflight(benchmark_store, scanner_cache=cache, run_id=opts.get("--run-id"))
        if preflight["selection"]["selected_count"] != 20:
            raise SystemExit(
                f"preflight validation-set mismatch: expected 20, got {preflight['selection']['selected_count']}"
            )
        if contains_secret_like(preflight):
            raise SystemExit("preflight contains secret-like keys; refusing to write")
        with open(opts["--out"], "w", encoding="utf-8") as fh:
            json.dump(preflight, fh, indent=2, ensure_ascii=False)
        print(f"preflight written: {opts['--out']}")
        print(f"run_id: {preflight['run_id']}")
        print(f"validation set: {preflight['selection']['selected_count']} / 20 ASINs")
        print(f"title conflicts: {preflight['benchmark_summary']['title_conflict_count']}")
        print(f"planned requests: {preflight['provider_plan']['request_count_total']}")
        print(preflight["human_confirmation"])
    elif command == "fixture-run":
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