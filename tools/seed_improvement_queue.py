"""Seed the product improvement queue from the written registers.

The knowledge loop consumes *knowledge* gaps; this queue is the other half —
concrete product/code improvements that a build session works through. It is a
real backlog, parsed from the two registers, not generated padding.

Sources:
  reports/improvement_register_500_*.md
  reports/bojo_100_improvements_*.md

Output: state/improvement/product_queue.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "improvement"

SOURCES = [
    ("reg500", ROOT / "reports" / "improvement_register_500_20261019.md", 500),
    ("bojo100", ROOT / "reports" / "bojo_100_improvements_20261021.md", 100),
]

# Domains that move the product most first.
WEIGHT = {
    "chat": 1.0, "runtime": 1.0, "agent": 1.0, "listing": 1.0, "ads": 1.0,
    "ui": 0.9, "model": 0.9, "creative": 0.8, "research": 0.8,
    "production": 0.9, "observability": 0.7, "ops": 0.7, "docs": 0.5,
    "test": 0.6, "data": 0.6, "architecture": 0.7, "security": 0.9,
}

_NUM = re.compile(r"^\s*(\d+)\.\s+(.*)$")
_HEADING = re.compile(r"^#{2,3}\s+(.*)$")
_MD = re.compile(r"[*_`]")


def clean(text: str) -> str:
    text = _MD.sub("", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("→", "->").replace("—", "-")


def parse(path: Path, tag: str, expect: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    area = "general"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        heading = _HEADING.match(line)
        if heading:
            area = clean(heading.group(1)).lower()
            continue
        match = _NUM.match(line)
        if not match:
            continue
        text = clean(match.group(2))
        if len(text) < 12:
            continue
        rows.append({
            "id": f"{tag}-{len(rows) + 1:04d}",
            "source": path.name,
            "source_index": int(match.group(1)),
            "area": area,
            "title": text[:180],
            "status": "open",
            "priority": round(max([w for k, w in WEIGHT.items() if k in area] or [0.5]), 2),
        })
    if expect and len(rows) < expect:
        print(f"  WARNING: {path.name} parsed {len(rows)} items, register claims {expect}")
    return rows


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(STATE / "product_queue.jsonl"))
    args = ap.parse_args(argv)

    all_rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for tag, path, expect in SOURCES:
        if not path.exists():
            print(f"  missing source: {path}")
            continue
        rows = parse(path, tag, expect)
        fresh = []
        for row in rows:
            key = row["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            fresh.append(row)
        all_rows.extend(fresh)
        print(f"  {tag:8s} {len(rows):4d} parsed, {len(fresh):4d} new")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows) + "\n",
                   encoding="utf-8")
    by_area: Dict[str, int] = {}
    for row in all_rows:
        by_area[row["area"]] = by_area.get(row["area"], 0) + 1
    print(f"  queued   {len(all_rows)} improvements -> {out}")
    for area, count in sorted(by_area.items(), key=lambda kv: -kv[1])[:12]:
        print(f"    {count:4d}  {area[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
