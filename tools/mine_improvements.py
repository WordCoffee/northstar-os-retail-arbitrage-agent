"""Mine the repository for concrete improvement candidates.

High-signal patterns only — every hit is a real line an engineer can act on:
  TODO / FIXME / HACK / XXX comments
  silenced exceptions (except ...: pass)
  NotImplementedError raises
  skipped / xfail tests
  hardcoded loopback URLs in the UI

Output is appended to state/improvement/product_queue.jsonl with
{source: "scan", area: "code-health"} so the same queue holds register items and
scanner findings.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "improvement"

PY_GLOBS = ["Northstar_backend/**/*.py"]
UI_GLOBS = ["northstar-os-ui/src/**/*.js", "northstar-os-ui/src/**/*.jsx"]

SKIP_DIRS = {"__pycache__", "node_modules", "dist", "build", ".git", "venv"}

PATTERNS = [
    ("todo", re.compile(r"\b(TODO|FIXME|HACK|XXX)\b[:\s-]*(.{0,120})"), 0.6),
    ("silenced", re.compile(r"except\s+Exception[^:]*:\s*(?:pass|#)"), 0.7),
    ("not-implemented", re.compile(r"raise\s+NotImplementedError"), 0.8),
    ("skip", re.compile(r"pytest\.mark\.(skip|xfail)|unittest\.skip"), 0.5),
    ("loopback", re.compile(r"127\.0\.0\.1:\d{4}"), 0.4),
]

MAX_PER_KIND = 400


def iter_files() -> List[Path]:
    out: List[Path] = []
    for pattern in PY_GLOBS + UI_GLOBS:
        for path in ROOT.glob(pattern):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            out.append(path)
    return out


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(STATE / "product_queue.jsonl"))
    args = ap.parse_args(argv)

    queue = Path(args.queue)
    existing: List[Dict[str, Any]] = []
    if queue.exists():
        for line in queue.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    existing.append(json.loads(line))
                except ValueError:
                    continue

    seen = {(r.get("title") or "").lower() for r in existing}
    counters = {kind: 0 for kind, _, _ in PATTERNS}
    added: List[Dict[str, Any]] = []

    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for kind, pattern, priority in PATTERNS:
                if counters[kind] >= MAX_PER_KIND:
                    continue
                match = pattern.search(line)
                if not match:
                    continue
                detail = (match.group(2) if match.lastindex and match.lastindex >= 2
                          else "").strip()
                title = f"[{kind}] {rel}:{lineno}"
                if detail:
                    title += f" - {detail[:110]}"
                title = re.sub(r"\s+", " ", title)
                if title.lower() in seen:
                    continue
                seen.add(title.lower())
                counters[kind] += 1
                added.append({
                    "id": f"scan-{kind}-{counters[kind]:04d}",
                    "source": "scan",
                    "source_index": lineno,
                    "area": f"code-health / {kind}",
                    "title": title[:220],
                    "status": "open",
                    "priority": priority,
                    "file": rel,
                    "line": lineno,
                })
                break  # one finding per line keeps the queue readable

    if not added:
        print("  no new findings")
        return 0

    queue.parent.mkdir(parents=True, exist_ok=True)
    with queue.open("a", encoding="utf-8") as fh:
        for row in added:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"  scanned files : {len(iter_files())}")
    print(f"  findings added: {len(added)}")
    for kind in counters:
        print(f"    {counters[kind]:4d}  {kind}")
    print(f"  total queue   : {len(existing) + len(added)} -> {queue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
