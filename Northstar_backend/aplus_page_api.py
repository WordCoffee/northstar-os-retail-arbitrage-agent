"""A+ page API: product copy + a plate in, a measured module set out.

`POST /api/design-studio/aplus-page` builds the six-beat page, renders every
module and returns each PNG as a data URL with its QA. A module that fails its
own QA is a 422 with the problems; the endpoint never returns a page it did not
measure.

The plate is the product photograph; type is drawn, never diffused. No database
row is written and nothing leaves the machine.
"""
from __future__ import annotations

import base64
import binascii
import io
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from design_studio_api import studio_account

import aplus_brief as ab
import aplus_layout as geo
import aplus_render as ar

router = APIRouter(prefix="/api/design-studio/aplus-page",
                   tags=["design-studio-aplus-page"])

MAX_DATA_URL_BYTES = 24 * 1024 * 1024


class APlusPageIn(BaseModel):
    brand: str = Field("MOGRA", max_length=60)
    product: str = Field("LION'S MANE", min_length=1, max_length=80)
    subtitle: str = Field("MUSHROOM POWDER", max_length=80)
    weight: str = Field("6 oz (170 g)", max_length=40)
    claims: List[str] = Field(default_factory=lambda: ["100% PURE", "NO FILLERS"])
    plate_data_url: str = Field(..., min_length=64, max_length=40_000_000)
    copy_style: str = Field("panel", pattern="^(panel|overlay)$")


def _decode(data_url: str):
    from PIL import Image

    payload = data_url.split(",", 1)[1] if "," in data_url else data_url
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"plate_data_url_invalid: {exc}")
    if len(raw) > MAX_DATA_URL_BYTES:
        raise HTTPException(status_code=413, detail="plate_image_too_large")
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422,
                            detail=f"plate_image_not_decodable: {exc}")


def _product(body: APlusPageIn) -> dict:
    return {"brand": body.brand, "product": body.product,
            "subtitle": body.subtitle, "weight": body.weight,
            "claims": list(body.claims)}


@router.get("/modules")
def modules(acct: str = Depends(studio_account)):
    return {"modules": [{"kind": k, "size": list(geo.CANVAS[k])}
                        for k in ab.PAGE_MODULES],
            "note": "The page order. Each module is rendered and QA'd before it is returned."}


@router.post("")
def create_page(body: APlusPageIn, acct: str = Depends(studio_account)):
    plate = _decode(body.plate_data_url)
    try:
        result = ab.build_page(_product(body), image=plate,
                               copy_style=body.copy_style)
    except ar.AplusNotPerfect as exc:
        raise HTTPException(status_code=422, detail={
            "code": "aplus_page_refused",
            "problems": getattr(exc, "problems", None) or [str(exc)],
            "detail": getattr(exc, "detail", None),
        })
    modules_out = []
    for module in result["modules"]:
        modules_out.append({
            "kind": module["kind"],
            "size": module["size"],
            "qa": module["qa"],
            "sha256": module["sha256"],
            "bytes": module["bytes"],
            "copy_mode": module["copy_mode"],
            "data_url": ("data:image/png;base64,"
                         + base64.b64encode(module["png"]).decode("ascii")),
        })
    return {
        "ok": True,
        "modules": modules_out,
        "page": {"ok": result["page"].get("ok"),
                 "problems": result["page"].get("problems") or [],
                 "bytes_total": result["page"].get("bytes_total")},
        "note": ("Each module passed its own QA. The plate is the product photograph; "
                 "type is drawn, not generated."),
    }


__all__ = ["router", "APlusPageIn", "create_page", "modules"]
