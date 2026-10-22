"""Design Studio lanes — cutout, upscale and MAIN compliance as API endpoints.

These are the manual, fast lanes that sit next to `/generate-async`: each one
takes a stored studio asset, runs a LOCAL deterministic or GPU-local step, and
registers the result as a new asset with the full evidence in metadata.

  POST /api/design-studio/lanes/cutout      BiRefNet matting -> framed MAIN PNG
  POST /api/design-studio/lanes/upscale     deterministic LANCZOS upscale
  POST /api/design-studio/lanes/main-check  measure a file against the MAIN rules
  GET  /api/design-studio/lanes/status      which lanes are usable right now

Upscale is deliberately model-free: the installed x4 model aborted the ComfyUI
process on a 1216px input (see 00_STATE known_issues), so the lane that ships is
the one that cannot take the pipeline down.

Gating: the cutout lane needs the local engine armed (MEDIA_GEN_LIVE=1 and
ComfyUI reachable) exactly like every other render; upscale and main-check are
pure PIL and always available.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from data_layer import get_northstar_db
from design_studio_api import studio_account

router = APIRouter(prefix="/api/design-studio/lanes", tags=["design-studio-lanes"])

_OUT_DIR = Path(__file__).resolve().parent / "data" / "studio_generated"


def _load_asset(asset_id: str, acct: str):
    db = get_northstar_db()
    asset = db.design_studio.assets.get_by_id(asset_id, account_id=acct)
    if not asset or not asset.get("storage_key"):
        raise HTTPException(status_code=404, detail="Asset not found")
    path = _OUT_DIR / Path(str(asset["storage_key"])).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found on disk")
    return db, asset, path


def _new_asset(db, *, acct: str, asset: Dict[str, Any], name_suffix: str,
               mime: str, payload: bytes, ext: str, kind: str,
               metadata: Dict[str, Any]) -> Dict[str, Any]:
    fname = f"{kind}_{uuid.uuid4().hex}.{ext}"
    (_OUT_DIR / fname).write_bytes(payload)
    base = asset.get("name") or "asset"
    aid = db.design_studio.assets.create({
        "account_id": acct, "project_id": asset.get("project_id"),
        "name": f"{base} {name_suffix}", "asset_type": kind,
        "mime_type": mime, "storage_key": fname, "size_bytes": len(payload),
        "metadata": metadata,
    })
    return {"asset_id": aid, "name": f"{base} {name_suffix}",
            "file_url": f"/api/design-studio/assets/{aid}/file"}


@router.get("/status")
def lanes_status(acct: str = Depends(studio_account)):
    import image_prep  # noqa: F401 - presence check
    import studio_generation as sg
    try:
        import prepress as pp
        profiles = [p.name for p in pp.available_cmyk_profiles()]
    except Exception:  # noqa: BLE001
        profiles = []
    try:
        import local_voice as lv
        voice = lv.engines()
    except Exception as exc:  # noqa: BLE001 - report the real reason, never fake it
        voice = {"preferred": None, "error": f"{type(exc).__name__}: {exc}"[:200]}
    engine = sg.engine_status()
    return {
        "engine": engine,
        "lanes": {
            "cutout": {"available": bool(engine.get("armed")),
                       "model": sg.CUTOUT_MODEL_FILE, "gpu": True,
                       "note": "BiRefNet matting; needs the local engine."},
            "upscale": {"available": True, "method": "lanczos+unsharp", "gpu": False,
                        "note": ("Deterministic, capped at 4x. Model upscaling is "
                                 "disabled after a server abort - see known_issues.")},
            "main_check": {"available": True, "gpu": False},
            "prepress": {"available": bool(profiles), "profiles": profiles,
                         "gpu": False},
            "narration": {"available": bool(voice.get("preferred")),
                          "engine": voice.get("preferred"),
                          "engines": {k: bool((voice.get(k) or {}).get("available"))
                                      for k in ("piper", "sapi")},
                          "ffmpeg": bool((voice.get("ffmpeg") or {}).get("available")),
                          "gpu": False,
                          "note": ("Local speech + ffmpeg mux: narrated video needs no "
                                   "provider key. Video stays silent when this is off.")},
        },
    }


class CutoutIn(BaseModel):
    asset_id: str = Field(..., min_length=3, max_length=80)
    fill: float = Field(0.88, ge=0.3, le=1.0)
    size: int = Field(2000, ge=256, le=6000)
    persist_framed: bool = True
    #: The policy the framed result is measured against (MAIN defaults).
    min_fill: float = Field(0.85, ge=0.1, le=1.0)
    min_side: int = Field(2000, ge=256, le=10000)


@router.post("/cutout")
def lane_cutout(body: CutoutIn, acct: str = Depends(studio_account)):
    """Cut the product out of a stored render and frame it for a MAIN slot."""
    import image_prep as ip
    import studio_generation as sg

    db, asset, path = _load_asset(body.asset_id, acct)
    try:
        cut = sg.generate_cutout(path.read_bytes())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    out: Dict[str, Any] = {}
    out["cutout"] = _new_asset(
        db, acct=acct, asset=asset, name_suffix="(cutout)", mime="image/png",
        payload=cut["bytes"], ext="png", kind="cutout",
        metadata={"lane": {"name": "cutout", "model": cut["model"],
                           "provider": cut["provider"],
                           "source_asset_id": body.asset_id}})
    framed = ip.frame_on_white_bytes(cut["bytes"], fill=body.fill, size=body.size)
    check = ip.check_main_compliance(framed["bytes"], min_fill=body.min_fill,
                                     min_side=body.min_side)
    out["compliance"] = check
    if body.persist_framed:
        out["framed"] = _new_asset(
            db, acct=acct, asset=asset, name_suffix=f"(MAIN {body.size})",
            mime="image/png", payload=framed["bytes"], ext="png", kind="listing_image",
            metadata={"lane": {"name": "cutout+frame", "fill_target": body.fill,
                               "size": framed["size"], "scale_applied": framed["scale_applied"],
                               "upscaled": framed["upscaled"],
                               "source_asset_id": body.asset_id},
                      "compliance": check})
    return out


class UpscaleIn(BaseModel):
    asset_id: str = Field(..., min_length=3, max_length=80)
    factor: float = Field(2.0, gt=1.0, le=4.0)


@router.post("/upscale")
def lane_upscale(body: UpscaleIn, acct: str = Depends(studio_account)):
    """Deterministic upscale (no GPU). Upscale a CLEAN PLATE before text."""
    import image_prep as ip

    db, asset, path = _load_asset(body.asset_id, acct)
    try:
        res = ip.upscale_lanczos(path.read_bytes(), factor=body.factor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _new_asset(
        db, acct=acct, asset=asset, name_suffix=f"({body.factor:g}x upscale)",
        mime="image/png", payload=res["bytes"], ext="png", kind="render",
        metadata={"lane": {"name": "upscale", "method": res["method"],
                           "factor": res["factor"], "source_size": res["source_size"],
                           "size": res["size"], "gpu": res["gpu"],
                           "source_asset_id": body.asset_id},
                  "note": res["note"]})


class MainCheckIn(BaseModel):
    asset_id: str = Field(..., min_length=3, max_length=80)
    min_fill: float = Field(0.85, ge=0.1, le=1.0)
    min_side: int = Field(2000, ge=256, le=10000)
    require_square: bool = False


class ReadinessIn(BaseModel):
    asset_id: Optional[str] = Field(None, max_length=80)
    main_asset_id: Optional[str] = Field(None, max_length=80)
    expected_terms: Optional[list] = None
    template_id: Optional[str] = Field(None, max_length=60)
    params: Optional[Dict[str, Any]] = None
    profile: Optional[str] = Field(None, max_length=120)
    tac_limit: float = Field(300.0, ge=50.0, le=400.0)
    min_fill: float = Field(0.85, ge=0.1, le=1.0)
    min_side: int = Field(2000, ge=256, le=10000)


@router.post("/readiness")
def lane_readiness(body: ReadinessIn, acct: str = Depends(studio_account)):
    """One verdict for "is this package retail-ready?" across every check we own."""
    import design_studio_print as dp
    import package_readiness as pr

    artwork = main_image = None
    db = get_northstar_db()
    if body.asset_id:
        _db, _asset, path = _load_asset(body.asset_id, acct)
        artwork = path.read_bytes()
    if body.main_asset_id:
        _db2, _asset2, path2 = _load_asset(body.main_asset_id, acct)
        main_image = path2.read_bytes()

    dieline = None
    if body.template_id:
        try:
            dieline = dp.build_from_template(body.template_id, body.params)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    return pr.assess_package(artwork=artwork, main_image=main_image, dieline=dieline,
                             expected_terms=body.expected_terms, profile=body.profile,
                             tac_limit=body.tac_limit, min_fill=body.min_fill,
                             min_side=body.min_side)


@router.post("/main-check")
def lane_main_check(body: MainCheckIn, acct: str = Depends(studio_account)):
    """Measure a stored image against the mechanical Amazon MAIN rules."""
    import image_prep as ip

    _db, asset, path = _load_asset(body.asset_id, acct)
    rep = ip.check_main_compliance(path.read_bytes(), min_fill=body.min_fill,
                                   min_side=body.min_side,
                                   require_square=body.require_square)
    return {"asset_id": body.asset_id, "name": asset.get("name"), **rep}
