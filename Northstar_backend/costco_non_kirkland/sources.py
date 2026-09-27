"""Local Costco data source discovery.

OFFLINE ONLY. Enumerates Costco product data that ALREADY exists locally in the
repository — database, cache, previously imported files, or approved exports.
Never crawls Costco and never fetches Costco URLs.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# The canonical local Costco data files (verified present in the repo).
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # .../Northstar OS Retail Arbitrage Agent
DEFAULT_DATA_DIR = DEFAULT_PROJECT_ROOT / "data"

COSTCO_DATA_FILES: tuple = (
    "costco-items.csv",
    "costco-discovery-catalog.json",
    "costco-product-detail.json",
    "costco-api-catalog.json",
    "costco-amazon-mapping.json",
)


@dataclass
class SourceDescriptor:
    source_name: str
    path: Optional[str]
    exists: bool
    kind: str  # csv | json-catalog | json-list | json-mapping
    raw_record_count: int = 0
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "path": self.path,
            "exists": self.exists,
            "kind": self.kind,
            "raw_record_count": self.raw_record_count,
            "note": self.note,
        }


def _kind_for(name: str) -> str:
    if name.endswith(".csv"):
        return "csv"
    if name == "costco-discovery-catalog.json":
        return "json-catalog"
    if name == "costco-amazon-mapping.json":
        return "json-mapping"
    return "json-list"


def _count_records(path: Optional[str], kind: str) -> int:
    if not path or not os.path.exists(path):
        return 0
    try:
        if kind == "csv":
            import csv
            with open(path, "r", encoding="utf-8", newline="") as fh:
                return sum(1 for _ in csv.DictReader(fh))
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            for key in ("records", "items", "asins"):
                if isinstance(data.get(key), list):
                    return len(data[key])
            return 0
        return 0
    except Exception:
        return 0


def discover_costco_sources(data_dir: Optional[str] = None,
                            backend_dir: Optional[str] = None) -> List[SourceDescriptor]:
    """Discover every local Costco data source.

    Checks the canonical project `data/` dir first, then a backend-local
    `data/` dir (some caches live at Northstar_backend/data).
    """
    dirs: List[Path] = []
    if data_dir:
        dirs.append(Path(data_dir))
    dirs.append(DEFAULT_DATA_DIR)
    if backend_dir:
        dirs.append(Path(backend_dir) / "data")

    seen: Dict[str, Path] = {}
    for d in dirs:
        for name in COSTCO_DATA_FILES:
            p = d / name
            if p.exists():
                if name not in seen:
                    seen[name] = p
                else:
                    # Prefer the project-root file; keep first occurrence.
                    continue

    sources = []
    for name in COSTCO_DATA_FILES:
        p = seen.get(name)
        kind = _kind_for(name)
        sources.append(SourceDescriptor(
            source_name=name,
            path=str(p) if p else None,
            exists=p is not None,
            kind=kind,
            raw_record_count=_count_records(str(p) if p else None, kind) if p else 0,
        ))
    return sources


def discover_summary(data_dir: Optional[str] = None,
                     backend_dir: Optional[str] = None) -> Dict[str, Any]:
    """Dry-run-friendly summary of discovered Costco sources and counts."""
    sources = discover_costco_sources(data_dir=data_dir, backend_dir=backend_dir)
    existing = [s for s in sources if s.exists]
    total = sum(s.raw_record_count for s in existing)
    return {
        "offline_only": True,
        "sources_checked": len(sources),
        "sources_found": len(existing),
        "total_raw_records": total,
        "sources": [s.to_dict() for s in sources],
    }