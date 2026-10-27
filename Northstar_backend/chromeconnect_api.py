"""Chrome Connect admin room API (P6-T6).

FastAPI router for ChromeConnect room: runner status, job queue,
Needs You queue, adapter health, alerts, evidence viewer.

Provenance: In-house implementation based on NORTHSTAROS_MASTER_BUILD_PLAN.md P6-T6.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

# Ensure chromeconnect_runner is importable
_RUNNER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "chromeconnect_runner")
if _RUNNER_DIR not in sys.path:
    sys.path.insert(0, _RUNNER_DIR)

try:
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False
    APIRouter = None

# In-memory state (production uses DB)
_runner_state: Dict[str, Any] = {
    "running": False,
    "paused": False,
    "jobs_completed": 0,
    "jobs_failed": 0,
    "last_heartbeat": None,
    "current_job": None,
}
_jobs: Dict[str, Dict[str, Any]] = {}
_alerts: List[Dict[str, Any]] = []
_adapter_health: Dict[str, Dict[str, Any]] = {}


def create_router() -> Optional[Any]:
    """Create the ChromeConnect API router (if FastAPI available)."""
    if not _FASTAPI_AVAILABLE:
        return None

    router = APIRouter(prefix="/chromeconnect", tags=["chromeconnect"])

    @router.get("/status")
    async def get_status():
        return {
            "runner": _runner_state,
            "jobs": {
                "total": len(_jobs),
                "queued": sum(1 for j in _jobs.values() if j.get("state") == "QUEUED"),
                "running": sum(1 for j in _jobs.values() if j.get("state") == "RUNNING"),
                "succeeded": sum(1 for j in _jobs.values() if j.get("state") == "SUCCEEDED"),
                "failed": sum(1 for j in _jobs.values() if j.get("state") == "FAILED"),
                "needs_owner": sum(1 for j in _jobs.values() if j.get("state") == "NEEDS_OWNER"),
            },
            "adapters": len(_adapter_health),
            "alerts": len([a for a in _alerts if not a.get("acknowledged")]),
        }

    @router.get("/jobs")
    async def list_jobs(state: Optional[str] = Query(None)):
        jobs = list(_jobs.values())
        if state:
            jobs = [j for j in jobs if j.get("state") == state]
        return {"jobs": jobs, "count": len(jobs)}

    @router.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @router.post("/jobs/{job_id}/resolve")
    async def resolve_job(job_id: str, body: Dict[str, Any]):
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.get("state") != "NEEDS_OWNER":
            raise HTTPException(status_code=400, detail="Job is not in NEEDS_OWNER state")
        job["state"] = "RUNNING"
        job["needs_owner_reason"] = None
        return {"status": "resolved", "job_id": job_id}

    @router.get("/adapters")
    async def list_adapters():
        return {"adapters": list(_adapter_health.values()), "count": len(_adapter_health)}

    @router.get("/adapters/{name}")
    async def get_adapter(name: str):
        adapter = _adapter_health.get(name)
        if not adapter:
            raise HTTPException(status_code=404, detail="Adapter not found")
        return adapter

    @router.get("/alerts")
    async def list_alerts(acknowledged: bool = False):
        alerts = _alerts if acknowledged else [a for a in _alerts if not a.get("acknowledged")]
        return {"alerts": alerts, "count": len(alerts)}

    @router.post("/alerts/acknowledge")
    async def acknowledge_alert(body: Dict[str, Any]):
        index = body.get("index", -1)
        if 0 <= index < len(_alerts):
            _alerts[index]["acknowledged"] = True
            return {"status": "acknowledged", "index": index}
        raise HTTPException(status_code=404, detail="Alert not found")

    @router.get("/evidence/{job_id}")
    async def get_evidence(job_id: str):
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"job_id": job_id, "evidence": job.get("evidence", [])}

    @router.post("/pause")
    async def pause_runner():
        _runner_state["paused"] = True
        return {"status": "paused"}

    @router.post("/resume")
    async def resume_runner():
        _runner_state["paused"] = False
        return {"status": "resumed"}

    return router


# In-memory helpers (for testing without FastAPI)
def register_job(job: Dict[str, Any]) -> str:
    _jobs[job["id"]] = job
    return job["id"]


def register_adapter_health(name: str, health: Dict[str, Any]) -> None:
    _adapter_health[name] = health


def add_alert(alert: Dict[str, Any]) -> None:
    _alerts.append(alert)


def get_status() -> Dict[str, Any]:
    return {
        "runner": _runner_state,
        "jobs": {
            "total": len(_jobs),
            "queued": sum(1 for j in _jobs.values() if j.get("state") == "QUEUED"),
            "running": sum(1 for j in _jobs.values() if j.get("state") == "RUNNING"),
            "succeeded": sum(1 for j in _jobs.values() if j.get("state") == "SUCCEEDED"),
            "failed": sum(1 for j in _jobs.values() if j.get("state") == "FAILED"),
            "needs_owner": sum(1 for j in _jobs.values() if j.get("state") == "NEEDS_OWNER"),
        },
        "adapters": len(_adapter_health),
        "alerts": len([a for a in _alerts if not a.get("acknowledged")]),
    }


def reset_state() -> None:
    """Reset in-memory state (for testing)."""
    global _runner_state, _jobs, _alerts, _adapter_health
    _runner_state = {
        "running": False, "paused": False, "jobs_completed": 0,
        "jobs_failed": 0, "last_heartbeat": None, "current_job": None,
    }
    _jobs = {}
    _alerts = []
    _adapter_health = {}
