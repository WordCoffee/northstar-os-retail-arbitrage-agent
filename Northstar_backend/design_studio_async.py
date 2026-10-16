"""Design Studio — asynchronous generation lane with credit metering.

Competitive-RE build (2026-10-16): Packify.ai runs generations through a queued,
pausable agent pipeline and meters every feature in credits; DYP.ai deducts
credits per feature (balance/cost/use/history). Northstar's `/generate` is
synchronous and records `credits_used: 0`. This module adds the missing lane
WITHOUT touching the sync endpoint:

- `POST /generate-async` -> creates a `queued` ds job, optionally RESERVES
  credits (real ledger: reserve -> commit on success / release on failure),
  and executes on a bounded worker pool.
- `GET /generate-async/{job_id}` -> job status (+ live balance when enforced).

Credit policy (honest, alpha-safe):
- Default is METER-ONLY (`DESIGN_CREDITS_ENFORCE=0`): the job records the
  planned cost + preview, but nothing is deducted — matching the current alpha
  posture where the credits meter is display-only.
- With `DESIGN_CREDITS_ENFORCE=1` the mechanic is REAL and fail-closed: a
  first-use plan allotment is granted per account (aligned with the
  `/api/v1/credits/me` display contract), then reserve -> commit/release.
  Insufficient balance refuses the job with HTTP 402.

Everything still runs on the operator's local engine (ComfyUI gate unchanged):
no provider is called, no money is spent.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel  # noqa: F401  (kept for type context in docstrings)

from credit_ledger import CreditLedger, InsufficientCredits, allotment_for_plan
from data_layer import get_northstar_db
from design_studio_api import GenerateIn, studio_account

router = APIRouter(prefix="/api/design-studio", tags=["design-studio-async"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _costs() -> Dict[str, int]:
    return {
        "image": int(os.environ.get("DESIGN_CREDIT_COST_IMAGE", "1")),
        "video": int(os.environ.get("DESIGN_CREDIT_COST_VIDEO", "4")),
    }


def credits_enforced() -> bool:
    return os.environ.get("DESIGN_CREDITS_ENFORCE", "0").strip().lower() in ("1", "true", "yes")


_LEDGER: Optional[CreditLedger] = None


def get_ledger() -> CreditLedger:
    """Process-wide ledger persisted as JSONL under Northstar_backend/data."""
    global _LEDGER
    if _LEDGER is None:
        path = Path(__file__).resolve().parent / "data" / "credit_ledger.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        _LEDGER = CreditLedger(path=str(path))
    return _LEDGER


def ensure_initial_grant(ledger: CreditLedger, account_id: str, plan: str = "foundation") -> None:
    """One idempotent plan allotment per account (matches the display meter)."""
    ledger.grant(account_id, allotment_for_plan(plan),
                 reason=f"alpha plan allotment ({plan})",
                 idempotency_key=f"grant:alpha:{account_id}:{plan}")


_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ds-gen")


def _out_dir() -> Path:
    d = Path(__file__).resolve().parent / "data" / "studio_generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _engine_status() -> dict:
    """Indirection so tests can patch the gate without patching studio_generation."""
    import studio_generation as sg
    return sg.engine_status()


def run_generation_job(*, job_id: str, acct: str, body: Dict[str, Any],
                       reservation_id: Optional[str] = None,
                       enforce: bool = False,
                       db=None, ledger: Optional[CreditLedger] = None,
                       out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Execute one queued generation job. Shared by the worker pool and tests."""
    import studio_generation as sg

    db = db or get_northstar_db()
    ledger = ledger if ledger is not None else (get_ledger() if enforce else None)
    out_dir = out_dir or _out_dir()
    kind = body.get("kind", "image")
    try:
        if kind == "video":
            out = sg.generate_video(prompt=body["brief"], width=body.get("width"),
                                    height=body.get("height"), tier=body.get("tier", "draft"),
                                    seed=body.get("seed"))
        else:
            out = sg.generate_image(prompt=body["brief"], width=body.get("width"),
                                    height=body.get("height"), tier=body.get("tier", "draft"),
                                    seed=body.get("seed"))
    except Exception as exc:  # noqa: BLE001 - recorded on the job, surfaced to the caller
        if enforce and reservation_id and ledger is not None:
            try:
                ledger.release(reservation_id, idempotency_key=f"release:{reservation_id}")
            except KeyError:
                pass
        db.design_studio.jobs.update(job_id, {
            "status": "failed", "logs": str(exc)[:2000],
            "credits_used": 0,  # released (or never charged) on failure
            "finished_at": _now(),
        }, account_id=acct)
        return {"status": "failed", "error": str(exc)[:400]}

    fname = f"{uuid.uuid4().hex}.{out['ext']}"
    (out_dir / fname).write_bytes(out["bytes"])
    aid = db.design_studio.assets.create({
        "account_id": acct,
        "project_id": body.get("project_id"),
        "name": f"{body.get('purpose') or kind} - {out['model']} - {_now()[:16]}",
        "asset_type": f"generated-{kind}",
        "mime_type": out["mime"],
        "storage_key": fname,
        "width": out.get("width"), "height": out.get("height"),
        "duration_seconds": out.get("duration_seconds"),
        "size_bytes": len(out["bytes"]),
        "metadata": {
            "generation": {
                "provider": "comfyui", "model": out["model"], "tier": body.get("tier", "draft"),
                "purpose": body.get("purpose"), "prompt": body["brief"],
                "seed": out.get("seed"), "generated_at": _now(), "lane": "async",
            },
            "note": "Rendered locally on the operator's machine via ComfyUI. Nothing was sent to any provider.",
        },
    })
    if enforce and reservation_id and ledger is not None:
        try:
            ledger.commit(reservation_id, idempotency_key=f"commit:{reservation_id}")
        except KeyError:
            pass
    db.design_studio.jobs.update(job_id, {
        "status": "done", "result_ids": [aid], "finished_at": _now(),
    }, account_id=acct)
    return {"status": "done", "asset_id": aid}


def submit_generation(acct: str, *, brief: str, kind: str = "image", tier: str = "draft",
                      purpose: Optional[str] = None, width: Optional[int] = None,
                      height: Optional[int] = None, seed: Optional[int] = None,
                      project_id: Optional[str] = None) -> Dict[str, Any]:
    """Create the queued job (+reservation) and schedule it. Raises HTTPException on gates."""
    if kind not in ("image", "video"):
        raise ValueError("kind must be image or video")
    st = _engine_status()
    if not st.get("armed"):
        raise HTTPException(status_code=409, detail={
            "code": "engine_not_armed",
            "message": ("The local media engine is not armed. Set MEDIA_GEN_LIVE=1 and keep "
                        "ComfyUI reachable at COMFYUI_URL (see the Engine card)."),
            "engine": st,
        })

    enforce = credits_enforced()
    cost = _costs()[kind]
    ledger = get_ledger() if enforce else None
    reservation: Optional[Dict[str, Any]] = None
    if enforce and ledger is not None:
        ensure_initial_grant(ledger, acct)
        try:
            res = ledger.reserve(acct, cost, action=f"design_studio.{kind}",
                                 idempotency_key=f"reserve:{uuid.uuid4().hex}")
        except InsufficientCredits as exc:
            raise HTTPException(status_code=402, detail={
                "code": "insufficient_credits", "message": str(exc), "cost": cost,
            })
        reservation = {"reservation_id": res.reservation_id, "amount": cost}

    db = get_northstar_db()
    job_id = db.design_studio.jobs.create({
        "account_id": acct,
        "project_id": project_id,
        "job_type": f"generate-{kind}",
        "provider": "local:comfyui",
        "status": "queued",
        "cost_preview": {
            "provider": "local",
            "credits": cost,
            "enforced": enforce,
            "note": ("Local compute on the operator's GPU; nothing paid. "
                     f"Credit enforcement {'ON' if enforce else 'OFF (meter-only alpha)'}."),
        },
        "params": {"purpose": purpose, "tier": tier, "brief": brief,
                   "width": width, "height": height, "seed": seed},
        "credits_used": cost if enforce else 0,
    })
    _EXECUTOR.submit(run_generation_job, job_id=job_id, acct=acct,
                     body={"kind": kind, "brief": brief, "tier": tier, "width": width,
                           "height": height, "seed": seed, "project_id": project_id,
                           "purpose": purpose},
                     reservation_id=(reservation or {}).get("reservation_id"),
                     enforce=enforce)
    return {
        "job": db.design_studio.jobs.get_by_id(job_id, account_id=acct),
        "reservation": reservation,
        "enforce": enforce,
        "engine": st,
    }


@router.post("/generate-async", status_code=202)
def generate_async(body: GenerateIn, acct: str = Depends(studio_account)):
    """Queue a local generation. Same gates as /generate; returns immediately."""
    try:
        return submit_generation(acct, brief=body.brief, kind=body.kind, tier=body.tier,
                                 purpose=body.purpose, width=body.width, height=body.height,
                                 seed=body.seed, project_id=body.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/generate-async/{job_id}")
def async_status(job_id: str, acct: str = Depends(studio_account)):
    """Poll a queued/running/done job (credits view included when enforced)."""
    db = get_northstar_db()
    job = db.design_studio.jobs.get_by_id(job_id, account_id=acct)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    payload: Dict[str, Any] = {"job": job, "enforce": credits_enforced()}
    if credits_enforced():
        payload["balance"] = get_ledger().balance(acct)
    return payload
