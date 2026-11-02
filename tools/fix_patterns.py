"""Append-only fix-pattern store: the trajectory, not just the diff.

One JSONL file per defect class plus an index. Every accepted (or failed) task is
recorded with what the author read, every edit attempt, the self-revision points,
the final shape, the probe transition and the commit or restore outcome.

    python tools/fix_patterns.py --list
    python tools/fix_patterns.py --record state/author_handoffs/trajectory.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "state" / "fix_patterns"


def _path(class_name: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in class_name)
    return STORE / f"{safe}.jsonl"


def record(entry: Dict[str, Any]) -> Path:
    """Append one trajectory. Never rewrites an existing line."""
    required = ("task", "defect_class", "outcome")
    missing = [k for k in required if not entry.get(k)]
    if missing:
        raise ValueError("a pattern record needs: " + ", ".join(required))
    STORE.mkdir(parents=True, exist_ok=True)
    entry = dict(entry)
    entry.setdefault("recorded_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    path = _path(str(entry["defect_class"]))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def entries(class_name: Optional[str] = None) -> List[Dict[str, Any]]:
    if not STORE.is_dir():
        return []
    files = [_path(class_name)] if class_name else sorted(STORE.glob("*.jsonl"))
    out: List[Dict[str, Any]] = []
    for path in files:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def hint(class_name: str, limit: int = 2) -> str:
    """A short, code-free pattern statement derived from accepted fixes."""
    picked = [e for e in entries(class_name) if e.get("outcome") == "accepted"][:limit]
    if not picked:
        return ""
    parts = []
    for e in picked:
        summary = str(e.get("pattern") or "").strip()
        if summary:
            parts.append(summary)
    return " ".join(parts)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--record", default="", help="JSON file with one trajectory")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--class", dest="klass", default="")
    args = ap.parse_args(argv)
    if args.record:
        data = json.loads(Path(args.record).read_text(encoding="utf-8"))
        print(record(data))
        return 0
    rows = entries(args.klass or None)
    print(json.dumps([{k: e.get(k) for k in ("task", "defect_class", "outcome",
                                            "commit", "pattern")} for e in rows],
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
