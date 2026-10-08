"""Foundation creative contract, backed by the shared creative services.

Context: the `feature/creative-cluster-launch` worktree ships
``foundation/api/creative.py`` with ``GET /readiness`` + ``POST /generate`` that
call ``local_image_gen.generate_image`` directly — i.e. it bypasses the shared
registry, capability router, job queue, provenance, and approved-component policy
that this branch defines.

This module exposes the *same contract* (``/api/v1/foundation/creative/readiness``
and ``/generate``) on top of the shared services, so the Foundation consumer can
delegate with a one-line import change instead of duplicating a local writer. It
is additive: it does not modify the WT-C worktree.

Integration note for the WT-C branch (documented, not auto-applied to avoid
clobbering unrelated changes in that worktree):

    # foundation/api/creative.py
    try:
        from creative.foundation_contract import build_readiness_shared, generate_shared
    except Exception:
        build_readiness_shared = generate_shared = None

    @router.get("/readiness")
    def readiness(...):
        if build_readiness_shared:
            return build_readiness_shared()
        return build_readiness(probe=probe_local_engine)   # legacy fallback

    @router.post("/generate")
    def generate(...):
        if generate_shared:
            return generate_shared(body)
        ... existing local_image_gen path ...
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException

from . import providers, registry, router, stages

router_foundation = APIRouter(prefix="/api/v1/foundation/creative", tags=["creative-foundation"])

_OUT = Path(__file__).resolve().parents[2] / "generated_images" / "creative"


def build_readiness_shared() -> Dict[str, Any]:
    """Provider-neutral readiness derived from the shared registry + router."""
    armed = "MEDIA_GEN_LIVE" in {k for k, v in _env_items() if v == "1"} or providers.media_live_armed()
    std = router.route("generate", "standard")
    local_up = bool(std.get("comfyui_up"))
    if not armed:
        generation, reason = "planned_not_armed", "media_gate_off"
    elif local_up and std.get("ok"):
        generation, reason = "local_available", "ok"
    else:
        generation, reason = "unavailable", "engine_unreachable" if not local_up else "no_approved_lane"
    try:
        manifest = registry.license_manifest()
    except Exception:
        manifest = {}
    return {
        "generation": generation,
        "armed": armed,
        "media_live": armed,
        "backend": "local" if std.get("ok") else "none",
        "local_engine": {"state": "reachable" if local_up else "unreachable", "kind": "comfyui"},
        "reason": reason,
        "routing": {
            "draft": (router.route("generate", "draft").get("primary") or {}).get("lane"),
            "standard": (std.get("primary") or {}).get("lane"),
            "high": (router.route("generate", "high").get("primary") or {}).get("lane"),
        },
        "quarantined": [c["id"] for c in registry.quarantined()],
        "components": [{"id": c["id"], "license": c["license"], "present": c["present"],
                        "commercial_use": c["commercial_use"]}
                       for c in manifest.get("components", [])],
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "notes": "Shared-services readiness only; does not activate generation.",
    }


def _env_items():
    import os
    return os.environ.items()


def generate_shared(body: Dict[str, Any]) -> Dict[str, Any]:
    """Render one image through the shared pipeline; return the Foundation shape."""
    prompt = str(body.get("prompt") or "")
    if not prompt:
        raise HTTPException(status_code=400, detail={"code": "bad_request",
                                                     "message": "prompt is required"})
    mode = str(body.get("mode") or "standard")
    width = int(body.get("width") or 1024)
    height = int(body.get("height") or 1024)
    steps = body.get("steps")
    seed = body.get("seed")
    t0 = time.time()
    _OUT.mkdir(parents=True, exist_ok=True)
    out = _OUT / f"foundation_{int(time.time()*1000)%1000000}.png"
    try:
        res = stages.generate(prompt, out, mode=mode, width=width, height=height,
                              steps=int(steps) if steps is not None else None,
                              cfg=body.get("cfg"), seed=seed,
                              lane=body.get("lane"))
    except stages.StageError as exc:
        raise HTTPException(status_code=503, detail={"code": "engine_unavailable",
                                                     "message": str(exc)}) from exc
    data = out.read_bytes()
    return {
        "ok": True,
        "lane": res.get("lane"),
        "component": res.get("component"),
        "seconds": round(time.time() - t0, 3),
        "width": width, "height": height, "steps": steps, "seed": seed,
        "engine": "shared-creative-services",
        "bytes": len(data), "mime": "image/png",
        "image": "data:image/png;base64," + base64.b64encode(data).decode("ascii"),
        "provenance": res.get("provenance"),
    }


@router_foundation.get("/readiness")
def readiness_endpoint() -> Dict[str, Any]:
    return build_readiness_shared()


@router_foundation.post("/generate")
def generate_endpoint(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    return generate_shared(body)
