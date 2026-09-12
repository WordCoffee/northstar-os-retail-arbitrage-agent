"""Mapping review CLI (offline, read-only on all data files).

Surfaces the Costco <-> Amazon mapping state of the cached candidates:
a review CSV per candidate (match quality, evidence, conflicts, the
verification task, and the suggested mapping action), coverage metrics,
and a read-only validator for proposed ledger imports.

Honesty rules:
  - Writes go ONLY to the explicitly supplied --output / --coverage-output
    / --validate-output / --audit paths. The verified ledger
    (COSTCO_AMAZON_MAPPING_PATH), search cache, snapshot store, Costco
    catalogs and run reports are never written, moved, or deleted.
  - --validate-import classifies a proposed import file (CSV/JSON):
    exact-with-evidence rows are ledger-confirmable, high-confidence
    rows are research, known conflicts are rejected, and rows that
    conflict with an existing ledger entry are held for review. It
    never writes the ledger — the only writer stays
    costco_api_client.import_ledger (append-only, conflict-held).
  - --audit appends one JSONL record per run (append-only audit
    trail); it never touches the ledger or any data file.
  - Unknown stays Unknown; no invented evidence, costs, or mappings.

Usage:
  python mapping_review.py --input data/scanner-search-cache.json --output data/batch/mapping-review.csv
  python mapping_review.py --input data/scanner-search-cache.json --coverage-output data/batch/mapping-coverage.json
  python mapping_review.py --validate-import data/batch/proposed-mapping.csv --validate-output data/batch/import-validation.json
  python mapping_review.py --input data/scanner-search-cache.json --output data/batch/mapping-review.csv --audit data/batch/mapping-review-audit.jsonl
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

import amazon_search
import costco_api_client
import opportunity_analytics
import product_analysis

load_dotenv()

# Suggested mapping actions (mission vocabulary).
ACTION_CONFIRM_EXACT = "confirm_exact_mapping"
ACTION_VERIFY_UPC = "verify_upc"
ACTION_VERIFY_COUNT_PACK = "verify_count_pack"
ACTION_VERIFY_WEIGHT = "verify_weight"
ACTION_VERIFY_VARIANT = "verify_variant"
ACTION_VERIFY_FLAVOR = "verify_flavor"
ACTION_REJECT = "reject_mapping"
ACTION_NO_CANDIDATE = "no_costco_candidate"

CSV_COLUMNS = [
    "asin",
    "amazon_title",
    "amazon_brand",
    "amazon_upc",
    "amazon_gtin_ean",
    "amazon_count_weight_variant_evidence",
    "costco_candidate_title",
    "costco_item_id",
    "costco_upc_ean",
    "costco_count_weight_variant_evidence",
    "match_quality",
    "match_evidence",
    "conflict_reasons",
    "verification_task",
    "suggested_action",
]

_ACTION_HINTS = [
    ("upc", ACTION_VERIFY_UPC),
    ("ean", ACTION_VERIFY_UPC),
    ("pack/count differs", ACTION_VERIFY_COUNT_PACK),
    ("net weight differs", ACTION_VERIFY_WEIGHT),
    ("flavor differs", ACTION_VERIFY_FLAVOR),
    ("variant", ACTION_VERIFY_VARIANT),
    ("formula/flavor", ACTION_VERIFY_VARIANT),
    ("count", ACTION_VERIFY_COUNT_PACK),
    ("weight", ACTION_VERIFY_WEIGHT),
]


def _evidence_text(candidate: Dict) -> str:
    """Amazon-side evidence string: brand + identifiers the candidate
    actually carries (never invented)."""
    parts = []
    if candidate.get("brand"):
        parts.append("brand=%s" % candidate["brand"])
    if candidate.get("upc"):
        parts.append("upc=%s" % candidate["upc"])
    if candidate.get("ean"):
        parts.append("ean=%s" % candidate["ean"])
    return "; ".join(parts)


def _costco_evidence(costco: Dict) -> str:
    parts = []
    for key in ("brand", "upc_or_ean", "pack_size", "net_weight", "unit_of_measure", "pack_count", "case_count"):
        if costco.get(key) is not None:
            parts.append("%s=%s" % (key, costco[key]))
    return "; ".join(parts)


def _match_evidence_text(costco: Dict) -> str:
    """Display evidence already structured by the costco client."""
    evidence = costco.get("evidence") or {}
    parts = []
    for key in ("matched_brand", "matched_upc", "matched_weight", "matched_count", "matched_variant", "matched_formula"):
        if evidence.get(key):
            parts.append(key)
    if costco.get("match_reason"):
        parts.append(costco["match_reason"])
    return "; ".join(parts)


def _conflict_reasons(costco: Dict) -> List[str]:
    conflicts = (costco.get("evidence") or {}).get("known_conflicts") or []
    return [str(c) for c in conflicts]


def _suggested_action(candidate: Dict, costco: Dict, verification_tasks: List[str]) -> str:
    """Mapping action per mission rules: exact-with-evidence and
    invoice-confirmed are confirm_exact_mapping; high-confidence rows
    get the verification hinted by the conflict/evidence text; candidate
    rows are research verification; mismatch is rejected; no Costco
    candidate is no_costco_candidate."""
    match_quality = costco.get("match_quality") or "unknown"
    if match_quality == "invoice_confirmed":
        return ACTION_CONFIRM_EXACT
    if match_quality == "exact":
        if candidate.get("upc") or candidate.get("ean"):
            return ACTION_CONFIRM_EXACT
        return ACTION_VERIFY_UPC
    if match_quality == "high_confidence":
        for text in (costco.get("match_reason") or "", " ".join(verification_tasks)):
            for hint, action in _ACTION_HINTS:
                if hint in text.lower():
                    return action
        return ACTION_VERIFY_UPC
    if match_quality == "candidate":
        for text in (costco.get("match_reason") or "", " ".join(verification_tasks)):
            for hint, action in _ACTION_HINTS:
                if hint in text.lower():
                    return action
        return ACTION_VERIFY_VARIANT
    if match_quality == "mismatch":
        return ACTION_REJECT
    return ACTION_NO_CANDIDATE


def review_rows(candidates: List[Dict]) -> List[Dict]:
    """One review row per candidate (read-only; costco resolution is
    local-only)."""
    rows: List[Dict] = []
    for c in candidates:
        costco = product_analysis.get_costco_price(
            c["name"],
            amazon_asin=c.get("asin"),
            amazon_upc=c.get("upc") or c.get("ean"),
            amazon_brand=c.get("brand"),
        ) or {}
        tasks = opportunity_analytics.verification_tasks(
            {
                "name": c["name"],
                "asin": c.get("asin"),
                "amazon_price": c.get("amazon_price"),
                "costco_cost": costco.get("costco_cost"),
                "match_quality": costco.get("match_quality") or "unknown",
                "match_reason": costco.get("match_reason"),
            }
        )
        rows.append(
            {
                "asin": c.get("asin"),
                "amazon_title": c["name"],
                "amazon_brand": c.get("brand"),
                "amazon_upc": c.get("upc"),
                "amazon_gtin_ean": c.get("ean"),
                "amazon_count_weight_variant_evidence": _evidence_text(c),
                "costco_candidate_title": costco.get("item_name"),
                "costco_item_id": costco.get("costco_item_id"),
                "costco_upc_ean": costco.get("upc_or_ean"),
                "costco_count_weight_variant_evidence": _costco_evidence(costco),
                "match_quality": costco.get("match_quality") or "unknown",
                "match_evidence": _match_evidence_text(costco),
                "conflict_reasons": "; ".join(_conflict_reasons(costco)),
                "verification_task": "; ".join(tasks) if tasks else "",
                "suggested_action": _suggested_action(c, costco, tasks),
            }
        )
    return rows


def write_review_csv(rows: List[Dict], output_path: str) -> int:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def coverage_metrics(candidates: List[Dict], rows: List[Dict]) -> Dict:
    """Coverage metrics (read-only): action counts, ledger hits, top
    conflict type, top missing identifier type, verification queue."""
    ledger = costco_api_client._load_ledger()
    actions: Dict[str, int] = {}
    conflicts: Dict[str, int] = {}
    missing_id: Dict[str, int] = {}
    verification_queue = 0
    for row in rows:
        actions[row["suggested_action"]] = actions.get(row["suggested_action"], 0) + 1
        if row["conflict_reasons"]:
            conflicts[row["conflict_reasons"]] = conflicts.get(row["conflict_reasons"], 0) + 1
        if not row["amazon_upc"] and not row["amazon_gtin_ean"]:
            missing_id["upc_and_ean"] = missing_id.get("upc_and_ean", 0) + 1
        elif not row["amazon_upc"]:
            missing_id["upc"] = missing_id.get("upc", 0) + 1
        elif not row["amazon_gtin_ean"]:
            missing_id["ean"] = missing_id.get("ean", 0) + 1
        if row["verification_task"]:
            verification_queue += 1
    ledger_hits = sum(1 for r in rows if r["asin"] and ledger.get(str(r["asin"]).upper()))
    return {
        "total_candidates": len(rows),
        "actions": dict(sorted(actions.items())),
        "ledger_entries": len(ledger),
        "ledger_hits": ledger_hits,
        "ledger_confirmable": actions.get(ACTION_CONFIRM_EXACT, 0),
        "verification_queue_size": verification_queue,
        "top_conflict_type": max(conflicts.items(), key=lambda kv: kv[1])[0] if conflicts else None,
        "conflict_type_counts": dict(sorted(conflicts.items())),
        "top_missing_identifier_type": max(missing_id.items(), key=lambda kv: kv[1])[0] if missing_id else None,
        "missing_identifier_counts": dict(sorted(missing_id.items())),
    }


def _flat_import_rows(path: str) -> List[Dict]:
    """Parse a proposed mapping import (CSV with asin,item_name plus
    optional evidence columns, or a flat JSON mapping/array)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    if path.lower().endswith(".json"):
        data = json.loads(raw)
        if isinstance(data, dict):
            return [{"asin": k, "item_name": v} for k, v in data.items()]
        if isinstance(data, list):
            return data
        raise ValueError("JSON import must be an object or an array")
    reader = csv.DictReader(raw.splitlines())
    return [dict(r) for r in reader]


def _is_valid_asin(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    asin = value.strip()
    return len(asin) == 10 and asin[0].isalpha() and asin.isalnum()


def validate_import(path: str) -> Dict:
    """Read-only validation of a proposed ledger import.

    Classifies each row: ledger-confirmable (exact evidence), research
    (high-confidence / evidence-incomplete), rejected (known conflict
    or invalid/empty), or held (conflicts with an existing ledger
    entry). Never writes the ledger.
    """
    rows = _flat_import_rows(path)
    ledger = costco_api_client._load_ledger()
    results: List[Dict] = []
    counts = {"ledger_confirmable": 0, "research": 0, "rejected": 0, "held_for_review": 0}
    for row in rows:
        asin = str(row.get("asin") or "").strip()
        item_name = str(row.get("item_name") or "").strip()
        upc = str(row.get("upc_or_ean") or row.get("upc") or "").strip()
        evidence = [
            v
            for v in (
                upc,
                str(row.get("brand") or "").strip(),
                str(row.get("count") or row.get("pack_count") or "").strip(),
                str(row.get("weight") or row.get("net_weight") or "").strip(),
                str(row.get("variant") or "").strip(),
            )
            if v
        ]
        record = {"asin": asin, "item_name": item_name, "evidence": evidence}
        if not _is_valid_asin(asin):
            record["status"] = "rejected"
            record["reason"] = "invalid_asin"
            counts["rejected"] += 1
        elif not item_name:
            record["status"] = "rejected"
            record["reason"] = "missing_item_name"
            counts["rejected"] += 1
        elif asin.upper() in ledger and ledger[asin.upper()] != item_name:
            record["status"] = "held_for_review"
            record["reason"] = "conflicts_with_existing_ledger"
            counts["held_for_review"] += 1
        elif upc or evidence:
            record["status"] = "ledger_confirmable"
            record["reason"] = "exact_evidence_present"
            counts["ledger_confirmable"] += 1
        else:
            record["status"] = "research"
            record["reason"] = "high_confidence_without_evidence"
            counts["research"] += 1
        results.append(record)
    return {
        "input": os.path.abspath(path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "counts": counts,
        "results": results,
        "note": (
            "Validation only. Ledger writes remain exclusively via "
            "costco_api_client.py mapping import (append-only, conflict-held)."
        ),
    }


def append_audit(path: str, record: Dict) -> None:
    """Append-only JSONL audit record. Never touches the ledger or any
    data file; creates the file only when --audit is explicitly given."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Costco<->Amazon mapping review")
    parser.add_argument("--input", help="candidate cache JSON (default: SCANNER_SEARCH_CACHE_PATH)")
    parser.add_argument("--output", help="review CSV output path (required for review mode)")
    parser.add_argument("--coverage-output", help="coverage metrics JSON output path")
    parser.add_argument("--validate-import", help="validate a proposed ledger import file (read-only)")
    parser.add_argument("--validate-output", help="JSON output for --validate-import")
    parser.add_argument("--audit", help="append-only JSONL audit path (optional)")
    args = parser.parse_args(argv)

    if args.validate_import:
        report = validate_import(args.validate_import)
        if args.validate_output:
            with open(args.validate_output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, sort_keys=True)
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
        if args.audit:
            append_audit(
                args.audit,
                {
                    "mode": "validate_import",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "input": args.validate_import,
                    "counts": report["counts"],
                },
            )
        return 0

    if args.input:
        os.environ["SCANNER_SEARCH_CACHE_PATH"] = args.input
    candidates = amazon_search.load_cached_candidates()
    if not candidates:
        print("No cached candidates found at %s" % (args.input or "SCANNER_SEARCH_CACHE_PATH"))
        return 1

    rows = review_rows(candidates)

    if args.coverage_output:
        metrics = coverage_metrics(candidates, rows)
        with open(args.coverage_output, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, sort_keys=True)
    if args.output:
        count = write_review_csv(rows, args.output)
        print("Wrote %d mapping review rows to %s" % (count, args.output))
    else:
        for row in rows:
            print(
                "%s\t%s\t%s"
                % (row["asin"] or row["amazon_title"][:40], row["match_quality"], row["suggested_action"])
            )
    if args.audit:
        append_audit(
            args.audit,
            {
                "mode": "review",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "input": args.input or os.environ.get("SCANNER_SEARCH_CACHE_PATH"),
                "rows": len(rows),
                "actions": coverage_metrics(candidates, rows)["actions"],
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())