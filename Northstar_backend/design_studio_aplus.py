"""Design Studio — A+ asset service.

`aplus_layout` owns the geometry and `aplus_render` owns the pixels. This module
is the product surface over them: it takes a saved plate, the copy for each
module, and returns rendered, measured, upload-ready A+ assets registered in the
studio's asset store.

Everything is deterministic and local: no provider call, no spend, no browser.
A module that fails QA is still returned, but its `qa.ok` is false and the page
verdict is false — the operator sees the defect instead of a silent pass.

Endpoints under /api/design-studio/aplus/*.
"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import aplus_layout as geo
import aplus_render as ar
from data_layer import get_northstar_db
from design_studio_api import studio_account

router = APIRouter(prefix="/api/design-studio/aplus", tags=["design-studio-aplus"])

_OUT_DIR = Path(__file__).resolve().parent / "data" / "studio_generated"
_LOGO_TMP = Path(__file__).resolve().parent / "data" / "compose_tmp"

DEFAULT_MODULES = ("header", "three_tiles", "comparison")


class ModuleIn(BaseModel):
    # `copy` is a BaseModel method name, so the field is aliased: the JSON key
    # stays "copy" while the attribute is copy_text.
    model_config = ConfigDict(populate_by_name=True)

    kind: str = Field(..., min_length=3, max_length=40)
    copy_text: Optional[Dict[str, Any]] = Field(None, alias="copy")
    copy_side: Optional[str] = Field(None, pattern="^(left|right)$")


class AplusRenderIn(BaseModel):
    plate_asset_id: str = Field(..., min_length=3, max_length=80)
    modules: Optional[List[ModuleIn]] = None
    brand: Optional[Dict[str, Any]] = None
    tile_asset_ids: Optional[List[str]] = None
    logo_data_url: Optional[str] = Field(None, max_length=3_000_000)
    copy_style: str = Field("panel", pattern="^(panel|overlay)$")
    project_id: Optional[str] = None


@router.get("/kinds")
def aplus_kinds():
    """Every module the renderer can produce, at its exact canvas size."""
    return {
        "kinds": [
            {"kind": kind, "width": size[0], "height": size[1],
             "tiles": len(geo.layout(kind)["tiles"]),
             "has_copy_band": geo.layout(kind)["copy"] is not None}
            for kind, size in sorted(geo.CANVAS.items())
        ],
        "defaults": list(DEFAULT_MODULES),
        "safe_inset": geo.SAFE_INSET,
        "max_bytes": ar.MAX_BYTES,
        "copy_styles": list(ar.COPY_STYLES),
        "notes": [
            "Copy is composited, never generated: the model paints the plate only.",
            "panel (default) gives the type its own column; overlay is held to a "
            "stricter contrast and a backdrop-variance ceiling.",
            "Prices, promotions, shipping claims, competitor references and medical "
            "claims are refused before rendering.",
        ],
    }


def _plate_path(db: Any, asset_id: str, acct: str) -> Path:
    asset = db.design_studio.assets.get_by_id(asset_id, account_id=acct)
    if not asset or not asset.get("storage_key"):
        raise HTTPException(status_code=404, detail=f"asset not found: {asset_id}")
    path = _OUT_DIR / Path(str(asset["storage_key"])).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"asset file missing on disk: {asset_id}")
    return path


@router.post("/render")
def aplus_render_route(body: AplusRenderIn, acct: str = Depends(studio_account)):
    """Render, measure and register one A+ page from a saved plate."""
    db = get_northstar_db()
    plate = _plate_path(db, body.plate_asset_id, acct)
    plate_asset = db.design_studio.assets.get_by_id(body.plate_asset_id, account_id=acct)

    modules = body.modules or [ModuleIn(kind=k) for k in DEFAULT_MODULES]
    tiles: List[Path] = [plate]
    if body.tile_asset_ids:
        tiles = [_plate_path(db, tid, acct) for tid in body.tile_asset_ids]

    tmp_logo: Optional[Path] = None
    logo: Optional[Path] = None
    if body.logo_data_url:
        try:
            payload = (body.logo_data_url.split(",", 1)[1]
                       if "," in body.logo_data_url else body.logo_data_url)
            _LOGO_TMP.mkdir(parents=True, exist_ok=True)
            tmp_logo = _LOGO_TMP / f"aplus_logo_{uuid.uuid4().hex[:10]}.png"
            tmp_logo.write_bytes(base64.b64decode(payload))
            logo = tmp_logo
        except Exception as exc:  # noqa: BLE001 - a bad logo is a 422, never a 500
            raise HTTPException(status_code=422,
                                detail=f"logo_data_url could not be decoded: {exc}")

    out_dir = _OUT_DIR / f"aplus_{uuid.uuid4().hex[:8]}"
    try:
        page = ar.render_page(
            [{"kind": m.kind, "copy": m.copy_text or {},
              **({"copy_side": m.copy_side} if m.copy_side else {})} for m in modules],
            brand=body.brand, image=plate, tiles=tiles, logo=logo,
            out_dir=out_dir, copy_style=body.copy_style)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        if tmp_logo is not None:
            try:
                tmp_logo.unlink()
            except OSError:
                pass

    registered: List[Dict[str, Any]] = []
    for entry in page["modules"]:
        # The asset store resolves a storage_key as a FLAT name under _OUT_DIR
        # (see _plate_path), so the per-job subfolder is flattened here rather
        # than leaving a key that would 404 on download.
        src = Path(entry["path"])
        dest = _OUT_DIR / f"{out_dir.name}_{src.name}"
        src.replace(dest)
        entry["path"] = str(dest)
        path = dest
        ext = path.suffix.lower()
        asset = db.design_studio.assets.create({
            "account_id": acct,
            "project_id": body.project_id or plate_asset.get("project_id"),
            "name": f"A+ {entry['kind']} — {path.stem}",
            "asset_type": "aplus_module",
            "mime_type": "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png",
            "storage_key": path.name,
            "width": entry["size"][0], "height": entry["size"][1],
            "size_bytes": entry["bytes"],
            "metadata": {
                "aplus": {
                    "kind": entry["kind"], "index": entry["index"],
                    "copy_mode": entry["copy_mode"], "qa": entry["qa"],
                    "plate_asset_id": body.plate_asset_id,
                    "copy_style": body.copy_style,
                },
                "note": ("copy composited deterministically; qa measured, not assumed"),
            },
        })
        registered.append({"kind": entry["kind"], "asset_id": asset,
                           "file_url": f"/api/design-studio/assets/{asset}/file",
                           "size": entry["size"], "bytes": entry["bytes"],
                           "copy_mode": entry["copy_mode"], "qa": entry["qa"]})

    preview_id = None
    if page.get("preview"):
        p = Path(page["preview"])
        p = p.replace(_OUT_DIR / f"{out_dir.name}_{p.name}")
        preview_id = db.design_studio.assets.create({
            "account_id": acct,
            "project_id": body.project_id or plate_asset.get("project_id"),
            "name": f"A+ page preview — {out_dir.name}",
            "asset_type": "aplus_preview",
            "mime_type": "image/png",
            "storage_key": p.name,
            "width": 0, "height": 0,
            "size_bytes": p.stat().st_size,
            "metadata": {"aplus": {"plate_asset_id": body.plate_asset_id,
                                   "page_ok": page["ok"]}},
        })

    return {
        "ok": page["ok"],
        "problems": page["problems"],
        "modules": registered,
        "preview_asset_id": preview_id,
        "preview_url": (f"/api/design-studio/assets/{preview_id}/file"
                        if preview_id else None),
        "bytes_total": page["bytes_total"],
        "plate_asset_id": body.plate_asset_id,
    }


__all__ = ["router", "AplusRenderIn", "ModuleIn"]
