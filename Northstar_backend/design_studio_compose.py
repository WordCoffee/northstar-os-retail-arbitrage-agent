"""Design Studio — mockup compositor service (typography pass over clean plates).

RE build 2026-10-16: closes the loop "clean plate -> shelf-ready mockup".
Real logo + real fonts (Playfair Display / Inter) + drawn certification icons
are composited deterministically onto the plate's pouch faces; text is never
generated. Geometry (per-face quads, erase circles, glyph box) comes from a
per-template preset (``data/compose_presets.json``) or the request body - a new
plate needs its quads, which we currently take from a grid-overlay pass.

Session endpoints under /api/design-studio/compose/*.
"""

from __future__ import annotations

import base64
import io
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from data_layer import get_northstar_db
from design_studio_api import studio_account

import mockup_compositor as mc

router = APIRouter(prefix="/api/design-studio/compose", tags=["design-studio-compose"])

_OUT_DIR = Path(__file__).resolve().parent / "data" / "studio_generated"
_LOGO_TMP = Path(__file__).resolve().parent / "data" / "compose_tmp"


def _safe_name(name: Optional[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip())[:80]
    if not base:
        base = "composed"
    if not base.lower().endswith(".png"):
        base += ".png"
    return base


class ComposeIn(BaseModel):
    template_id: str = Field(..., min_length=3, max_length=60)
    plate_asset_id: str = Field(..., min_length=3, max_length=80)
    out_name: Optional[str] = Field(None, max_length=120)
    skus: Optional[List[Dict[str, Any]]] = None
    quads: Optional[List[List[List[float]]]] = None
    erases: Optional[List[Dict[str, Any]]] = None
    glyph_box: Optional[List[int]] = None
    shading: float = Field(0.5, ge=0.0, le=1.0)
    realism: Optional[Dict[str, Any]] = None
    logo_data_url: Optional[str] = Field(None, max_length=3_000_000)


@router.get("/templates")
def compose_templates(acct: str = Depends(studio_account)):
    presets = mc.load_presets()
    out = []
    for tid, tpl in mc.DEFAULT_TEMPLATES.items():
        p = presets.get(tid) or {}
        out.append({
            "id": tid, "description": tpl["description"],
            "panel": tpl["panel"],
            "installed_presets": ([{"plate_file": p.get("plate_file"),
                                    "faces": len(p.get("quads") or [])}] if p else []),
        })
    return {"templates": out,
            "notes": ["Presets carry per-plate geometry (quads/erase/glyph box).",
                      "A new plate needs its own quad pass before it can be composed."]}


@router.get("/presets")
def compose_presets(acct: str = Depends(studio_account)):
    presets = mc.load_presets()
    return {"presets": [
        {"template_id": tid, "plate_file": p.get("plate_file"),
         "faces": len(p.get("quads") or [])}
        for tid, p in presets.items()]}


@router.post("/mockup")
def compose_mockup_endpoint(body: ComposeIn, acct: str = Depends(studio_account)):
    if body.template_id not in mc.DEFAULT_TEMPLATES:
        raise HTTPException(status_code=422, detail=f"unknown template_id {body.template_id!r}")

    db = get_northstar_db()
    plate_asset = db.design_studio.assets.get_by_id(body.plate_asset_id, account_id=acct)
    if not plate_asset or not plate_asset.get("storage_key"):
        raise HTTPException(status_code=404, detail="Plate asset not found")
    plate_path = _OUT_DIR / Path(str(plate_asset["storage_key"])).name
    if not plate_path.is_file():
        raise HTTPException(status_code=404, detail="Plate file not found on disk")

    preset = mc.get_preset(body.template_id) or {}
    logo_path: Optional[Path] = None
    tmp_logo: Optional[Path] = None
    if body.logo_data_url:
        try:
            payload = body.logo_data_url.split(",", 1)[1] if "," in body.logo_data_url else body.logo_data_url
            raw = base64.b64decode(payload)
            _LOGO_TMP.mkdir(parents=True, exist_ok=True)
            tmp_logo = _LOGO_TMP / f"logo_{uuid.uuid4().hex[:10]}.png"
            tmp_logo.write_bytes(raw)
            logo_path = tmp_logo
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"logo_data_url could not be decoded: {exc}")
    else:
        lp = preset.get("logo_path")
        if lp and Path(lp).is_file():
            logo_path = Path(lp)
    if logo_path is None:
        raise HTTPException(status_code=422, detail=(
            "No logo available: pass logo_data_url (base64 PNG) or set a preset logo_path."))

    out_path = _OUT_DIR / _safe_name(body.out_name or f"composed_{body.template_id}_{uuid.uuid4().hex[:8]}")
    try:
        result = mc.compose_mockup(
            template_id=body.template_id, plate_path=plate_path, logo_path=logo_path,
            out_path=out_path, skus=body.skus, quads=body.quads, erases=body.erases,
            glyph_box=body.glyph_box, shading=body.shading, realism=body.realism,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        if tmp_logo is not None:
            try:
                tmp_logo.unlink()
            except OSError:
                pass

    aid = db.design_studio.assets.create({
        "account_id": acct,
        "project_id": plate_asset.get("project_id"),
        "name": f"{body.template_id} — composed ({len(result['skus'])} SKUs)",
        "asset_type": "composite",
        "mime_type": "image/png",
        "storage_key": out_path.name,
        "width": result["size"][0], "height": result["size"][1],
        "size_bytes": out_path.stat().st_size,
        "metadata": {
            "compositor": {"template_id": body.template_id,
                           "plate_asset_id": body.plate_asset_id,
                           "faces": result["quads"], "erases": result["erases"],
                           "skus": result["skus"], "shading": body.shading,
                           "realism": result.get("realism"),
                           "face_metrics": result.get("face_metrics")},
            "note": result["note"],
        },
    })
    return {"asset_id": aid, "file_url": f"/api/design-studio/assets/{aid}/file",
            "template_id": body.template_id, "size": result["size"],
            "note": result["note"]}
