"""Chrome Connect run logger (Phase 0 baseline).

Records a one-line JSON record per Chrome Connect run to
``logs/chromeconnect_runs.jsonl`` (local only, never sent anywhere).

Fields logged (per Phase 0 spec):
    task, site, path (adapter|ai|unknown), steps, time_s, pass_fail, failure_reason

Never logged: credentials, cookies, session tokens, full page content,
or any data from signed-in pages.

Usage:
    from chromeconnect_run_log import log_run
    log_run(task="costco scan kitchen", site="costco.com", path="adapter",
            steps=12, time_s=4.2, pass_fail=True, failure_reason=None)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LOG_PATH = _REPO_ROOT / "logs" / "chromeconnect_runs.jsonl"


def _ensure_log_dir() -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def log_run(
    task: str,
    site: str,
    path: str,  # "adapter" | "ai" | "unknown"
    steps: int,
    time_s: float,
    pass_fail: bool,
    failure_reason: Optional[str] = None,
    run_id: Optional[str] = None,
    needs_login: bool = False,
    source: str = "synthetic",  # "synthetic" | "operator"
) -> dict:
    """Append one run record to the local JSONL log. Returns the record."""
    _ensure_log_dir()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": str(task)[:200],
        "site": str(site)[:100],
        "path": str(path)[:20],
        "steps": int(steps),
        "time_s": round(float(time_s), 3),
        "pass_fail": bool(pass_fail),
        "failure_reason": (str(failure_reason)[:300] if failure_reason else None),
        "needs_login": bool(needs_login),
        "source": str(source)[:20],
    }
    if run_id:
        record["run_id"] = str(run_id)[:100]

    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def read_runs(n: int = 50) -> list[dict]:
    """Read the most recent N run records."""
    if not _LOG_PATH.exists():
        return []
    lines = _LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def baseline_summary() -> dict:
    """Compute baseline metrics from logged runs (Phase 0)."""
    runs = read_runs(10000)
    if not runs:
        return {"total_runs": 0, "pass_rate": None, "avg_steps": None,
                "avg_time_s": None, "paths": {}, "failure_reasons": {},
                "by_source": {}, "needs_login_count": 0}
    total = len(runs)
    passed = sum(1 for r in runs if r.get("pass_fail"))
    paths: dict[str, int] = {}
    reasons: dict[str, int] = {}
    by_source: dict[str, dict] = {}
    needs_login_count = 0
    for r in runs:
        p = r.get("path", "unknown")
        paths[p] = paths.get(p, 0) + 1
        fr = r.get("failure_reason")
        if fr:
            reasons[fr] = reasons.get(fr, 0) + 1
        src = r.get("source", "unknown")
        if src not in by_source:
            by_source[src] = {"total": 0, "passed": 0, "failed": 0}
        by_source[src]["total"] += 1
        if r.get("pass_fail"):
            by_source[src]["passed"] += 1
        else:
            by_source[src]["failed"] += 1
        if r.get("needs_login"):
            needs_login_count += 1
    return {
        "total_runs": total,
        "pass_rate": round(passed / total, 4) if total else None,
        "avg_steps": round(sum(r.get("steps", 0) for r in runs) / total, 2),
        "avg_time_s": round(sum(r.get("time_s", 0) for r in runs) / total, 3),
        "paths": paths,
        "failure_reasons": reasons,
        "by_source": by_source,
        "needs_login_count": needs_login_count,
        "first_run": runs[0].get("ts"),
        "last_run": runs[-1].get("ts"),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        print(json.dumps(baseline_summary(), indent=2))
    else:
        # Self-test
        rec = log_run(task="phase0 self-test", site="localhost", path="unknown",
                      steps=0, time_s=0.0, pass_fail=True, failure_reason=None)
        print("logged:", rec)
        print("summary:", json.dumps(baseline_summary(), indent=2))
