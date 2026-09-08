"""Read-only Costco -> Amazon matching coverage report (hardening batch).

Measures how many cached Amazon candidates receive a trustworthy local
Costco cost (and therefore usable economics) from the existing matcher —
the data bottleneck before ranking. It is a pure diagnostic:

- Reads ONLY local files:
    * data/scanner-search-cache.json          (candidate cache)
    * data/costco-items.csv                   (legacy CSV layer)
    * data/costco-product-detail.json         (layer 2, optional)
    * data/costco-invoice-confirmed.json      (layer 3, optional)
    * data/costco-amazon-mapping.json         (verified ledger, optional)
  Paths come from the same env vars the scanner uses
  (SCANNER_SEARCH_CACHE_PATH, COSTCO_CSV_PATH, COSTCO_CATALOG_DETAIL_PATH,
  COSTCO_INVOICE_PATH, COSTCO_AMAZON_MAPPING_PATH).
- Never imports main, never calls a route, never touches a provider,
  never performs network calls, and never modifies any input file.
- Writes ONLY the explicit outputs requested on the command line.

Every percentage shows its visible denominator (x/y):
  match_coverage      = (exact + invoice_confirmed + high_confidence) / eligible
  cogs_coverage       = rows with a real Costco COGS / eligible
  economics_ready     = price + COGS + usable FBA fee / eligible
  opportunity_complete = economics_ready + monthly sales + seller data / eligible
  eligible = candidates with a valid ASIN or product URL AND a name.

CLI
---
    python coverage_report.py
    python coverage_report.py --cache data/scanner-search-cache.json
    python coverage_report.py --out data/scanner-coverage-report.json
    python coverage_report.py --csv data/scanner-review-queue.csv
    python coverage_report.py --top 50 --csv data/scanner-top-opportunities.csv

The review-queue CSV has EXACTLY the 24 batch-specified columns; the
top-opportunity export ranks scored non-mismatch rows (default 50) by
opportunity_score, nulls last, and only ever writes to an explicit path.

Exit codes: 0 success; 2 unreadable cache/catalog (nothing written).
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import amazon_search
import costco_api_client
import costco_client
import opportunity_analytics
import product_analysis

PURCHASE_GATE = product_analysis.PURCHASE_GATE_MATCH_QUALITIES  # exact | invoice_confirmed | high_confidence
GATE_BUCKETS = ("exact", "invoice_confirmed", "high_confidence")

# Batch-specified review-queue columns (exact order, never renamed).
REVIEW_QUEUE_COLUMNS = (
    "asin",
    "amazon_title",
    "product_url",
    "amazon_price",
    "buy_box_price",
    "estimated_monthly_sales",
    "total_sellers",
    "fba_sellers",
    "costco_match_quality",
    "costco_item_name",
    "costco_cost",
    "costco_cost_basis",
    "cost_match_reason",
    "economics_confidence",
    "economics_status",
    "estimated_net_profit",
    "estimated_roi_pct",
    "missing_fields",
    "verification_task",
    "opportunity_readiness",
    "recommended_next_step",
    "cache_source",
    "observed_at",
    "enriched_at",
)

TOP_OPPORTUNITY_COLUMNS = (
    "rank",
    "asin",
    "amazon_title",
    "opportunity_score",
    "opportunity_score_reasons",
    "opportunity_readiness",
    "recommended_next_step",
    "match_readiness",
    "data_completeness_score",
    "freshness_label",
    "costco_match_quality",
    "costco_item_name",
    "costco_cost",
    "costco_cost_basis",
    "amazon_price",
    "estimated_monthly_sales",
    "fba_sellers",
    "missing_fields",
)

_REASON_TASK = (
    ("weight", "confirm_weight"),
    ("count", "confirm_pack"),
    ("pack", "confirm_pack"),
    ("flavor", "confirm_flavor"),
    ("formula", "confirm_flavor"),
    ("UPC", "confirm_upc"),
    ("dimension", "confirm_dimension"),
)


def _verification_task(quality: Optional[str], reason: Optional[str]) -> str:
    if quality in ("exact", "invoice_confirmed"):
        return "none"
    if quality == "high_confidence":
        return "confirm_variant"
    if quality == "candidate":
        return "confirm_weight_or_pack"
    if quality == "unknown":
        return "provide_upc_or_weight"
    if quality == "mismatch":
        text = reason or ""
        for needle, task in _REASON_TASK:
            if needle in text:
                return task
        return "review"
    return "unmatched"


def _missing_fields(candidate: Dict[str, Any], match: Optional[Dict[str, Any]]) -> List[str]:
    missing = []
    if candidate.get("amazon_price") is None:
        missing.append("amazon_price")
    if not (candidate.get("upc") or candidate.get("gtin") or candidate.get("ean")):
        missing.append("upc")
    if candidate.get("weight_lbs") is None and candidate.get("weight") is None:
        missing.append("weight")
    if match is None:
        missing.append("costco_cost")
        missing.append("fba_fee")
        return missing
    if match.get("costco_cost") is None:
        missing.append("costco_cost")
    if candidate.get("fba_fee") is None and not match.get("weight_lbs"):
        missing.append("fba_fee")
    return missing


def _title_similarity(amazon_name: str, costco_item_name: str) -> float:
    return costco_client._title_similarity(amazon_name, costco_item_name)


def _best_csv_row(name: str) -> Tuple[Optional[Dict], float]:
    """Best legacy-CSV row by normalized title ratio (read-only, mirrors
    the pre-selection in costco_client.get_costco_price for diagnostics)."""
    path = costco_client._resolve_csv_path()
    if not os.path.exists(path):
        return None, 0.0

    with open(path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    best, best_ratio = None, 0.0
    for row in rows:
        ratio = _title_similarity(name, row.get("item_name") or "")
        if ratio > best_ratio:
            best, best_ratio = row, ratio
    return best, best_ratio


def _blocked_csv_probe(name: str) -> Optional[Dict[str, Any]]:
    """Diagnostic-only surface for a CSV row that fingerprints as a known
    conflict (mismatch).

    resolve_costco_cost intentionally returns None for hard identity
    conflicts so the discovery pipeline never passes a failed match as a
    cost. The coverage report, however, needs to SEE those blocked rows
    (their reason drives the blocked_mismatch readiness) without ever
    treating them as a cost basis. This probe reuses the same fuzzy-gate
    and fingerprint the CSV layer uses, and returns a cost-less mismatch
    record when the row genuinely conflicts.
    """
    best, ratio = _best_csv_row(name)
    if best is None or ratio < costco_client.MATCH_RATIO_THRESHOLD:
        return None
    eq = costco_client.product_equivalence(name, best.get("item_name") or "")
    if eq.get("match_quality") != "mismatch":
        return None
    return {
        "match_quality": "mismatch",
        "match_reason": eq.get("match_reason") or "Known identity conflict (CSV row).",
        "item_name": best.get("item_name"),
        "costco_cost": None,
        "cost_status": "blocked_mismatch",
        "source": "csv:diagnostic",
    }


def _load_ledger() -> Dict[str, str]:
    """Verified ASIN -> costco item_name ledger (read-only)."""
    raw = os.getenv("COSTCO_AMAZON_MAPPING_PATH")
    if raw:
        path = raw if os.path.isabs(raw) else os.path.join(costco_api_client._project_root(), raw)
    else:
        path = os.path.join(costco_api_client._project_root(), "data", "costco-amazon-mapping.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).upper(): str(v) for k, v in data.items()}


def _ledger_hits(ledger: Dict[str, str], rows: List[Dict[str, Any]]) -> int:
    return sum(1 for r in rows if r.get("asin") and ledger.get(str(r.get("asin")).upper()))


def _economics_confidence(price, cost, fee_usable) -> Optional[str]:
    if price is None or cost is None:
        return "unavailable"
    if fee_usable:
        return "estimated"
    return "provisional"


def analyze_candidates(cache_path: Optional[str] = None) -> Dict[str, Any]:
    """Run every cached candidate through the existing local matcher and
    bucket the results. Zero writes, zero network."""
    candidates = amazon_search.load_cached_candidates()
    total = len(candidates)
    ledger = _load_ledger()
    meta = amazon_search.cache_meta()

    quality_counts = Counter()
    layer_counts = Counter()
    missing_reasons = Counter()
    mismatch_reasons = Counter()
    similarity_histogram = Counter()
    verification_task_counts = Counter()
    readiness_counts = Counter()
    score_reason_counts = Counter()

    eligible = 0
    gate = 0
    cogs_found = 0
    purchase_authorized = 0
    price_present = 0
    fba_fee_present = 0
    upc_present = 0
    weight_evidence = 0
    estimated_ready = 0
    provisional = 0
    mapping_verification = 0
    opportunity_complete = 0

    rows = []
    scored_rows = []

    for c in candidates:
        name = c.get("name") or ""
        asin = c.get("asin")
        product_url = c.get("product_url")
        amazon_price = c.get("amazon_price")

        eligible_this = bool(name) and bool(asin or product_url)
        if eligible_this:
            eligible += 1

        match = costco_api_client.resolve_costco_cost(
            name,
            amazon_asin=asin,
            amazon_upc=c.get("upc") or c.get("ean"),
            amazon_brand=c.get("brand"),
        )
        if match is None:
            # Hard conflicts must not fabricate costs, but the report still
            # needs to surface them as blocked (with reasons) rather than
            # silently reading "no candidate".
            match = _blocked_csv_probe(name)
        quality = match.get("match_quality") if match else None
        layer = match.get("source") if match else "none"

        if quality:
            quality_counts[quality] += 1
        else:
            quality_counts["unmatched"] += 1
        layer_counts[layer] += 1

        if quality in PURCHASE_GATE:
            gate += 1
        if match and match.get("costco_cost") is not None:
            cogs_found += 1
        if match and match.get("cost_is_purchase_authorized"):
            purchase_authorized += 1
        if amazon_price is not None:
            price_present += 1
        if c.get("fba_fee") is not None:
            fba_fee_present += 1
        if c.get("upc") or c.get("gtin") or c.get("ean"):
            upc_present += 1
        if c.get("weight_lbs") is not None or c.get("weight") is not None:
            weight_evidence += 1

        fee_usable = c.get("fba_fee") is not None or (match or {}).get("weight_lbs") is not None
        if quality in PURCHASE_GATE and match and match.get("costco_cost") is not None:
            if fee_usable:
                estimated_ready += 1
            else:
                provisional += 1
        elif match and match.get("costco_cost") is not None:
            mapping_verification += 1

        if (
            estimated_ready_dims(
                quality, match, fee_usable, amazon_price, c, eligible_this
            )
        ):
            opportunity_complete += 1

        if quality == "mismatch" and match:
            mismatch_reasons[match.get("match_reason") or "unknown reason"] += 1

        for field in _missing_fields(c, match):
            missing_reasons[field] += 1

        if quality:
            score = match.get("match_reason") or quality
        else:
            best, ratio = _best_csv_row(name)
            score = "closest CSV title ratio %.2f (%s)" % (ratio, (best or {}).get("item_name") or "none")
            if ratio < 0.5:
                bucket = "0.00-0.50"
            elif ratio < 0.70:
                bucket = "0.50-0.70"
            elif ratio < 0.85:
                bucket = "0.70-0.85"
            else:
                bucket = "0.85+"
            similarity_histogram[bucket] += 1

        econ_confidence = _economics_confidence(amazon_price, (match or {}).get("costco_cost"), fee_usable)
        econ_status = (
            "estimated_fee_stack" if econ_confidence == "estimated"
            else "needs_fee_verification" if econ_confidence == "provisional"
            else "missing_amazon_price" if amazon_price is None
            else "missing_costco_cogs"
        )

        row = {
            "asin": asin,
            "amazon_title": name,
            "product_url": product_url,
            "amazon_price": amazon_price,
            "buy_box_price": c.get("buy_box_price"),
            "estimated_monthly_sales": c.get("monthly_sales_estimate"),
            "total_sellers": c.get("total_sellers"),
            "fba_sellers": c.get("fba_sellers"),
            "costco_match_quality": quality or "unmatched",
            "costco_item_name": match.get("item_name") if match else None,
            "costco_cost": match.get("costco_cost") if match else None,
            "costco_cost_basis": match.get("costco_cost_basis") if match else None,
            "cost_match_reason": match.get("match_reason") if match else None,
            "economics_confidence": econ_confidence,
            "economics_status": econ_status,
            "estimated_net_profit": None,
            "estimated_roi_pct": None,
            "missing_fields": ",".join(_missing_fields(c, match)),
            "verification_task": None,
            "opportunity_readiness": None,
            "recommended_next_step": None,
            "cache_source": meta.get("cache_source"),
            "observed_at": c.get("observed_at"),
            "enriched_at": c.get("enriched_at"),
        }

        analytics_input = {
            "name": name,
            "asin": asin,
            "product_url": product_url,
            "amazon_price": amazon_price,
            "costco_cost": row["costco_cost"],
            "match_quality": quality,
            "match_reason": row["cost_match_reason"],
            "cost_match_reason": row["cost_match_reason"],
            "economics_confidence": econ_confidence,
            "economics_status": econ_status,
            "net_profit": None,
            "roi_pct": None,
            "fba_fee": c.get("fba_fee"),
            "monthly_sales_estimate": row["estimated_monthly_sales"],
            "total_sellers": row["total_sellers"],
            "fba_sellers": row["fba_sellers"],
        }
        fields = opportunity_analytics.opportunity_fields(analytics_input, meta)
        row["verification_task"] = fields["primary_verification_task"] or _verification_task(
            quality, row["cost_match_reason"]
        )
        row["opportunity_readiness"] = fields["opportunity_readiness"]
        row["recommended_next_step"] = fields["recommended_next_step"]

        verification_task_counts[row["verification_task"]] += 1
        readiness_counts[fields["opportunity_readiness"]] += 1
        for reason in fields["opportunity_score_reasons"]:
            score_reason_counts[reason.split(" (")[0]] += 1

        rows.append(row)

        if quality != "mismatch":
            scored_rows.append({
                "row": row,
                "score": fields["opportunity_score"],
                "reasons": fields["opportunity_score_reasons"],
            })

    match_pct = _pct(gate, eligible)
    cogs_pct = _pct(cogs_found, eligible)
    econ_pct = _pct(estimated_ready, eligible)
    complete_pct = _pct(opportunity_complete, eligible)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cache": {
            "path": cache_path or amazon_search._cache_path(),
            "source": meta.get("cache_source"),
            "fetched_at": meta.get("cache_fetched_at"),
            "schema_version": meta.get("cache_schema_version"),
            "cache_status": meta.get("cache_status"),
            "candidates": total,
        },
        "totals": {
            "total_candidates": total,
            "eligible": eligible,
            "exact": quality_counts.get("exact", 0),
            "invoice_confirmed": quality_counts.get("invoice_confirmed", 0),
            "high_confidence": quality_counts.get("high_confidence", 0),
            "candidate": quality_counts.get("candidate", 0),
            "mismatch": quality_counts.get("mismatch", 0),
            "unknown": quality_counts.get("unknown", 0),
            "unmatched": quality_counts.get("unmatched", 0),
            "match_coverage_count": gate,
            "match_coverage_denominator": eligible,
            "match_coverage_percent": match_pct,
            "costco_cogs_found": cogs_found,
            "cogs_coverage_count": cogs_found,
            "cogs_coverage_denominator": eligible,
            "cogs_coverage_percent": cogs_pct,
            "economics_ready_count": estimated_ready,
            "economics_ready_denominator": eligible,
            "economics_ready_percent": econ_pct,
            "opportunity_complete_count": opportunity_complete,
            "opportunity_complete_denominator": eligible,
            "opportunity_complete_percent": complete_pct,
            "cost_is_purchase_authorized": purchase_authorized,
            "price_present": price_present,
            "fba_fee_present": fba_fee_present,
            "upc_present": upc_present,
            "weight_evidence_present": weight_evidence,
            "estimated_economics_ready": estimated_ready,
            "provisional_economics": provisional,
            "mapping_verification_required": mapping_verification,
        },
        "per_layer": dict(layer_counts),
        "ledger_entries": len(ledger),
        "ledger_hits": _ledger_hits(ledger, candidates),
        "missing_data_reasons": dict(missing_reasons),
        "top_mismatch_reasons": dict(mismatch_reasons.most_common(10)),
        "title_similarity_histogram": dict(similarity_histogram),
        "verification_task_counts": dict(verification_task_counts.most_common()),
        "opportunity_readiness_counts": dict(readiness_counts.most_common()),
        "opportunity_score_reason_counts": dict(score_reason_counts.most_common(15)),
        "rows": rows,
        "top_opportunities": _top_opportunities(scored_rows),
    }


def estimated_ready_dims(quality, match, fee_usable, amazon_price, candidate, eligible_this) -> bool:
    """opportunity_complete requires: price + COGS + usable fee + monthly
    sales + seller data on an eligible row."""
    if not eligible_this:
        return False
    return (
        quality in PURCHASE_GATE
        and amazon_price is not None
        and match is not None
        and match.get("costco_cost") is not None
        and fee_usable
        and candidate.get("monthly_sales_estimate") is not None
        and candidate.get("total_sellers") is not None
        and candidate.get("fba_sellers") is not None
    )


def _pct(count: int, denominator: int) -> float:
    return round((count / denominator) * 100, 1) if denominator else 0.0


def _top_opportunities(scored_rows: List[Dict[str, Any]], limit: int = 50) -> List[Dict[str, Any]]:
    """Scored non-mismatch rows sorted by opportunity_score, nulls last."""
    def key(item):
        score = item["score"]
        if score is None:
            return (1, 0.0)
        return (0, -float(score))

    ranked = sorted(scored_rows, key=key)
    return [
        {
            "rank": i + 1,
            "score": item["score"],
            "score_reasons": item["reasons"],
            **item["row"],
        }
        for i, item in enumerate(ranked[:limit])
    ]


def export_review_queue(report: Dict[str, Any], path: str) -> str:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_QUEUE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in report["rows"]:
            writer.writerow(row)
    return path


def export_top_opportunities(report: Dict[str, Any], path: str) -> str:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TOP_OPPORTUNITY_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in report["top_opportunities"]:
            writer.writerow(row)
    return path


def _print_summary(report: Dict[str, Any]) -> None:
    t = report["totals"]
    denom = t["eligible"]
    print("coverage report: %d cached candidates (%d eligible)" % (t["total_candidates"], denom))
    print("  exact:                %d" % t["exact"])
    print("  invoice_confirmed:    %d" % t["invoice_confirmed"])
    print("  high_confidence:      %d" % t["high_confidence"])
    print("  candidate:            %d" % t["candidate"])
    print("  mismatch:             %d" % t["mismatch"])
    print("  unknown:              %d" % t["unknown"])
    print("  unmatched (no row):   %d" % t["unmatched"])
    print("  match coverage:       %d/%d = %.1f%%" % (
        t["match_coverage_count"], denom, t["match_coverage_percent"]))
    print("  cogs coverage:        %d/%d = %.1f%%" % (
        t["cogs_coverage_count"], denom, t["cogs_coverage_percent"]))
    print("  economics ready:      %d/%d = %.1f%%" % (
        t["economics_ready_count"], denom, t["economics_ready_percent"]))
    print("  opportunity complete: %d/%d = %.1f%%" % (
        t["opportunity_complete_count"], denom, t["opportunity_complete_percent"]))
    print("  costco cogs found:    %d" % t["costco_cogs_found"])
    print("  purchase authorized:  %d" % t["cost_is_purchase_authorized"])
    print("  price present:        %d" % t["price_present"])
    print("  fba fee present:      %d" % t["fba_fee_present"])
    print("  upc present:          %d" % t["upc_present"])
    print("  weight evidence:      %d" % t["weight_evidence_present"])
    print("  provisional:          %d" % t["provisional_economics"])
    print("  mapping verification: %d" % t["mapping_verification_required"])
    print("per layer:", report["per_layer"])
    print("ledger entries/hits:", report["ledger_entries"], "/", report["ledger_hits"])
    if report["missing_data_reasons"]:
        print("missing data:", report["missing_data_reasons"])
    if report["verification_task_counts"]:
        print("verification tasks:", report["verification_task_counts"])
    if report["opportunity_readiness_counts"]:
        print("opportunity readiness:", report["opportunity_readiness_counts"])
    if report["top_mismatch_reasons"]:
        print("top mismatch reasons:")
        for reason, count in report["top_mismatch_reasons"].items():
            print("  %3d  %s" % (count, reason))
    if report["title_similarity_histogram"]:
        print("title similarity (unmatched only):", report["title_similarity_histogram"])
    if report["top_opportunities"]:
        print("top opportunities (scored, non-mismatch):")
        for item in report["top_opportunities"][:10]:
            print("  #%d  score=%s  %s (%s)" % (
                item["rank"], item["score"], item["amazon_title"] or item["asin"], item["costco_match_quality"]))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Costco->Amazon matching coverage report (zero network, zero writes to inputs).",
    )
    parser.add_argument("--cache", default=None, help="candidate cache path (default: scanner cache path)")
    parser.add_argument("--out", default=None, help="write the JSON report to this path")
    parser.add_argument("--csv", default=None, help="write the 24-column review-queue CSV to this path")
    parser.add_argument("--top", type=int, default=None, help="top-opportunity export size (default 50); requires --csv")
    args = parser.parse_args(argv)

    if args.top is not None and args.top < 1:
        print("error: --top must be >= 1")
        return 2
    if args.top is not None and args.csv is None:
        print("error: --top requires --csv")
        return 2

    try:
        if args.cache:
            os.environ["SCANNER_SEARCH_CACHE_PATH"] = args.cache
        report = analyze_candidates(cache_path=args.cache)
    except (OSError, ValueError) as e:
        print("error: %s" % e)
        return 2

    _print_summary(report)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print("report written: %s" % args.out)
    if args.csv:
        export_review_queue(report, args.csv)
        print("review queue csv written: %s" % args.csv)
        top_limit = args.top if args.top is not None else 50
        if top_limit:
            top_path = args.csv.rsplit(".", 1)[0] + "-top-%d.csv" % top_limit
            export_top_opportunities(report, top_path)
            print("top opportunities csv written: %s" % top_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
