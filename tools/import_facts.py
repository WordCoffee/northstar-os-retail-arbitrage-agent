"""Bulk-import knowledge facts into the packs.

Facts live in ``knowledge/facts/*.psv`` (pipe-delimited, one rule per row):

    domain | slug | DO | DON'T | WHY | source | confidence | applies_to

The importer turns each row into a full atom, validates it with the same linter
the improvement loop uses, rejects duplicates/near-duplicates, and appends the
rest to ``knowledge/<domain>/atoms.json``. Nothing is invented: every atom keeps
its source and is marked ``needs_verification`` until checked.

Usage:
  python tools/import_facts.py --dry-run
  python tools/import_facts.py
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import cie_research  # noqa: E402
import knowledge_pack as kp  # noqa: E402

FACTS_DIR = ROOT / "knowledge" / "facts"
TODAY = _dt.date.today().isoformat()


def parse_psv(path: Path) -> List[Tuple[int, Dict[str, Any]]]:
    rows: List[Tuple[int, Dict[str, Any]]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 7)]
        if len(parts) != 8:
            rows.append((lineno, {"_error": f"expected 8 fields, got {len(parts)}"}))
            continue
        domain, slug, do, dont, why, source, confidence, applies = parts
        applies_list = [a.strip() for a in applies.replace("/", ",").split(",") if a.strip()]
        tags = sorted({t for t in slug.replace(".", " ").replace("-", " ").split() if t})
        rows.append((lineno, {
            "id": f"{domain}.{slug}",
            "domain": domain,
            "applies_to": applies_list or ["pl", "reseller"],
            "do": do,
            "dont": dont,
            "why": why,
            "source": source,
            "source_kind": "curated_fact",
            "effective_date": TODAY,
            "last_verified": TODAY,
            "confidence": confidence or "medium",
            "needs_verification": True,
            "tags": tags + [domain],
        }))
    return rows


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Import pipe-delimited facts as atoms")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    files = sorted(FACTS_DIR.glob("*.psv"))
    if not files:
        print(f"no fact files under {FACTS_DIR}")
        return 1

    existing = kp.all_atoms()
    by_domain: Dict[str, List[Dict[str, Any]]] = {}
    added: List[str] = []
    skipped: List[Tuple[str, str]] = []
    rejected: List[Tuple[str, str]] = []

    for path in files:
        for lineno, atom in parse_psv(path):
            label = f"{path.name}:{lineno}"
            if "_error" in atom:
                rejected.append((label, atom["_error"]))
                continue
            problems = kp.validate_atom(atom, known_domains=kp.domains())
            if problems:
                rejected.append((label, "; ".join(problems)))
                continue
            if any(a.get("id") == atom["id"] for a in existing):
                skipped.append((label, f"id already exists: {atom['id']}"))
                continue
            dup = next(((a.get("id"), cie_research.similarity(atom, a))
                        for a in existing
                        if cie_research.similarity(atom, a) >= 0.9), None)
            if dup:
                skipped.append((label, f"near-duplicate of {dup[0]} ({dup[1]})"))
                continue
            by_domain.setdefault(atom["domain"], []).append(atom)
            existing.append(atom)
            added.append(atom["id"])

    for domain, atoms in by_domain.items():
        if args.dry_run:
            continue
        current = kp.load_atoms(domain)
        kp.save_atoms(domain, current + atoms)
        kp.write_pack_meta(domain)

    print(f"  files      : {len(files)}")
    print(f"  added      : {len(added)}" + (" (dry run)" if args.dry_run else ""))
    print(f"  skipped    : {len(skipped)}")
    print(f"  rejected   : {len(rejected)}")
    for label, why in rejected[:10]:
        print(f"    REJECT {label}: {why}")
    for label, why in skipped[:10]:
        print(f"    SKIP   {label}: {why}")
    for domain in sorted(by_domain):
        print(f"    +{len(by_domain[domain]):3d}  {domain}")
    if not args.dry_run:
        stats = kp.stats()
        print(f"  total atoms: {stats['total']} across {len(stats['domains'])} domains")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
