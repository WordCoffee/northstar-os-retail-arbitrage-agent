"""Subagents — isolated context, a report, and the parent re-verifies.

A subagent never shares the parent's mutable state. Its report carries file hashes;
the parent checks them before believing anything. An edit made by a subagent is
outside the parent's checkpoint (the documented reference has the same limit).
"""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

SubagentRunner = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class SubagentTask:
    task_id: str
    title: str
    prompt: str
    scope: List[str] = field(default_factory=list)
    acceptance: List[str] = field(default_factory=list)
    max_attempts: int = 1

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "title": self.title, "prompt": self.prompt,
                "scope": list(self.scope), "acceptance": list(self.acceptance),
                "max_attempts": self.max_attempts}


@dataclass
class SubagentReport:
    task_id: str
    ok: bool
    summary: str
    files: List[Dict[str, str]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "ok": self.ok, "summary": self.summary,
                "files": list(self.files), "error": self.error}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_subagents(tasks: Sequence[SubagentTask], runner: SubagentRunner, *,
                  max_parallel: int = 2, verify_files: bool = True) -> List[SubagentReport]:
    """Run each task in isolation. Order is stable; a crash is a failed report."""
    def _one(task: SubagentTask) -> SubagentReport:
        # Copy, so a runner cannot mutate the parent's task object.
        payload = dict(task.to_dict())
        try:
            raw = runner(payload) or {}
        except Exception as exc:  # noqa: BLE001 - a crash is a report, not a hang
            return SubagentReport(task.task_id, False, "", error=str(exc)[:300])
        report = SubagentReport(
            task_id=str(raw.get("task_id") or task.task_id),
            ok=bool(raw.get("ok")),
            summary=str(raw.get("summary") or "")[:2000],
            files=list(raw.get("files") or []),
            error=(str(raw.get("error"))[:300] if raw.get("error") else None),
        )
        if report.task_id != task.task_id:
            report.ok = False
            report.error = "report task_id does not match the task"
        if verify_files and report.ok:
            for entry in report.files:
                p = Path(str(entry.get("path") or ""))
                if not p.is_file():
                    report.ok = False
                    report.error = f"reported file missing: {p}"
                    break
                want = str(entry.get("sha256") or "")
                if want and _sha(p) != want:
                    report.ok = False
                    report.error = f"reported hash does not match: {p}"
                    break
        return report

    workers = max(1, min(int(max_parallel), len(tasks) or 1))
    if workers == 1:
        return [_one(t) for t in tasks]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, tasks))


def merge(reports: Sequence[SubagentReport]) -> Dict[str, Any]:
    ok = all(r.ok for r in reports)
    return {
        "ok": ok,
        "reports": [r.to_dict() for r in reports],
        "files": [f for r in reports for f in r.files],
        "errors": [r.error for r in reports if r.error],
        "summary": "; ".join(r.summary for r in reports if r.summary)[:4000],
    }
