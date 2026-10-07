"""`/api/creative/*` routes for the local exact-text mockup workflow.

Additive and local-only. Registered by ``main.py`` via ``mount_creative(app)``.
No auth changes, no database, no migrations: it composes images on the local
filesystem and (optionally) calls the local ComfyUI lane.

Endpoints
---------
* ``GET  /api/creative/health``          — ComfyUI + model-lane status
* ``GET  /api/creative/presets``         — brand, containers, products, surfaces
* ``POST /api/creative/compose``         — deterministic exact text onto an image
* ``POST /api/creative/generate-scene``  — Qwen/FLUX base scene (local)
* ``POST /api/creative/mockup``          — full pipeline (generate/edit + text)
* ``GET  /api/creative/file/{name}``     — serve a produced PNG
* ``GET  /mogra-mockup``                 — beginner-friendly standalone UI page
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import comfy_client, label_zone, mogra_mockup, presets
from .exact_text import BrandContentError, LabelSpec, brand_fonts, compose_exact_text

_log = logging.getLogger("northstar.creative")

router = APIRouter(prefix="/api/creative", tags=["creative"])

STATIC_DIR = Path(__file__).resolve().parent / "static"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _out_dir() -> Path:
    d = mogra_mockup.default_output_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_output(name: str) -> Path:
    if not _SAFE_NAME.match(name or ""):
        raise HTTPException(status_code=400, detail="invalid file name")
    p = (_out_dir() / name).resolve()
    if p.parent != _out_dir().resolve():
        raise HTTPException(status_code=400, detail="invalid file path")
    return p


def _decode_source(source_base64: Optional[str], source_path: Optional[str]) -> Optional[Image.Image]:
    if source_base64:
        data = source_base64.split(",", 1)[-1]  # tolerate data URLs
        try:
            raw = base64.b64decode(data)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="source_base64 is not valid base64")
        try:
            return Image.open(io.BytesIO(raw)).convert("RGBA")
        except Exception:
            raise HTTPException(status_code=400, detail="source_base64 is not a readable image")
    if source_path:
        p = Path(source_path)
        if not p.exists():
            raise HTTPException(status_code=400, detail=f"source_path not found: {p}")
        return Image.open(p).convert("RGBA")
    return None


def _spec_from_body(body: Dict[str, Any]) -> LabelSpec:
    if body.get("product"):
        return mogra_mockup.build_spec(
            body["product"],
            brand=body.get("brand"), tagline=body.get("tagline"),
            product_name=body.get("product_name"), descriptor=body.get("descriptor"),
            net_weight=body.get("net_weight"),
            ingredients=body.get("ingredients", ""),
            rear_placeholders=body.get("rear_placeholders"),
            extra_lines=body.get("extra_lines"),
        )
    return LabelSpec.from_dict(body)


def _surface_from_body(body: Dict[str, Any]) -> Dict[str, Any]:
    quad = body.get("quad")
    if quad:
        quad = [[float(p[0]), float(p[1])] for p in quad]
    return mogra_mockup.resolve_surface(
        container=body.get("container"), surface_key=body.get("surface"),
        quad=quad, curvature=body.get("curvature"), style_key=body.get("style"))


@router.get("/health")
def health() -> Dict[str, Any]:
    client = comfy_client.ComfyClient()
    models = comfy_client.resolve_models(client)
    return {
        "ok": True,
        "comfyui": {"url": models["comfyui_url"], "up": models["comfy_up"],
                    "gguf_node": models["gguf_node"]},
        "models": {k: models[k] for k in
                   ("clip", "vae", "t2i_unet", "edit_unet", "flux_unet")},
        "on_disk": models["on_disk"],
        "qwen_ready": models["qwen_ready"],
        "qwen_edit_ready": models["qwen_edit_ready"],
        "fonts": brand_fonts(),
        "output_dir": str(_out_dir()),
    }


@router.get("/presets")
def get_presets() -> Dict[str, Any]:
    return presets.catalog()


@router.post("/compose")
def compose(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Deterministic exact text onto an uploaded or on-disk image."""
    spec = _spec_from_body(body)
    surface = _surface_from_body(body)
    enforce = bool(body.get("enforce_brand", True))
    try:
        base = _decode_source(body.get("source_base64"), body.get("source_path"))
    except HTTPException:
        raise
    if base is None:
        raise HTTPException(status_code=400,
                            detail="provide source_base64 or source_path")
    align_info = {"mode": body.get("align", "preset"), "source": "preset"}
    if align_info["mode"] == "auto":
        zone = label_zone.detect_label_zone(base)
        if zone:
            surface["quad_norm"] = zone["quad_norm"]
            align_info.update({"source": "detected", "confidence": zone["confidence"],
                               "zone": zone})
        else:
            align_info["source"] = "preset_fallback"
    try:
        out, params = compose_exact_text(base, spec, surface, surface["style"],
                                         supersample=int(body.get("supersample", 2)),
                                         enforce_brand=enforce,
                                         return_params=True)
    except BrandContentError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    name = body.get("filename") or f"compose_{mogra_mockup._stamp()}.png"
    name = Path(name).name
    if not _SAFE_NAME.match(name):
        name = f"compose_{mogra_mockup._stamp()}.png"
    out_path = _out_dir() / name
    out.convert("RGB").save(out_path, format="PNG")
    return {"ok": True, "output": str(out_path),
            "url": f"/api/creative/file/{out_path.name}", "params": params,
            "align": align_info}


@router.post("/detect-zone")
def detect_zone(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Return the detected blank label zone (normalized quad) for an image."""
    base = _decode_source(body.get("source_base64"), body.get("source_path"))
    if base is None:
        raise HTTPException(status_code=400,
                            detail="provide source_base64 or source_path")
    zone = label_zone.detect_label_zone(base)
    return {"ok": True, "zone": zone, "found": zone is not None}


@router.post("/generate-scene")
def generate_scene(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    prompt = body.get("prompt")
    if not prompt:
        cdict = presets.get_container(body["container"]) if body.get("container") else None
        pdict = presets.get_product(body["product"]) if body.get("product") else None
        prompt = comfy_client.build_scene_prompt(container=cdict, product=pdict,
                                                 extra=body.get("extra", ""))
    out_path = _out_dir() / f"scene_{mogra_mockup._stamp()}.png"
    try:
        res = comfy_client.generate_scene(
            prompt, out_path, width=int(body.get("width", 1024)),
            height=int(body.get("height", 1024)), steps=int(body.get("steps", 20)),
            cfg=float(body.get("cfg", 4.0)), seed=body.get("seed"),
            negative=body.get("negative", ""))
    except comfy_client.ComfyUIError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"ok": True, "lane": res["lane"], "output": str(out_path),
            "url": f"/api/creative/file/{out_path.name}", "prompt": prompt}


@router.post("/mockup")
def mockup(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Full pipeline: base scene (upload/generate/edit) + exact text."""
    if not body.get("product"):
        raise HTTPException(status_code=400, detail="product is required")
    source_image: Optional[str] = None
    tmp_upload: Optional[Path] = None
    if body.get("source_base64"):
        base = _decode_source(body["source_base64"], None)
        tmp_upload = _out_dir() / f"upload_{mogra_mockup._stamp()}.png"
        base.convert("RGB").save(tmp_upload, format="PNG")
        source_image = str(tmp_upload)
    elif body.get("source_path"):
        source_image = body["source_path"]

    try:
        result = mogra_mockup.build_mockup(
            product=body["product"], container=body.get("container"),
            surface_key=body.get("surface"), source_image=source_image,
            generate=bool(body.get("generate", False)),
            scene_prompt=body.get("scene_prompt"),
            quad=body.get("quad"), curvature=body.get("curvature"),
            style_key=body.get("style"),
            width=int(body.get("width", 1024)), height=int(body.get("height", 1024)),
            steps=int(body.get("steps", 20)), seed=body.get("seed"),
            ingredients=body.get("ingredients", ""),
            rear_placeholders=body.get("rear_placeholders"),
            extra_lines=body.get("extra_lines"),
            enforce_brand=bool(body.get("enforce_brand", True)),
            align=body.get("align", "preset"),
            panel_prep=body.get("panel_prep"),
        )
    except BrandContentError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (ValueError, comfy_client.ComfyUIError) as exc:
        raise HTTPException(status_code=503 if isinstance(exc, comfy_client.ComfyUIError) else 400,
                            detail=str(exc))
    result["url"] = f"/api/creative/file/{Path(result['output']).name}"
    return result


@router.get("/file/{name}")
def get_file(name: str) -> FileResponse:
    p = _safe_output(name)
    if not p.exists():
        raise HTTPException(status_code=404, detail="not found")
    media = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    return FileResponse(p, media_type=media)


@router.get("/recent")
def recent(limit: int = 12) -> Dict[str, Any]:
    d = _out_dir()
    files = sorted(d.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"items": [{"name": f.name, "url": f"/api/creative/file/{f.name}",
                       "mtime": f.stat().st_mtime} for f in files[:max(1, min(limit, 100))]]}


# ---------------------------------------------------------------------------
# App integration
# ---------------------------------------------------------------------------

def mount_creative(app: Any) -> None:
    """Register the router, the UI page, and the static assets on ``app``."""
    app.include_router(router)
    # Creative service lanes (additive, local-first): listing-forge / social / ad-pilot
    try:
        from . import service_routes
        for r in (service_routes.listing_router, service_routes.social_router,
                  service_routes.adpilot_router, service_routes.capabilities_router,
                  service_routes.assets_router, service_routes.media_router,
                  service_routes.approvals_router, service_routes.guardian_router,
                  service_routes.competitor_router):
            app.include_router(r)
        _log.info("Creative service lanes mounted "
                  "(/api/listing-forge/*, /api/social/*, /api/ad-pilot/*, /api/creative/capabilities)")
    except Exception as exc:  # keep the mockup lane alive if a lane fails to load
        _log.warning("Creative service lanes unavailable: %s", exc)
    if STATIC_DIR.exists():
        app.mount("/api/creative/static", StaticFiles(directory=str(STATIC_DIR)),
                  name="creative-static")

        @app.get("/mogra-mockup", include_in_schema=False)
        @app.get("/mogra-mockup/", include_in_schema=False)
        def serve_mogra_mockup() -> FileResponse:  # pragma: no cover - thin
            return FileResponse(STATIC_DIR / "mockup.html")
