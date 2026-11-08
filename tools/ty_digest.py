"""The daily digest, and the disk floor that gates work before it starts.

Folded fix (WORK ORDER 3 items 5): *no downloads or new worktrees below 5 GB free; report
free space in every digest.* The floor lives here so every caller asks the same question,
and the digest always prints the answer.

    python tools/ty_digest.py --write
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
TY = ROOT / "reports" / "ty"
QUEUE = TY / "director_queue.json"
SCORES = ROOT / "ty" / "scorecards.json"
DB = ROOT / "state" / "director" / "queue.sqlite"

FLOOR_GB = 5.0


def free_gb(path: Optional[Path] = None) -> float:
    try:
        usage = shutil.disk_usage(str(path or ROOT))
        return round(usage.free / (1024 ** 3), 2)
    except OSError:
        return 0.0


def allow_download(*, path: Optional[Path] = None, free: Optional[float] = None) -> Dict[str, Any]:
    """May work that consumes disk start? The floor is 5 GB and it is not negotiable."""
    space = free_gb(path) if free is None else float(free)
    ok = space >= FLOOR_GB
    return {"allow": ok, "free_gb": space, "floor_gb": FLOOR_GB,
            "reason": "" if ok else f"free disk {space} GB is below the {FLOOR_GB} GB floor"}


def allow_worktree(*, path: Optional[Path] = None,
                   free: Optional[float] = None) -> Dict[str, Any]:
    """A worktree is cheap but it is still new disk; the same floor applies."""
    return allow_download(path=path, free=free)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _jobs() -> Dict[str, Any]:
    if not DB.exists():
        return {}
    try:
        conn = sqlite3.connect(str(DB), timeout=5)
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in
                conn.execute("SELECT id, unit, title, status, owner FROM jobs").fetchall()]
        conn.close()
    except sqlite3.Error:
        return {}
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"total": len(rows), "by_status": counts,
            "open": [row for row in rows if row["status"] in
                     ("queued", "claimed", "running", "ready")][:10]}


def _parity() -> Dict[str, Any]:
    flag = ROOT / "config" / "chromeconnect_quarantine.json"
    runs = sorted(TY.glob("d8_parity_run*.json"))
    passes = 0
    for path in runs:
        try:
            if (json.loads(path.read_text(encoding="utf-8")).get("comparison") or {}).get("ok"):
                passes += 1
        except ValueError:
            continue
    return {"runs": len(runs), "passes": passes,
            "quarantined": flag.exists(),
            "six_point": [p.name for p in sorted(TY.glob("d8_sixpoint_run*.json"))]}


def collect(*, path: Optional[Path] = None) -> Dict[str, Any]:
    """Everything the digest needs, as data. Missing files are reported, not invented."""
    queue = _read_json(QUEUE)
    scores = _read_json(SCORES)
    rows = [row for row in scores.get("services") or [] if isinstance(row, dict)]
    below = [row for row in rows if not row.get("meets_bar")]
    below.sort(key=lambda row: -float(row.get("gap") or 0))
    gaps = _read_json(ROOT / "ty" / "seller_gaps.json")
    intel = _read_json(ROOT / "ty" / "intel_gaps.json")
    models = _read_json(ROOT / "ty" / "model_leaderboard.json")
    needs = (TY / "needs_you.md")
    return {
        "date": date.today().isoformat(),
        "disk": allow_download(path=path),
        "units": {name: (row.get("status") if isinstance(row, dict) else row)
                  for name, row in (queue.get("units") or {}).items()},
        "in_flight": queue.get("unit_in_flight", ""),
        "services": {"total": len(rows), "below_bar": len(below), "at_bar": len(rows) - len(below),
                     "top_gaps": [{"id": row.get("id"), "gap": row.get("gap"),
                                   "weakest": row.get("weakest")} for row in below[:5]]},
        "jobs": _jobs(),
        "parity": _parity(),
        "seller_gaps": len(gaps.get("gaps") or []) if isinstance(gaps, dict) else 0,
        "intel_findings": len(intel.get("findings") or []) if isinstance(intel, dict) else 0,
        "model_roles": len((models.get("roles") or {})) if isinstance(models, dict) else 0,
        "needs_you_open": (len([line for line in needs.read_text(encoding="utf-8").splitlines()
                                if line.startswith("## ")])
                           if needs.exists() else 0),
    }


def render(data: Dict[str, Any]) -> str:
    disk = data["disk"]
    lines: List[str] = [
        f"# Ty digest — {data['date']}", "",
        f"**Disk free:** {disk['free_gb']} GB (floor {disk['floor_gb']} GB — "
        f"{'ok' if disk['allow'] else 'BELOW FLOOR, work that consumes disk is refused'})", "",
        f"**Unit in flight:** {data['in_flight'] or '(none)'}", "",
        "| unit | status |", "|---|---|",
    ]
    for name, status in sorted(data["units"].items()):
        lines.append(f"| {name} | {status} |")
    services = data["services"]
    lines += ["", "## Services", "",
              f"{services['total']} scored, {services['below_bar']} below the bar, "
              f"{services['at_bar']} at it.", ""]
    if services["top_gaps"]:
        lines += ["| service | gap | weakest |", "|---|---|---|"]
        for row in services["top_gaps"]:
            lines.append(f"| {row['id']} | {row['gap']} | {row['weakest']} |")
    parity = data["parity"]
    lines += ["", "## Chrome Connect parity", "",
              f"{parity['runs']} suite run(s), {parity['passes']} passing; "
              f"quarantined: {parity['quarantined']}; "
              f"six-point evidence files: {len(parity['six_point'])}", ""]
    lines += ["## Lanes", "",
              f"- Seller-Tester gaps filed: {data['seller_gaps']}",
              f"- Intel findings: {data['intel_findings']}",
              f"- Model roles on the leaderboard: {data['model_roles']}",
              f"- Open `needs_you` sections: {data['needs_you_open']}", ""]
    jobs = data["jobs"]
    if jobs:
        lines += ["## Jobs", "",
                  f"{jobs.get('total', 0)} total: "
                  + ", ".join(f"{key}={value}" for key, value in
                              sorted((jobs.get("by_status") or {}).items())), ""]
    return "\n".join(lines) + "\n"


def write(*, path: Optional[Path] = None, out: Optional[Path] = None) -> Dict[str, Any]:
    data = collect(path=path)
    target = Path(out) if out else TY / f"digest_{data['date']}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(data), encoding="utf-8")
    return {"ok": True, "path": str(target), "disk_free_gb": data["disk"]["free_gb"]}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ty digest and disk floor")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)
    if ns.write:
        print(json.dumps(write(), indent=2))
        return 0
    print(json.dumps(collect(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
