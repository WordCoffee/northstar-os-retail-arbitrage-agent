"""Social frame API: a product picture in, a placement-safe frame out.

`POST /api/design-studio/social-frames/render` decodes a product picture, draws
the declared copy inside the placement's safe area, OCRs the result and returns
the measured boxes. A frame that fails its own check is saved under
`data/studio_generated/rejected_*` and returned as a 422 with the reason - it is
never presented as a deliverable.

No database row is written: the image is returned as a data URL and saved on
disk, so this endpoint has no account-scoped storage to get wrong. The caller
can persist the file wherever its own asset flow expects.
"""
from __future__ import annotations

import base64
import binascii
import io
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from design_studio_api import studio_account

import ad_formats
import social_frames as sf

router = APIRouter(prefix="/api/design-studio/social-frames",
                   tags=["design-studio-social-frames"])

OUT_DIR = Path(__file__).resolve().parent / "data" / "studio_generated"
MAX_DATA_URL_BYTES = 12 * 1024 * 1024


class SocialFrameIn(BaseModel):
    product_data_url: str = Field(..., min_length=64, max_length=16_000_000)
    placement: str = Field(..., min_length=3, max_length=40)
    headline: str = Field(..., min_length=1, max_length=120)
    subline: str = Field("", max_length=120)
    cta: str = Field("", max_length=40)
    palette: str = Field("forest", max_length=20)


def _decode_image(data_url: str):
    from PIL import Image

    payload = data_url.split(",", 1)[1] if "," in data_url else data_url
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422,
                            detail=f"product_data_url_invalid: {exc}")
    if len(raw) > MAX_DATA_URL_BYTES:
        raise HTTPException(status_code=413, detail="product_image_too_large")
    try:
        return Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422,
                            detail=f"product_image_not_decodable: {exc}")


def _safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text)[:40] or "frame"


@router.get("/placements")
def placements(acct: str = Depends(studio_account)):
    return ad_formats.placements()


@router.post("/render")
def render_frame(body: SocialFrameIn, acct: str = Depends(studio_account)):
    if body.placement not in ad_formats.PLACEMENTS:
        raise HTTPException(status_code=422, detail={
            "code": "placement_unknown", "known": sorted(ad_formats.PLACEMENTS)})
    product = _decode_image(body.product_data_url)
    try:
        frame = sf.render_social_frame(
            product, placement=body.placement, headline=body.headline,
            subline=body.subline, cta=body.cta, palette=body.palette)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    checked = sf.check_frame(frame, expected_headline=body.headline,
                             expected_cta=body.cta)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{_safe_name(body.placement)}_{uuid.uuid4().hex[:10]}"
    if not checked["ok"]:
        rejected = OUT_DIR / f"rejected_{stem}.png"
        frame["image"].save(rejected)
        raise HTTPException(status_code=422, detail={
            "code": "frame_refused",
            "reason": checked["reason"],
            "checks": checked["checks"],
            "boxes": frame["boxes"],
            "contrast": frame["contrast"],
            "candidate": str(rejected),
        })

    path = OUT_DIR / f"{stem}.png"
    frame["image"].save(path)
    buf = io.BytesIO()
    frame["image"].save(buf, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    return {
        "ok": True,
        "file": str(path),
        "data_url": data_url,
        "placement": body.placement,
        "canvas": frame["canvas"],
        "boxes": frame["boxes"],
        "contrast": frame["contrast"],
        "checks": checked["checks"],
        "words": checked.get("words"),
        "compliance": frame["compliance"],
    }


__all__ = ["router", "SocialFrameIn", "render_frame", "placements", "OUT_DIR"]
