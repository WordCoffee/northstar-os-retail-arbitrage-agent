"""Shared creative job queue + single heavy worker.

One process-wide queue with a single heavy-job worker by default (the mission's
resource policy: heavy concurrency == 1). Jobs are persisted as JSON so the
history survives a restart. Each job exposes stage progress, a cancellable flag,
resource warnings, and its provenance sidecar path.

Long-running diffusion is executed in a worker thread; the queue itself is
thread-safe. Cancellation sets a flag the running stage polls between steps.
"""

from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import provenance as prov

JOBS_DIR = Path(__file__).resolve().parents[2] / "generated_images" / "creative_jobs"


def _ensure_dir() -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    return JOBS_DIR


class JobCancelled(RuntimeError):
    pass


class CreativeJobStore:
    def __init__(self, max_concurrency: int = 1):
        self._lock = threading.RLock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._queue: deque = deque()
        self._cancel: Dict[str, bool] = {}
        self._heavy = threading.Semaphore(max(1, int(max_concurrency)))
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        _ensure_dir()
        self._load_existing()

    # -- persistence -------------------------------------------------------
    def _persist(self, job: Dict[str, Any]) -> None:
        try:
            (_ensure_dir() / f"{job['id']}.json").write_text(
                json.dumps(job, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_existing(self) -> None:
        for p in sorted(_ensure_dir().glob("*.json")):
            try:
                job = json.loads(p.read_text(encoding="utf-8"))
                if job.get("status") in ("queued", "running"):
                    job["status"] = "error"
                    job["error"] = "interrupted by restart"
                    job["progress"] = {"stage": "failed"}
                self._jobs[job["id"]] = job
            except Exception:
                continue

    # -- public ------------------------------------------------------------
    def create(self, *, task: str, payload: Dict[str, Any],
               plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        jid = uuid.uuid4().hex[:12]
        job = {
            "id": jid,
            "task": task,
            "status": "queued",           # queued | running | done | error | cancelled
            "created_at": time.time(),
            "updated_at": time.time(),
            "progress": {"stage": "queued", "step": 0, "total": None,
                         "eta_seconds": None, "message": "queued"},
            "plan": plan or {},
            "payload": payload,
            "output": None,
            "provenance": None,
            "images": [],
            "error": None,
            "resource_warnings": [],
        }
        with self._lock:
            self._jobs[jid] = job
            self._persist(job)
        return job

    def get(self, jid: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._jobs.get(jid)

    def list(self, limit: int = 60) -> list:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j["created_at"],
                          reverse=True)[:limit]

    def update(self, jid: str, **patch) -> None:
        with self._lock:
            job = self._jobs.get(jid)
            if not job:
                return
            job.update(patch)
            job["updated_at"] = time.time()
            self._persist(job)

    def progress(self, jid: str, *, stage: str, step: int = 0,
                 total: Optional[int] = None, eta: Optional[float] = None,
                 message: str = "") -> None:
        with self._lock:
            job = self._jobs.get(jid)
            if not job:
                return
            job["progress"] = {"stage": stage, "step": step, "total": total,
                               "eta_seconds": eta, "message": message}
            job["updated_at"] = time.time()
            self._persist(job)

    def cancel(self, jid: str) -> bool:
        with self._lock:
            if jid not in self._jobs:
                return False
            self._cancel[jid] = True
            job = self._jobs[jid]
            if job["status"] == "queued":
                job["status"] = "cancelled"
                job["progress"] = {"stage": "cancelled"}
                self._persist(job)
            return True

    def is_cancelled(self, jid: str) -> bool:
        with self._lock:
            return bool(self._cancel.get(jid))

    def submit(self, *, task: str, payload: Dict[str, Any],
               runner: Callable[[str, Dict[str, Any], "CreativeJobStore"], Dict[str, Any]],
               plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        job = self.create(task=task, payload=payload, plan=plan)
        self._queue.append((job["id"], runner))
        self._start_worker()
        return job

    # -- worker ------------------------------------------------------------
    def _start_worker(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._stop.clear()
            self._worker = threading.Thread(target=self._run, daemon=True,
                                            name="creative-worker")
            self._worker.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                jid, runner = self._queue.popleft()
            except IndexError:
                return
            with self._lock:
                job = self._jobs.get(jid)
                if not job or job["status"] == "cancelled":
                    continue
                job["status"] = "running"
                job["progress"] = {"stage": "starting", "step": 0, "message": "starting"}
                self._persist(job)
            # Heavy work holds the semaphore for the whole job (concurrency == 1).
            with self._heavy:
                if self.is_cancelled(jid):
                    self.update(jid, status="cancelled", progress={"stage": "cancelled"})
                    continue
                try:
                    runner(jid, job.get("payload", {}), self)
                except JobCancelled:
                    self.update(jid, status="cancelled", progress={"stage": "cancelled"})
                except Exception as exc:  # never leak a raw 500; record it
                    self.update(jid, status="error", error=str(exc),
                                progress={"stage": "failed", "message": str(exc)})
                    try:
                        (_ensure_dir() / f"{jid}.error.txt").write_text(
                            traceback.format_exc(), encoding="utf-8")
                    except Exception:
                        pass


store = CreativeJobStore()


def run_from_runner(jid: str, payload: Dict[str, Any], st: CreativeJobStore) -> Dict[str, Any]:
    """Default runner hook — overridden by the pipeline module at import time."""
    raise RuntimeError("no creative runner registered")


def status() -> Dict[str, Any]:
    with store._lock:
        jobs = list(store._jobs.values())
    return {
        "queued": sum(1 for j in jobs if j["status"] == "queued"),
        "running": sum(1 for j in jobs if j["status"] == "running"),
        "done": sum(1 for j in jobs if j["status"] == "done"),
        "error": sum(1 for j in jobs if j["status"] == "error"),
        "cancelled": sum(1 for j in jobs if j["status"] == "cancelled"),
        "heavy_concurrency": 1,
        "jobs_dir": str(JOBS_DIR),
    }
