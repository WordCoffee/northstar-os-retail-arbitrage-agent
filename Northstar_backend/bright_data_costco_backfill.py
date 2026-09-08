"""Backfill resolved Costco item numbers from lookup evidence into the
master price capture CSV.

The gated lookup (`bright_data_costco_lookup.py resolve`) persists one
normalized evidence record per query under
`data/costco-lookup-runs/<run_ts>/normalized/lookup_<key>_<ts>.json`, each
with ``query`` (the Exact Amazon title that was searched), an
``identity_match_status`` and a ranked ``best_candidate``.

This tool folds the STRONG matches back into a NEW copy of the master capture
CSV — it never mutates the original. Only records whose search page clearly
identified the product (``lookup_candidate``, best score >= 0.50) auto-fill
the ``Costco candidate item number`` column. Weak matches, no-results and
page-not-found rows are REPORTED but never fabricated into the CSV, so a
rebuilt full-pull manifest can only ever contain ids with real evidence.

Rules:
  - Rows that already carry a different item number are never overwritten
    (conflict is reported instead).
  - Duplicate queries across evidence keep the highest-score record.
  - Output defaults to ``<csv>`` with ``_backfilled`` suffix; refusing to
    overwrite the input path.

Never makes network calls; reads only local evidence and the local CSV.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from typing import Dict, List, Optional

LOOKUP_CANDIDATE = "lookup_candidate"
MIN_ACCEPT_SCORE = 0.50

DEFAULT_LOOKUP_ROOT = "data/costco-lookup-runs"

ITEM_NUMBER_COL = "Costco candidate item number"
AMAZON_TITLE_COL = "Exact Amazon title"
MATCH_SOURCE_COL = "Match source"
MATCH_CONFIDENCE_COL = "Match confidence"
NOTES_COL = "Notes / mismatch detail"


def _load_normalized_records(lookup_dirs: List[str]) -> List[Dict]:
    """Load every normalized lookup record from the given directories."""
    records: List[Dict] = []
    for d in lookup_dirs:
        pattern = os.path.join(d, "normalized", "lookup_*.json")
        for path in sorted(glob.glob(pattern)):
            try:
                with open(path, "r", encoding="utf-8-sig") as fh:
                    rec = json.load(fh)
            except (OSError, ValueError) as exc:
                print(f"[backfill] SKIP unreadable evidence {path}: {exc}")
                continue
            if isinstance(rec, dict) and rec.get("query"):
                records.append(rec)
    return records


def build_resolved_map(records: List[Dict]) -> Dict[str, Dict]:
    """query (normalized, stripped) -> {item_id, score, source, conflicts}.

    Only ``lookup_candidate`` records with best score >= MIN_ACCEPT_SCORE are
    accepted. Duplicate queries keep the highest-score record; a disagreement
    in item id between two records for the same query is counted as a
    conflict (highest score still wins).
    """
    resolved: Dict[str, Dict] = {}
    for rec in records:
        query = str(rec.get("query", "")).strip()
        if not query:
            continue
        best = rec.get("best_candidate") or {}
        item_id = str(best.get("item_id", "")).strip()
        score = float(best.get("score") or 0.0)
        status = rec.get("identity_match_status") or ""

        if status == LOOKUP_CANDIDATE and item_id and score >= MIN_ACCEPT_SCORE:
            prev = resolved.get(query)
            if prev is None or score > prev["score"]:
                if prev is not None and prev["item_id"] != item_id:
                    resolved[query] = {
                        "item_id": item_id,
                        "score": score,
                        "source": rec.get("provider") or "BRIGHTDATA_WEB_UNLOCKER",
                        "evidence": rec.get("run_id") or "",
                        "conflicts": prev["conflicts"] + 1,
                    }
                else:
                    resolved[query] = {
                        "item_id": item_id,
                        "score": score,
                        "source": rec.get("provider") or "BRIGHTDATA_WEB_UNLOCKER",
                        "evidence": rec.get("run_id") or "",
                        "conflicts": (prev.get("conflicts", 0) if prev else 0),
                    }
            elif prev is not None and prev["item_id"] != item_id:
                prev["conflicts"] = prev.get("conflicts", 0) + 1
    return resolved


def _summarize_skipped(records: List[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for rec in records:
        status = rec.get("identity_match_status") or ""
        counts[status] = counts.get(status, 0) + 1
    return counts


def backfill_csv(
    csv_path: str,
    out_path: str,
    lookup_dirs: List[str],
    dry_run: bool = False,
) -> Dict:
    """Fill resolved item numbers into a new CSV copy and return a report."""
    out_path = os.path.abspath(out_path)
    if os.path.abspath(csv_path) == out_path:
        raise ValueError(
            "refusing to overwrite the input CSV in place; pass a distinct --out"
        )

    records = _load_normalized_records(lookup_dirs)
    resolved = build_resolved_map(records)
    skipped = _summarize_skipped(records)

    report = {
        "evidence_records": len(records),
        "queries_resolved": len(resolved),
        "rows_total": 0,
        "rows_filled": 0,
        "rows_already_matched": 0,
        "conflicts": 0,
        "dry_run": dry_run,
        "out_path": out_path,
        "resolved_rows": [],
        "weak_and_unresolved_titles": [],
        "status_counts": skipped,
    }

    if records:
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        report["rows_total"] = len(rows)

        for row in rows:
            title = str(row.get(AMAZON_TITLE_COL) or "").strip()
            hit = resolved.get(title)
            existing = str(row.get(ITEM_NUMBER_COL) or "").strip()
            # any title that was actually looked up but did not clear the gate
            looked_up = {r.get("query", "").strip() for r in records if r.get("query")}

            if hit:
                if existing:
                    if existing != hit["item_id"]:
                        report["conflicts"] += 1
                else:
                    row[ITEM_NUMBER_COL] = hit["item_id"]
                    row[MATCH_SOURCE_COL] = hit["source"]
                    row[MATCH_CONFIDENCE_COL] = f"jaccard {hit['score']:.2f}"
                    prev_notes = str(row.get(NOTES_COL) or "").strip()
                    note = (
                        f"item id from {hit['source']} search lookup"
                        + (f" run {hit['evidence']}" if hit.get("evidence") else "")
                    )
                    row[NOTES_COL] = f"{prev_notes}; {note}".strip("; ") if prev_notes else note
                    report["rows_filled"] += 1
                    report["resolved_rows"].append(
                        {
                            "asin": row.get("ASIN", ""),
                            "amazon_title": title,
                            "item_id": hit["item_id"],
                            "score": hit["score"],
                            "source": hit["source"],
                        }
                    )
            elif title and title in looked_up:
                report["weak_and_unresolved_titles"].append(
                    {"amazon_title": title,
                     "reason": "lookup did not clear acceptance gate"}
                )

        if not dry_run:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

    return report


def _expand_lookup_dirs(args) -> List[str]:
    dirs = list(args.lookup_dir or [])
    if args.lookup_root or (not dirs):
        root = args.lookup_root or DEFAULT_LOOKUP_ROOT
        if os.path.isdir(root):
            runs = sorted(
                (os.path.join(root, d) for d in os.listdir(root)),
                reverse=True,
            )
            dirs.extend(d for d in runs if os.path.isdir(d))
    seen = set()
    unique = []
    for d in dirs:
        d = os.path.normpath(d)
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def _cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="bright_data_costco_backfill.py",
        description="Fold lookup evidence item ids back into a NEW master CSV "
        "copy (offline, never overwrites the input).",
    )
    parser.add_argument("--csv", required=True, help="master price capture CSV path")
    parser.add_argument(
        "--out",
        default=None,
        help="output CSV path (default: <csv>_backfilled.csv)",
    )
    parser.add_argument(
        "--lookup-dir",
        action="append",
        default=None,
        help="lookup run dir containing normalized/ evidence (repeatable)",
    )
    parser.add_argument(
        "--lookup-root",
        default=DEFAULT_LOOKUP_ROOT,
        help="root scanning for lookup-runs subdirs (default: data/costco-lookup-runs)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print plan, write nothing")
    parser.add_argument(
        "--report-json",
        default=None,
        help="optional path to write the machine-readable backfill report",
    )
    args = parser.parse_args(argv)

    lookup_dirs = _expand_lookup_dirs(args)
    if not lookup_dirs:
        print("[backfill] no lookup evidence directories found — nothing to fold back.")
        return 1

    out_path = args.out or f"{os.path.splitext(args.csv)[0]}_backfilled.csv"
    report = backfill_csv(args.csv, out_path, lookup_dirs, dry_run=args.dry_run)

    if report["evidence_records"] == 0:
        print("[backfill] no normalized lookup records found; nothing was filled.")
        return 1

    print("=== BACKFILL SUMMARY ===")
    for key in ("evidence_records", "queries_resolved", "rows_total", "rows_filled",
                "rows_already_matched", "conflicts"):
        print(f"{key:<22}: {report[key]}")
    print(f"status_counts       : {report['status_counts']}")
    for row in report["resolved_rows"]:
        print(
            f"  filled {row['item_id']:<10} score={row['score']:.2f} "
            f"{row['amazon_title'][:56]}"
        )
    if report["weak_and_unresolved_titles"]:
        print("still unresolved (did not clear acceptance gate):")
        for row in report["weak_and_unresolved_titles"]:
            print(f"  - {row['amazon_title'][:80]}")
    if args.dry_run:
        print(f"[dry-run] would write: {out_path}")
    else:
        print(f"wrote: {out_path}")
    if args.report_json and not args.dry_run:
        with open(args.report_json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"report json: {args.report_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())