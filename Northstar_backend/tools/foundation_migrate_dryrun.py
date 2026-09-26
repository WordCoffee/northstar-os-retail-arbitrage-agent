#!/usr/bin/env python
"""Foundation migration DRY-RUN tool.

Reads the four existing product stores and reports what a canonical migration
WOULD do. It NEVER writes to any source or target and NEVER calls a provider.

Stores read (all read-only):
  1. products table      -> Northstar_backend/data/northstar.db (sqlite, mode=ro)
  2. scanner cache       -> Northstar_backend/data/scanner-search-cache*.json
  3. SourceScout manifest-> Northstar_backend/data/catalog/sourcescout_manifest.json
  4. Golden Goose reports-> Northstar_backend/data/golden-goose-reports/*.json

Usage:
  python -m Northstar_backend.tools.foundation_migrate_dryrun --json
  python -m Northstar_backend.tools.foundation_migrate_dryrun --repo-root . --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

_ASIN_RE = re.compile(r"^[0-9A-Z]{10}$")
_PACK_RE = re.compile(r"(\bpack of\b|\bcase of\b|\b\d+\s*(ct|count|pk)\b|\bmultipack\b|\bbundle\b)", re.I)

DEFAULT_MARKETPLACE = "amazon.com"


def normalize_asin(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    v = str(raw).strip().upper()
    return v or None


def valid_asin(raw: Optional[str]) -> bool:
    v = normalize_asin(raw)
    return bool(v and _ASIN_RE.match(v))


def looks_ambiguous_pack(title: Optional[str]) -> bool:
    return bool(title and _PACK_RE.search(title))


@dataclass
class SourceStats:
    source: str
    records: int = 0
    valid_asin: int = 0
    invalid_asin: int = 0
    missing_asin: int = 0
    missing_provenance: int = 0


@dataclass
class DryRunReport:
    source_stats: list[SourceStats] = field(default_factory=list)
    resolved_identity_count: int = 0
    new_product_candidate_count: int = 0
    duplicate_count: int = 0
    conflict_count: int = 0
    invalid_asin_count: int = 0
    marketplace_unknown_count: int = 0
    pack_ambiguity_count: int = 0
    variation_ambiguity_count: int = 0
    records_missing_provenance: int = 0
    proposed_mapping: dict = field(default_factory=dict)
    reconciliation_totals: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    read_only: bool = True
    writes_performed: int = 0


def _read_products(db_path: str) -> list[dict]:
    if not os.path.exists(db_path):
        return []
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT asin, title, marketplace, fetched_at, provider_id FROM products"
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []
    finally:
        con.close()


def _read_json_list(path: str, list_key: Optional[str] = None) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (ValueError, OSError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if list_key and isinstance(data.get(list_key), list):
            return data[list_key]
        for k in ("items", "products", "records", "rows", "opportunities"):
            if isinstance(data.get(k), list):
                return data[k]
    return []


def run_dry_run(repo_root: str) -> DryRunReport:
    rep = DryRunReport()
    identities: dict[str, set] = {}
    titles_by_identity: dict[str, set] = {}

    def ingest(source: str, records: list[dict], asin_key="asin", title_key="title") -> None:
        stats = SourceStats(source=source)
        for rec in records:
            stats.records += 1
            asin = normalize_asin(rec.get(asin_key) or rec.get("amazon_asin"))
            title = rec.get(title_key) or rec.get("name") or rec.get("product_title")
            mp = rec.get("marketplace") or DEFAULT_MARKETPLACE
            has_prov = any(rec.get(k) for k in ("fetched_at", "generated_at", "cached_at",
                                                "meta", "provider", "provider_id"))
            if not has_prov:
                stats.missing_provenance += 1
                rep.records_missing_provenance += 1
            if not asin:
                stats.missing_asin += 1
                rep.marketplace_unknown_count += 1
            elif not valid_asin(asin):
                stats.invalid_asin += 1
                rep.invalid_asin_count += 1
            else:
                stats.valid_asin += 1
                key = f"{mp}:{asin}"
                identities.setdefault(key, set()).add(source)
                titles_by_identity.setdefault(key, set()).add(str(title or ""))
            if looks_ambiguous_pack(title):
                rep.pack_ambiguity_count += 1
        rep.source_stats.append(stats)

    # 1. products table
    db_path = os.path.join(repo_root, "Northstar_backend", "data", "northstar.db")
    ingest("products_table", _read_products(db_path))

    # 2. scanner caches
    for p in glob.glob(os.path.join(repo_root, "Northstar_backend", "data",
                                    "scanner-search-cache*.json")):
        ingest(os.path.basename(p), _read_json_list(p))

    # 3. sourcescout manifest
    sc = os.path.join(repo_root, "Northstar_backend", "data", "catalog",
                      "sourcescout_manifest.json")
    ingest("sourcescout_manifest", _read_json_list(sc, "items"))

    # 4. golden goose reports
    gg_files = sorted(glob.glob(os.path.join(repo_root, "Northstar_backend", "data",
                                             "golden-goose-reports", "goose_scan_*.json")))
    if gg_files:
        ingest("golden_goose_report", _read_json_list(gg_files[-1], "opportunities"))

    rep.resolved_identity_count = len(identities)
    rep.new_product_candidate_count = len(identities)
    total_records = sum(s.records for s in rep.source_stats)
    rep.duplicate_count = max(0, total_records - len(identities))
    rep.conflict_count = sum(1 for k, t in titles_by_identity.items() if len(t) > 1)
    # variation ambiguity: same brand-family heuristic = titles sharing a base with
    # differing suffixes is out of scope for a deterministic dry run; report 0 with note.
    rep.variation_ambiguity_count = 0
    rep.notes.append("variation ambiguity requires brand-family inference; deferred (0 by heuristic)")

    rep.proposed_mapping = {
        "catalog_product": len(identities),
        "product_identifier(asin)": sum(s.valid_asin for s in rep.source_stats),
        "amazon_offer_snapshot": sum(s.valid_asin for s in rep.source_stats),
        "supplier_documentation": 0,  # no invoice data in sources
    }
    rep.reconciliation_totals = {
        "total_source_records": total_records,
        "distinct_amazon_identities": len(identities),
        "records_beyond_first_occurrence": rep.duplicate_count,
    }
    return rep


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Foundation migration dry-run (read-only).")
    ap.add_argument("--repo-root", default=".", help="repository root")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)

    report = run_dry_run(args.repo_root)
    payload = asdict(report)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"DRY RUN (read_only={report.read_only}, writes={report.writes_performed})")
        for s in report.source_stats:
            print(f"  {s.source}: records={s.records} valid_asin={s.valid_asin} "
                  f"invalid={s.invalid_asin} missing_asin={s.missing_asin} "
                  f"missing_provenance={s.missing_provenance}")
        print(f"  resolved_identities={report.resolved_identity_count} "
              f"new_candidates={report.new_product_candidate_count} "
              f"duplicates={report.duplicate_count} conflicts={report.conflict_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())