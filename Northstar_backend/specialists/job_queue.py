"""GPU job queue + run ledger (blueprint §11 and §7).

One heavy job at a time by default, interactive work ahead of batch work, an
explicit VRAM guard before a job starts, and a ledger line for every run so cost
and provenance are answerable after the fact.

Pure Python, no network, no thread pool of its own: the caller runs the job and
the queue decides *when*. That keeps it testable without a GPU.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

#: interactive work wins over batch work at the same arrival time.
PRIORITY = {"interactive": 0, "batch": 1}


@dataclass(order=True)
class Job:
    priority: int
    seq: int
    job_id: str = field(compare=False)
    kind: str = field(compare=False, default="image")
    payload: Dict[str, Any] = field(compare=False, default_factory=dict)
    created_at: float = field(compare=False, default_factory=time.time)


class JobQueue:
    """Single-slot heavy queue with a VRAM guard and a run ledger."""

    def __init__(self, *, ledger_path: Optional[Path] = None,
                 vram_guard: Optional[Callable[[], bool]] = None):
        self._jobs: List[Job] = []
        self._seq = 0
        self._running: Optional[Job] = None
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self.vram_guard = vram_guard
        self.history: List[Dict[str, Any]] = []

    # ── queue ───────────────────────────────────────────────────────────────
    def submit(self, kind: str, payload: Optional[Dict[str, Any]] = None,
               *, priority: str = "interactive") -> Dict[str, Any]:
        if priority not in PRIORITY:
            raise ValueError(f"priority must be one of {sorted(PRIORITY)}")
        self._seq += 1
        job = Job(priority=PRIORITY[priority], seq=self._seq,
                  job_id=f"job_{uuid.uuid4().hex[:10]}", kind=kind,
                  payload=dict(payload or {}))
        self._jobs.append(job)
        self._jobs.sort()
        return {"job_id": job.job_id, "kind": kind, "priority": priority,
                "queued": len(self._jobs), "position": self._position(job)}

    def _position(self, job: Job) -> int:
        ordered = sorted(self._jobs)
        return ordered.index(job) + (1 if self._running else 0)

    def status(self) -> Dict[str, Any]:
        return {
            "running": ({"job_id": self._running.job_id, "kind": self._running.kind}
                        if self._running else None),
            "queued": [{"job_id": j.job_id, "kind": j.kind} for j in sorted(self._jobs)],
            "slots": 1,
        }

    # ── execution ───────────────────────────────────────────────────────────
    def acquire(self) -> Dict[str, Any]:
        """Take the next job if a slot is free and VRAM allows. Never guesses."""
        if self._running is not None:
            return {"ok": False, "reason": "busy", "running": self._running.job_id}
        if not self._jobs:
            return {"ok": False, "reason": "empty"}
        job = sorted(self._jobs)[0]
        if self.vram_guard is not None and not self.vram_guard():
            return {"ok": False, "reason": "vram_guard",
                    "detail": "not enough free VRAM for a heavy job; nothing started"}
        self._jobs.remove(job)
        self._running = job
        return {"ok": True, "job": {"job_id": job.job_id, "kind": job.kind,
                                    "payload": job.payload,
                                    "waited_s": round(time.time() - job.created_at, 3)}}

    def complete(self, job_id: str, *, ok: bool, detail: str = "",
                 credits: float = 0.0, cost_usd: float = 0.0,
                 outputs: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self._running or self._running.job_id != job_id:
            return {"ok": False, "reason": "not_running", "job_id": job_id}
        job = self._running
        self._running = None
        record = {
            "job_id": job.job_id, "kind": job.kind, "ok": bool(ok),
            "detail": str(detail)[:300], "credits": float(credits),
            "cost_usd": float(cost_usd), "outputs": list(outputs or []),
            "queued_at": job.created_at, "finished_at": time.time(),
            "duration_s": round(time.time() - job.created_at, 3),
        }
        self.history.append(record)
        self._append(record)
        return {"ok": True, "record": record}

    def _append(self, record: Dict[str, Any]) -> None:
        if not self.ledger_path:
            return
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    # ── reporting ───────────────────────────────────────────────────────────
    def totals(self) -> Dict[str, Any]:
        return {
            "jobs": len(self.history),
            "failed": sum(1 for r in self.history if not r["ok"]),
            "credits": round(sum(r["credits"] for r in self.history), 3),
            "cost_usd": round(sum(r["cost_usd"] for r in self.history), 4),
        }


#: Process-wide queue the chat tools report against.
_default: Optional[JobQueue] = None


def get_queue() -> JobQueue:
    global _default
    if _default is None:
        root = Path(__file__).resolve().parent.parent
        _default = JobQueue(ledger_path=root / "data" / "job_ledger.jsonl")
    return _default
