"""Listing image API: one text-safe render, gated before it becomes a file.

`GET /styles` returns the five text-safe prompts. `POST /` renders one on the
local lane and applies the matching gate (white-background main image vs
secondary style). A failed gate is a 422 with the candidate path and the
measured reasons.
"""
from __future__ import annotations

import base64
import io
import re
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from design_studio_api import studio_account

import listing_render
import social_frames as sf

router = APIRouter(prefix="/api/design-studio/listing-images",
                   tags=["design-studio-listing-images"])

OUT_DIR = Path(__file__).resolve().parent / "data" / "studio_generated"


class ListingImageIn(BaseModel):
    style: str = Field("white-bg", min_length=3, max_length=40)
    brief: str = Field("", max_length=600)
    width: int = Field(1024, ge=512, le=1536)
    height: int = Field(1024, ge=512, le=1536)
    tier: str = Field("final", pattern="^(draft|final)$")


def _name(style: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", style)[:30] or "listing"


@router.get("/styles")
def styles(acct: str = Depends(studio_account)):
    return sf.listing_prompt_pack()


@router.post("")
def create_listing_image(body: ListingImageIn, acct: str = Depends(studio_account)):
    if body.style not in sf.LISTING_STYLES:
        raise HTTPException(status_code=422, detail={
            "code": "listing_style_unknown", "known": sorted(sf.LISTING_STYLES)})
    try:
        result = listing_render.generate(
            body.style, body.brief, width=body.width, height=body.height,
            tier=body.tier)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={
            "code": "image_lane_unavailable", "reason": str(exc)[:400]})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{_name(body.style)}_{uuid.uuid4().hex[:10]}"
    if not result["ok"]:
        rejected = OUT_DIR / f"rejected_{stem}.png"
        rejected.write_bytes(result["bytes"])
        raise HTTPException(status_code=422, detail={
            "code": "listing_image_refused",
            "style": body.style,
            "reason": result["reason"],
            "gate": result["gate"],
            "candidate": str(rejected),
        })

    path = OUT_DIR / f"{stem}.png"
    path.write_bytes(result["bytes"])
    from PIL import Image
    with Image.open(io.BytesIO(result["bytes"])) as img:
        size = list(img.size)
    data_url = ("data:image/png;base64,"
                + base64.b64encode(result["bytes"]).decode("ascii"))
    return {
        "ok": True,
        "style": body.style,
        "main_image": result["main_image"],
        "file": str(path),
        "data_url": data_url,
        "size": size,
        "gate": result["gate"],
        "text_fidelity": result.get("text_fidelity"),
        "prompt": result["prompt"],
    }


__all__ = ["router", "ListingImageIn", "create_listing_image", "styles", "OUT_DIR"]
