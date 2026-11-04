"""Video ad API: plan first, then an explicit, observable render job.

A 15 s video is minutes of local GPU work. Refusing to start it on a typo is the
point of this surface: `POST /video-ad/plan` returns the scene plan and the
sampler clip count without rendering; `POST /video-ad/render` requires
`confirm: true`, runs in a background thread, and is polled through
`GET /video-ad/jobs/{id}`. A failed stage leaves the job `failed` with the
reason; a done job carries its manifest.

The render uses the local Wan lane and a product picture (an existing studio
asset or a data URL). No provider, no network, no cost.
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from design_studio_api import studio_account
from data_layer import get_northstar_db

import shorts
import video_ad
import video_formats
import video_script

router = APIRouter(prefix="/api/design-studio/video-ad",
                   tags=["design-studio-video-ad"])

ASSET_DIR = Path(__file__).resolve().parent / "data" / "studio_generated"
JOBS_DIR = ASSET_DIR / "video_ad_jobs"
MAX_DATA_URL_BYTES = 24 * 1024 * 1024

_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
#: Job ids are generated; the route validates the shape before touching a path.
_JOB_ID = re.compile(r"^vad_[a-f0-9]{12}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _save(job: Dict[str, Any]) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = JOBS_DIR / f"{job['job_id']}.json"
    tmp = path.with_suffix(".json.tmp")
    # A poller may read while a stage update is being written; write-then-replace
    # keeps the job file parseable at every instant.
    tmp.write_text(json.dumps(job, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def recover_interrupted() -> List[str]:
    """Mark jobs left queued/running by a previous process as interrupted.

    A background thread cannot survive a restart, so leaving its file at
    `running` is a lie a poller would wait on forever.
    """
    rows: List[str] = []
    if not JOBS_DIR.is_dir():
        return rows
    for path in JOBS_DIR.glob("*.json"):
        job = _load(path.stem)
        if not job or job.get("status") not in ("queued", "running"):
            continue
        job.update({"status": "interrupted", "stage": "interrupted",
                    "reason": "process restarted before the job finished",
                    "updated_at": _now()})
        _save(job)
        rows.append(str(job.get("job_id") or path.stem))
    return rows


def _update(job_id: str, **fields: Any) -> Dict[str, Any]:
    with _LOCK:
        job = _JOBS.get(job_id) or _load(job_id) or {"job_id": job_id}
        job.update(fields)
        job["updated_at"] = _now()
        _JOBS[job_id] = job
        _save(job)
    return job


def _load(job_id: str) -> Optional[Dict[str, Any]]:
    path = JOBS_DIR / f"{job_id}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a corrupt job file is a miss
        return None


class VideoAdIn(BaseModel):
    brand: str = Field("MOGRA", max_length=60)
    product: str = Field("LION'S MANE", min_length=1, max_length=80)
    subtitle: str = Field("MUSHROOM POWDER", max_length=80)
    weight: str = Field("6 oz (170 g)", max_length=40)
    claims: List[str] = Field(default_factory=lambda: ["100% PURE", "NO FILLERS"])
    platform: str = Field("tiktok", min_length=3, max_length=40)
    seconds: Optional[float] = Field(None, ge=1, le=600)
    plate_asset_id: Optional[str] = Field(None, max_length=80)
    plate_data_url: Optional[str] = Field(None, max_length=40_000_000)
    steps: int = Field(16, ge=4, le=60)
    cfg: float = Field(5.0, ge=1.0, le=12.0)
    seed: int = Field(0, ge=0, le=2**31 - 1)
    voiceover_text: str = Field("", max_length=600)
    vary_framing: bool = True
    confirm: bool = False


def _product(body: VideoAdIn) -> Dict[str, Any]:
    return {"brand": body.brand, "product": body.product, "subtitle": body.subtitle,
            "weight": body.weight, "claims": list(body.claims)}


def _decode_data_url(data_url: str) -> bytes:
    payload = data_url.split(",", 1)[1] if "," in data_url else data_url
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422,
                            detail=f"plate_data_url_invalid: {exc}")
    if len(raw) > MAX_DATA_URL_BYTES:
        raise HTTPException(status_code=413, detail="plate_image_too_large")
    return raw


def _plate_bytes(body: VideoAdIn, acct: str) -> bytes:
    if body.plate_data_url:
        return _decode_data_url(body.plate_data_url)
    if body.plate_asset_id:
        db = get_northstar_db()
        asset = db.design_studio.assets.get_by_id(body.plate_asset_id, account_id=acct)
        if not asset or not asset.get("storage_key"):
            raise HTTPException(status_code=404, detail="Plate asset not found")
        path = ASSET_DIR / Path(str(asset["storage_key"])).name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Plate file not found on disk")
        return path.read_bytes()
    raise HTTPException(status_code=422, detail={
        "code": "plate_required",
        "message": "pass plate_asset_id or plate_data_url for the Wan source image"})


def _plan(body: VideoAdIn) -> Dict[str, Any]:
    try:
        video_formats.plan(body.platform, body.seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422,
                            detail={"code": "video_format_invalid", "message": str(exc)})
    plan = video_script.plan_scenes(_product(body), platform=body.platform,
                                    seconds=body.seconds, seed=body.seed)
    chunks = video_ad.scene_chunks(plan)
    return {
        "ok": True,
        "dry_run": True,
        "plan": plan,
        "scene_chunks": chunks,
        "sampler_clips": sum(len(row["chunks"]) for row in chunks),
        "note": ("This is a plan. POST /render with confirm=true to spend the local "
                 "GPU time; a 15 s TikTok is several minutes of work."),
        "compliance": plan["compliance"],
    }


@router.post("/plan")
def plan_only(body: VideoAdIn, acct: str = Depends(studio_account)):
    return _plan(body)


@router.post("/render", status_code=202)
def start_render(body: VideoAdIn, acct: str = Depends(studio_account)):
    if not body.confirm:
        raise HTTPException(status_code=400, detail={
            "code": "confirm_render_required",
            "message": "set confirm=true; this starts a real local Wan render",
            "plan": _plan(body),
        })
    import studio_generation as sg
    plate = _plate_bytes(body, acct)
    status = sg.engine_status()
    if not status.get("armed") or not status.get("reachable"):
        raise HTTPException(status_code=503, detail={
            "code": "image_lane_unavailable",
            "engine": status,
            "message": "the local media lane is not armed/reachable",
        })
    plan = _plan(body)
    job_id = f"vad_{uuid.uuid4().hex[:12]}"
    job = {
        "job_id": job_id, "status": "queued", "stage": "queued",
        "created_at": _now(), "updated_at": _now(),
        "platform": body.platform, "seconds": plan["plan"]["seconds"],
        "out_dir": str(ASSET_DIR / "video_ad" / job_id),
        "scenes": len(plan["plan"]["scenes"]),
        "sampler_clips": plan["sampler_clips"],
    }
    _update(job_id, **{k: v for k, v in job.items() if k != "job_id"})
    thread = threading.Thread(
        target=_run_job, name=f"video-ad-{job_id}",
        args=(job_id, _product(body), body, plate, job["out_dir"]), daemon=True)
    thread.start()
    return {"ok": True, "job_id": job_id, "status": "queued",
            "status_url": f"/api/design-studio/video-ad/jobs/{job_id}",
            "plan": plan}


def _run_job(job_id: str, product: Dict[str, Any], body: VideoAdIn,
             plate: bytes, out_dir: str) -> None:
    def progress(stage: str, detail: Dict[str, Any]) -> None:
        _update(job_id, status="running", stage=stage, detail=detail)

    _update(job_id, status="running", stage="script")
    try:
        manifest = video_ad.produce(
            product, platform=body.platform, seconds=body.seconds,
            out_dir=out_dir, plate_png=plate, steps=body.steps, cfg=body.cfg,
            seed=body.seed, voiceover_text=body.voiceover_text or None,
            vary_framing=body.vary_framing, on_progress=progress)
    except Exception as exc:  # noqa: BLE001 - the job records the reason
        _update(job_id, status="failed", stage="failed",
                reason=f"{type(exc).__name__}: {exc}"[:800])
        return
    _update(job_id, status="done", stage="done", file=manifest["file"],
            manifest=manifest, reason="")


@router.get("/jobs/{job_id}")
def get_job(job_id: str, acct: str = Depends(studio_account)):
    if not _JOB_ID.fullmatch(str(job_id or "")):
        # A job id is generated, never a path fragment. Refuse a traversal
        # attempt before it reaches _load's Path join.
        raise HTTPException(status_code=404, detail="video-ad job not found")
    job = _JOBS.get(job_id) or _load(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="video-ad job not found")
    return job


@router.get("/jobs")
def list_jobs(acct: str = Depends(studio_account)):
    rows = []
    if JOBS_DIR.is_dir():
        for path in sorted(JOBS_DIR.glob("*.json"))[-20:]:
            data = _load(path.stem)
            if data:
                rows.append({k: data.get(k) for k in
                             ("job_id", "status", "stage", "created_at",
                              "platform", "seconds", "file", "reason")})
    return {"jobs": rows}


# A restart cannot keep a background thread alive; mark its job files honestly.
try:
    _RECOVERED_ON_IMPORT = recover_interrupted()
except Exception:  # noqa: BLE001 - recovery must never prevent the app booting
    _RECOVERED_ON_IMPORT = []


__all__ = ["router", "VideoAdIn", "plan_only", "start_render", "get_job",
           "list_jobs", "_run_job", "JOBS_DIR", "_JOBS", "recover_interrupted"]
