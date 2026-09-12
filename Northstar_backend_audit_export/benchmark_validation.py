"""Pure/offline ASIN benchmark comparison engine (Phases 3-4 of the benchmark
validation task; plan: docs/asin-benchmark-validation-plan.md).

Accepts (1) a benchmark canonical record from asin_benchmark_store and (2) a
normalized hypothetical future market snapshot in the intel_schema.py shape,
and returns a field-by-field validation report. ZERO provider/network calls —
this module imports no provider clients and performs no I/O on live data.

Honesty invariants:
  - Comparisons run only when both values exist; missing -> null/status,
    never 0.
  - Price/BSR drift is labeled "requires freshness/context review", never
    "provider error".
  - Offer/economics/demand sections are INTERNAL coverage/provenance checks
    only; every result carries "not externally benchmarked" / "estimate
    validation, not sales-truth validation" labels.
  - No single deceptive accuracy percentage is produced: batch metrics are
    separate measured and coverage metrics.
"""

from typing import Any, Dict, List, Optional

PRICE_WITHIN_TOLERANCE = 0.05  # |dPct| <= 5%  -> within_tolerance (PROPOSED)
PRICE_MODERATE_TOLERANCE = 0.15  # |dPct| <= 15% -> moderate_drift (PROPOSED)
TITLE_LIKELY_SIMILARITY = 0.55  # >= 0.55 token overlap -> likely_match (PROPOSED)
TITLE_MATCH_SIMILARITY = 0.90  # >= 0.90 token overlap -> match (PROPOSED)

INTERNAL_ONLY_LABEL = "not externally benchmarked"
DEMAND_LABEL = "estimate validation, not sales-truth validation"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_title(value: Any) -> Optional[str]:
    if value is None:
        return None
    return asin_benchmark_store_normalize(value)


def asin_benchmark_store_normalize(value: Any) -> Optional[str]:
    import re as _re

    if value is None:
        return None
    text = " ".join(str(value).split())
    text = _re.sub(r"[^\w\s]", "", text, flags=_re.UNICODE)
    return text.lower()


def token_overlap_similarity(a: Any, b: Any) -> Optional[float]:
    left = _norm_title(a)
    right = _norm_title(b)
    if left is None or right is None:
        return None
    la = set(left.split())
    lb = set(right.split())
    if not la or not lb:
        return 0.0
    return len(la & lb) / max(len(la), len(lb))


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def compare_identity(
    bench_title: Any, live_title: Any, bench_pack: Optional[List[tuple]] = None,
    live_pack: Optional[List[tuple]] = None,
) -> Dict[str, Any]:
    """ASIN exact-match plus normalized-title/pack-size signal comparison.

    title_status: match | likely_match | mismatch | unavailable.
    pack_status: match | conflict | unavailable. A pack conflict is NEVER
    auto-resolved -> pack_mismatch_block True.
    """
    if bench_title is None or live_title is None:
        return {
            "title_status": "unavailable",
            "title_similarity": None,
            "pack_status": "unavailable",
            "pack_mismatch_block": False,
            "note": "identity comparison unavailable: benchmark or live title missing",
        }
    if bench_pack is None:
        bench_pack = pack_tokens_signal(bench_title)
    if live_pack is None:
        live_pack = pack_tokens_signal(live_title)
    similarity = token_overlap_similarity(bench_title, live_title) or 0.0
    if similarity >= TITLE_MATCH_SIMILARITY:
        title_status = "match"
    elif similarity >= TITLE_LIKELY_SIMILARITY:
        title_status = "likely_match"
    else:
        title_status = "mismatch"

    bt = set(bench_pack or [])
    lt = set(live_pack or [])
    pack_status = "unavailable"
    pack_mismatch_block = False
    if bt or lt:
        if bt == lt and bt:
            pack_status = "match"
        elif bt and lt and bt & lt:
            pack_status = "match" if bt <= lt or lt <= bt else "conflict"
        elif bt and lt:
            pack_status = "conflict"
            pack_mismatch_block = True
        elif bt or lt:
            pack_status = "unavailable"
    if pack_status == "conflict":
        pack_mismatch_block = True

    note = None
    if title_status == "mismatch":
        note = "title mismatch flagged; requires human review"
    elif pack_mismatch_block:
        note = "pack-size signal conflict; NEVER auto-resolved — human review required"
    return {
        "title_status": title_status,
        "title_similarity": round(similarity, 4),
        "pack_status": pack_status,
        "pack_mismatch_block": pack_mismatch_block,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------

def compare_price(
    bench_price: Any, live_price: Any,
    within_tolerance: float = PRICE_WITHIN_TOLERANCE,
    moderate_tolerance: float = PRICE_MODERATE_TOLERANCE,
) -> Dict[str, Any]:
    """Only when both exist. Classification: exact | within_tolerance |
    moderate_drift | material_drift | unavailable."""
    b = _num(bench_price)
    l = _num(live_price)
    if b is None or l is None:
        return {
            "comparable": False,
            "absolute_variance": None,
            "percent_variance": None,
            "classification": "unavailable",
            "note": "price comparison unavailable: benchmark or live price missing",
        }
    absolute = l - b
    pct = absolute / b if b else None
    if absolute == 0:
        classification = "exact"
    elif pct is not None and abs(pct) <= within_tolerance:
        classification = "within_tolerance"
    elif pct is not None and abs(pct) <= moderate_tolerance:
        classification = "moderate_drift"
    else:
        classification = "material_drift"
    note = "price drift labeled requires freshness/context review — not a provider error" if classification != "exact" else "exact price match at benchmark reference time"
    return {
        "comparable": True,
        "absolute_variance": round(absolute, 2),
        "percent_variance": round(pct, 4) if pct is not None else None,
        "classification": classification,
        "capture_time_status": "unknown",
        "note": note,
    }


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

def compare_reviews(bench_reviews: Any, live_reviews: Any) -> Dict[str, Any]:
    """Trend classification only. Higher live count is expected; a lower
    count is flagged, never auto-failed without listing/variation context."""
    b = _num(bench_reviews)
    l = _num(live_reviews)
    if b is None or l is None:
        return {
            "comparable": False,
            "trend": "unavailable",
            "direction": None,
            "percent_change": None,
            "note": "review comparison unavailable: benchmark or live review count missing",
        }
    if l == b:
        trend = "unchanged"
    elif l > b:
        trend = "expected_growth"
    else:
        trend = "decline_flag"
    pct = (l - b) / b if b else None
    note = None
    if trend == "decline_flag":
        note = "live review count lower than benchmark; flagged — requires listing/variation context, not auto-failed"
    elif trend == "expected_growth":
        note = "live review count higher than benchmark; expected for a maturing listing"
    return {
        "comparable": True,
        "trend": trend,
        "direction": "up" if l > b else ("down" if l < b else "flat"),
        "percent_change": round(pct, 4) if pct is not None else None,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Prime / FBA signal
# ---------------------------------------------------------------------------

def compare_prime_fba(bench_state: Any, live_state: Any) -> Dict[str, Any]:
    """match | changed | unavailable. Changed does not imply error."""
    if bench_state is None or live_state is None:
        return {
            "comparable": False,
            "status": "unavailable",
            "note": "Prime/FBA comparison unavailable: benchmark or live signal missing",
        }
    if str(bench_state).strip().lower() == str(live_state).strip().lower():
        return {"comparable": True, "status": "match", "note": None}
    return {
        "comparable": True,
        "status": "changed",
        "note": "Prime/FBA signal changed vs benchmark; does not imply provider error — review context",
    }


# ---------------------------------------------------------------------------
# BSR / category
# ---------------------------------------------------------------------------

def compare_bsr(
    bench_rank: Any, bench_category: Any, live_rank: Any, live_category: Any,
) -> Dict[str, Any]:
    """Only when both rank numbers exist AND category context matches.
    BSR change is never equated with provider inaccuracy."""
    b = _num(bench_rank)
    l = _num(live_rank)
    if b is None or l is None:
        return {
            "comparable": False,
            "category_context": "unavailable",
            "observed_change": None,
            "percent_change": None,
            "note": "BSR comparison unavailable: benchmark or live BSR rank missing",
        }
    if bench_category is None or live_category is None:
        return {
            "comparable": False,
            "category_context": "unavailable",
            "observed_change": None,
            "percent_change": None,
            "note": "BSR category context missing on one side; comparison withheld",
        }
    if str(bench_category).strip().lower() != str(live_category).strip().lower():
        return {
            "comparable": False,
            "category_context": "mismatch",
            "observed_change": None,
            "percent_change": None,
            "note": "BSR category mismatch flagged for review; ranks not compared across categories",
        }
    change = l - b
    pct = change / b if b else None
    return {
        "comparable": True,
        "category_context": "match",
        "observed_change": round(change, 4),
        "percent_change": round(pct, 4) if pct is not None else None,
        "direction": "improved_rank" if l < b else ("worsened_rank" if l > b else "unchanged"),
        "note": "BSR change is market drift signal, not provider inaccuracy",
    }


# ---------------------------------------------------------------------------
# Offer/seller section (internal coverage/provenance only)
# ---------------------------------------------------------------------------

def validate_offer_section(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    facts = snapshot.get("facts") or {}
    market = facts.get("market") or {}
    provenance = facts.get("provenance") or {}
    coverage = market.get("coverage") or {}
    seller_counts = market.get("seller_counts") or {}
    buy_box = market.get("buy_box") or {}
    offers = market.get("offers")

    present = bool(offers) or coverage.get("offer_list_available") is True or seller_counts.get("total_observed") is not None

    source = None
    timestamp = None
    for key in ("market.seller_counts", "market.offers", "market.coverage"):
        entry = provenance.get(key)
        if isinstance(entry, dict):
            source = entry.get("source") or source
            timestamp = entry.get("fetched_at") or entry.get("observed_at") or timestamp
    if timestamp is None and buy_box.get("observed_at"):
        timestamp = buy_box["observed_at"]

    offers_complete = coverage.get("offers_complete_status")
    coverage_status = offers_complete if offers_complete in ("full", "partial", "unknown") else "unknown"
    if coverage_status == "unknown" and present and coverage.get("offer_list_available") is False:
        coverage_status = "partial"

    consistency = validate_seller_count_consistency(seller_counts, offers)

    return {
        "present": present,
        "source": source,
        "timestamp": timestamp,
        "coverage": coverage_status,
        "internal_consistency": consistency,
        "buy_box_present": buy_box.get("available") is True,
        "buy_box_requires_offer_data": _buy_box_consistency(buy_box, present),
        "label": INTERNAL_ONLY_LABEL,
        "note": "no benchmark seller roster exists; coverage/provenance validated internally only",
    }


def validate_seller_count_consistency(
    seller_counts: Dict[str, Any], offers: Any,
) -> Dict[str, Any]:
    """total == FBA + FBM (+ AMAZON when present) — only when all exist."""
    total = seller_counts.get("total_observed")
    fba = seller_counts.get("fba_observed")
    fbm = seller_counts.get("fbm_observed")
    amazon = seller_counts.get("amazon_observed")
    if total is None:
        return {"status": "unavailable", "reason": "total_observed missing"}
    if fba is None or fbm is None:
        return {"status": "unavailable", "reason": "fba_observed or fbm_observed missing"}
    expected = fba + fbm + (amazon if amazon is not None else 0)
    if amazon is not None and total == expected:
        return {"status": "consistent", "fba": fba, "fbm": fbm, "amazon": amazon, "total": total}
    if amazon is None and total == expected:
        return {
            "status": "consistent",
            "fba": fba, "fbm": fbm, "total": total,
            "note": "amazon_observed absent; total matches FBA+FBM",
        }
    return {
        "status": "inconsistent",
        "fba": fba, "fbm": fbm, "amazon": amazon, "total": total,
        "expected": expected,
        "reason": "total_observed does not equal FBA+FBM(+AMAZON); review roster",
    }


def _buy_box_consistency(buy_box: Dict[str, Any], offer_present: bool) -> Dict[str, Any]:
    if buy_box.get("available") is not True:
        return {"status": "absent", "note": "no Buy Box winner reported"}
    if not offer_present:
        return {
            "status": "warning",
            "note": "Buy Box winner reported without offer roster presence — flagged",
        }
    return {"status": "ok", "note": "Buy Box winner present alongside offer data"}


# ---------------------------------------------------------------------------
# Economics (internal only)
# ---------------------------------------------------------------------------

def validate_economics_internal(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    facts = snapshot.get("facts") or {}
    economics = facts.get("economics") or {}
    cost = facts.get("cost") or {}
    fees = facts.get("fees") or {}

    roi = _num(economics.get("roi_pct"))
    net = _num(economics.get("net_profit"))
    confidence = economics.get("economics_confidence")

    if roi == 0:
        return {
            "readiness": "unavailable",
            "label": INTERNAL_ONLY_LABEL,
            "note": "roi_pct is 0 — unknown must be null; economics not usable",
        }
    if roi is None or confidence is None:
        return {
            "readiness": "unavailable",
            "label": INTERNAL_ONLY_LABEL,
            "note": "ROI unavailable: material economics inputs missing",
        }
    cost_ok = bool(cost.get("cost_status")) and cost.get("cost_status") != "unavailable"
    fee_provenance = any(
        isinstance(v, dict) and (v.get("source") or v.get("method"))
        for v in fees.values()
        if isinstance(v, dict)
    )
    if not cost_ok or not fee_provenance:
        return {
            "readiness": "assumption_based",
            "label": INTERNAL_ONLY_LABEL,
            "note": "ROI present but cost/fee provenance incomplete — assumption-based",
        }
    if confidence == "estimated":
        return {
            "readiness": "decision_ready",
            "label": INTERNAL_ONLY_LABEL,
            "note": "ROI computed with cost + fee provenance; not externally benchmarked",
        }
    return {
        "readiness": "assumption_based",
        "label": INTERNAL_ONLY_LABEL,
        "note": f"ROI present with confidence '{confidence}' — assumption-based",
    }


# ---------------------------------------------------------------------------
# Demand (internal only)
# ---------------------------------------------------------------------------

def validate_demand_internal(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    facts = snapshot.get("facts") or {}
    demand = facts.get("demand") or {}
    market = facts.get("market") or {}

    bsr = demand.get("bsr")
    bsr_category = demand.get("bsr_category")
    if bsr is None and market.get("bsr") is not None:
        bsr = market.get("bsr")
        bsr_category = market.get("bsr_category")
    method = demand.get("sales_estimation_method")
    confidence = demand.get("sales_estimation_confidence")
    estimate = demand.get("estimated_monthly_sales")

    if estimate == 0:
        return {
            "label": DEMAND_LABEL,
            "note": "estimated_monthly_sales is 0 — unknown must be null; demand not usable",
        }
    return {
        "bsr_input_present": bsr is not None,
        "bsr_category_present": bsr_category is not None,
        "estimation_method": method if method else None,
        "estimation_confidence": confidence if confidence else None,
        "label": DEMAND_LABEL,
        "note": "estimate validation only — never sales-truth validation",
    }


# ---------------------------------------------------------------------------
# Full benchmark-record comparison
# ---------------------------------------------------------------------------

def compare_benchmark_record(
    bench: Dict[str, Any], snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    """bench: canonical record from asin_benchmark_store (canonical.asins[k]).
    snapshot: intel_schema.py-shaped normalized market snapshot."""
    facts = snapshot.get("facts") or {}
    identity = facts.get("identity") or {}
    market = facts.get("market") or {}
    demand = facts.get("demand") or {}

    live_asin = snapshot.get("asin")
    asin_match = "pass" if live_asin and str(live_asin).upper() == str(bench.get("asin")).upper() else "fail"

    live_title = identity.get("name")
    live_price = market.get("amazon_price")
    if live_price is None and (market.get("buy_box") or {}).get("price") is not None:
        live_price = (market.get("buy_box") or {}).get("price")
        live_price_source = "buy_box"
    else:
        live_price_source = "amazon_price" if live_price is not None else None

    live_reviews = identity.get("reviews_count")
    if live_reviews is None:
        live_reviews = market.get("reviews_count")
    if live_reviews is None:
        live_reviews = demand.get("reviews_count")

    live_bsr = demand.get("bsr")
    if live_bsr is None:
        live_bsr = market.get("bsr")
    live_bsr_category = demand.get("bsr_category")
    if live_bsr_category is None:
        live_bsr_category = market.get("bsr_category")

    live_prime = market.get("prime_fba")
    if live_prime is None:
        fulfillment = (market.get("buy_box") or {}).get("fulfillment")
        if fulfillment in ("FBA", "FBM", "AMAZON"):
            live_prime = "yes" if fulfillment in ("FBA", "AMAZON") else "no"
        else:
            live_prime = None

    return {
        "asin": bench.get("asin"),
        "capture_time_status": bench.get("capture_time_status", "unknown"),
        "capture_time_note": "reference capture time unknown — reference only, not freshness proof"
        if bench.get("capture_time_status") != "known" else None,
        "benchmark_source_files": bench.get("source_files"),
        "identity": {
            "asin_match": asin_match,
            **compare_identity(
                bench.get("title"), live_title,
                bench_pack=pack_tokens_signal(bench.get("title")),
                live_pack=pack_tokens_signal(live_title),
            ),
        },
        "price": compare_price(bench.get("price"), live_price),
        "reviews": compare_reviews(bench.get("reviews"), live_reviews),
        "prime_fba": compare_prime_fba(bench.get("prime_fba"), live_prime),
        "bsr": compare_bsr(
            bench.get("bsr_rank_number"), bench.get("bsr_category"),
            live_bsr, live_bsr_category,
        ),
        "offer_section": validate_offer_section(snapshot),
        "economics": validate_economics_internal(snapshot),
        "demand": validate_demand_internal(snapshot),
        "internally_validated": {
            "label": INTERNAL_ONLY_LABEL,
            "note": "seller/offer, economics and demand are coverage/provenance checks — never benchmarked against the CSVs",
        },
    }


def pack_tokens_signal(title: Any) -> List[tuple]:
    """Re-export of the store's pack extractor to avoid importing it eagerly."""
    from asin_benchmark_store import pack_tokens

    return pack_tokens(title)


# ---------------------------------------------------------------------------
# Batch metrics (Phase 4)
# ---------------------------------------------------------------------------

def summarize_batch(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    matched = [r for r in reports if r["identity"]["asin_match"] == "pass"]
    unmatched = [r for r in reports if r["identity"]["asin_match"] == "fail"]

    title_statuses = [r["identity"]["title_status"] for r in matched]
    price_classes = [r["price"]["classification"] for r in matched]
    review_comparable = [r for r in matched if r["reviews"]["comparable"]]
    review_declines = [r for r in review_comparable if r["reviews"]["trend"] == "decline_flag"]
    prime_comparable = [r for r in matched if r["prime_fba"]["comparable"]]
    bsr_comparable = [r for r in matched if r["bsr"]["comparable"]]

    offer_present = [r for r in matched if r["offer_section"]["present"]]
    offer_coverage = [r["offer_section"]["coverage"] for r in offer_present]
    buy_box_present = [r for r in matched if r["offer_section"]["buy_box_present"]]
    consistent = [r for r in offer_present if r["offer_section"]["internal_consistency"]["status"] == "consistent"]

    econ_readiness = [r["economics"]["readiness"] for r in matched]

    title_match_count = sum(1 for s in title_statuses if s == "match")
    title_likely_count = sum(1 for s in title_statuses if s == "likely_match")
    title_available = sum(1 for s in title_statuses if s != "unavailable")

    return {
        "scope": "benchmark-matched rows only for measured rates; unmatched rows counted separately",
        "benchmark_matched_asin_count": len(matched),
        "unmatched_asin_count": len(unmatched),
        "conflicting_benchmark_reference_count": sum(1 for r in matched if r.get("benchmark_source_files") and len(r["benchmark_source_files"]) > 1),
        "identity_title_match_rate": round(title_match_count / title_available, 4) if title_available else None,
        "identity_title_likely_match_count": title_likely_count,
        "identity_title_unavailable_count": len(title_statuses) - title_available,
        "pack_mismatch_block_count": sum(1 for r in matched if r["identity"]["pack_mismatch_block"]),
        "price_comparable_count": sum(1 for c in price_classes if c != "unavailable"),
        "price_exact_count": price_classes.count("exact"),
        "price_within_tolerance_count": price_classes.count("within_tolerance"),
        "price_moderate_drift_count": price_classes.count("moderate_drift"),
        "price_material_drift_count": price_classes.count("material_drift"),
        "price_unavailable_count": price_classes.count("unavailable"),
        "review_comparable_count": len(review_comparable),
        "review_decline_flag_count": len(review_declines),
        "prime_fba_comparable_count": len(prime_comparable),
        "bsr_comparable_count": len(bsr_comparable),
        "bsr_category_mismatch_count": sum(1 for r in matched if not r["bsr"]["comparable"] and r["bsr"]["category_context"] == "mismatch"),
        "market_snapshot_coverage": {
            "seller_roster_present": len(offer_present),
            "coverage_full": offer_coverage.count("full"),
            "coverage_partial": offer_coverage.count("partial"),
            "coverage_unknown": offer_coverage.count("unknown"),
            "buy_box_present": len(buy_box_present),
            "seller_counts_internally_consistent": len(consistent),
            "seller_counts_inconsistent": len(offer_present) - len(consistent),
        },
        "economics_readiness": {
            "decision_ready": econ_readiness.count("decision_ready"),
            "assumption_based": econ_readiness.count("assumption_based"),
            "unavailable": econ_readiness.count("unavailable"),
        },
        "benchmark_limitations": {
            "capture_time_unknown": True,
            "note": "benchmark capture time unknown; reference only, not freshness proof",
            "no_seller_roster_benchmark": True,
            "no_economics_benchmark": True,
            "no_demand_truth_benchmark": True,
            "price_bsr_drift_expected": "Price and BSR may legitimately change; comparison validates mapping and plausibility, not live market stability",
        },
    }


# ---------------------------------------------------------------------------
# CLI (offline)
# ---------------------------------------------------------------------------

def _cli() -> None:
    import json as _json
    import sys

    args = sys.argv[1:]
    if not args or args[0] != "compare":
        raise SystemExit("usage: python benchmark_validation.py compare --benchmark <store.json> --snapshots <snapshots.json>")
    opts = {}
    i = 1
    while i < len(args):
        if args[i] in ("--benchmark", "--snapshots") and i + 1 < len(args):
            opts[args[i]] = args[i + 1]
            i += 2
        else:
            raise SystemExit(f"unknown arg: {args[i]}")
    bench_store = _json.load(open(opts["--benchmark"], encoding="utf-8"))
    snapshots = _json.load(open(opts["--snapshots"], encoding="utf-8"))
    if isinstance(snapshots, dict) and "snapshots" in snapshots:
        snapshots = snapshots["snapshots"]
    canonical = bench_store.get("canonical", {})
    reports = []
    for snap in snapshots:
        asin = (snap.get("asin") or "").upper()
        bench = canonical.get(asin)
        if bench is None:
            reports.append(
                {
                    "asin": asin,
                    "identity": {"asin_match": "fail"},
                    "note": "no benchmark reference for this ASIN",
                }
            )
            continue
        reports.append(compare_benchmark_record(bench, snap))
    print(_json.dumps({"reports": reports, "metrics": summarize_batch(reports)}, indent=2))


if __name__ == "__main__":
    _cli()
