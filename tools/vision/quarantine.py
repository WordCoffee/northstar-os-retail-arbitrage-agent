"""Quarantine Chrome Connect by retiring it, never by deleting it.

Work order §5.1 layer 5: Chrome Connect is retired **by quarantine, not deletion**, and
only after the parity suite passes twice. This module is the gate, so a future session
cannot retire the incumbent on a single green run or on no evidence at all.

A quarantine writes one flag file. The controller, its config and its tests stay exactly
where they are; `restore()` removes the flag and the old path is available again.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
FLAG = ROOT / "config" / "chromeconnect_quarantine.json"
EVIDENCE = ROOT / "reports" / "ty"
PASSES_REQUIRED = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def evidence(out_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every parity run on disk, oldest first, with its comparison verdict."""
    folder = Path(out_dir or EVIDENCE)
    rows: List[Dict[str, Any]] = []
    for path in sorted(folder.glob("d8_parity_run*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows.append({"path": _relative(path), "run": data.get("run"),
                     "comparison": data.get("comparison") or {},
                     "at": data.get("at")})
    return rows


def _relative(path: Path) -> str:
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def eligible(out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Two independent passes, both comparing Vision >= Chrome Connect."""
    rows = evidence(out_dir)
    passes = [row for row in rows if row["comparison"].get("ok")]
    return {"eligible": len(passes) >= PASSES_REQUIRED and len(rows) >= PASSES_REQUIRED,
            "runs": len(rows), "passes": len(passes), "required": PASSES_REQUIRED,
            "evidence": rows}


def quarantine(*, out_dir: Optional[Path] = None, flag: Optional[Path] = None) -> Dict[str, Any]:
    """Write the quarantine flag, but only on two recorded passes."""
    check = eligible(out_dir)
    if not check["eligible"]:
        return {"ok": False, "reason": "parity_not_passed_twice", **check}
    target = Path(flag or FLAG)
    payload = {"quarantined": True, "at": _now(),
               "reason": "Ty's Vision matched or beat Chrome Connect twice",
               "passes": check["passes"],
               "evidence": [row["path"] for row in check["evidence"]],
               "restore": "python -m tools.vision.quarantine --restore"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, **payload}


def status(*, flag: Optional[Path] = None) -> Dict[str, Any]:
    target = Path(flag or FLAG)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return {"quarantined": bool(data.get("quarantined")), **data}
    except (OSError, ValueError):
        return {"quarantined": False, "reason": "no quarantine flag"}


def restore(*, flag: Optional[Path] = None) -> Dict[str, Any]:
    target = Path(flag or FLAG)
    if not target.exists():
        return {"ok": True, "quarantined": False, "detail": "already active"}
    target.unlink()
    return {"ok": True, "quarantined": False, "detail": "flag removed, controller active"}


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Chrome Connect quarantine gate")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--quarantine", action="store_true")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--out-dir", default="")
    ns = parser.parse_args(argv)

    if ns.restore:
        print(json.dumps(restore(), indent=2))
        return 0
    if ns.quarantine:
        result = quarantine(out_dir=Path(ns.out_dir) if ns.out_dir else None)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    print(json.dumps({"status": status(), "eligibility": eligible(
        Path(ns.out_dir) if ns.out_dir else None)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
