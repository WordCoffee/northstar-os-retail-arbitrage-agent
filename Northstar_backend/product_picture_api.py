"""Design Studio — product picture API.

`POST /api/design-studio/product-picture` renders a photoreal package plate on
the local FLUX 3 lane, measures the package face, warps the designed panel onto
it and refuses the result when the OCR gate cannot read the wordmark or the net
weight. The work happens on this machine; nothing is sent to a provider.

`GET /api/design-studio/product-picture/designs` reports the declared designs
and the plate briefs so a caller can see what will be rendered before spending a
minute of GPU time on it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from design_studio_api import studio_account

import mogra_label_art as art
import product_picture as pp

router = APIRouter(prefix="/api/design-studio/product-picture",
                   tags=["design-studio-product-picture"])


class ProductPictureIn(BaseModel):
    #: Declared artwork. A caller may override fields (brand, product, weight,
    #: nutrition rows) with `design`, but it cannot invent a different template.
    product: str = Field("mogra-lions-mane", min_length=3, max_length=60)
    out_dir: Optional[str] = Field(None, max_length=200)
    faces: List[str] = Field(default_factory=lambda: ["front", "back"])
    width: int = Field(1024, ge=512, le=2048)
    height: int = Field(1536, ge=512, le=2048)
    tier: str = Field("final", pattern="^(draft|final)$")
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    design: Optional[Dict[str, Any]] = None


@router.get("/designs")
def designs(acct: str = Depends(studio_account)):
    base = art.MOGRA_LIONS_MANE
    return {
        "designs": [{
            "id": "mogra-lions-mane",
            "brand": base["brand"],
            "product": base["product"],
            "net_weight": base["net_weight"],
            "panel_px": list(art.BASE_SIZE),
            "faces": list(pp.PLATE_BRIEFS),
            "plate_briefs": dict(pp.PLATE_BRIEFS),
        }],
        "gate": ("A picture is written only when mockup_quality.assert_legible reads "
                 "the wordmark and the net weight and the type is sharp."),
        "account": acct,
    }


@router.post("")
def create_product_picture(body: ProductPictureIn, acct: str = Depends(studio_account)):
    try:
        design = art.design_for(body.product)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if body.design:
        design = {**design, **body.design}
    faces = [str(f).strip().lower() for f in body.faces]
    if not faces:
        raise HTTPException(status_code=422, detail="faces must name at least one face")
    unknown = [f for f in faces if f not in pp.PLATE_BRIEFS]
    if unknown:
        raise HTTPException(status_code=422,
                            detail=f"unknown face(s) {unknown}; known: {list(pp.PLATE_BRIEFS)}")

    try:
        result = pp.build(design, out_dir=body.out_dir, faces=faces,
                          width=body.width, height=body.height,
                          tier=body.tier, seed=body.seed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:  # engine refused (disarmed / VRAM busy)
        raise HTTPException(status_code=503, detail={
            "code": "image_lane_unavailable", "reason": str(exc)[:400]})

    if not result.get("ok"):
        failures = [r for r in result.get("faces") or [] if not r.get("ok")]
        lane_down = all(str(r.get("reason", "")).startswith("image_lane_unavailable")
                        for r in failures) and bool(failures)
        if lane_down:
            raise HTTPException(status_code=503, detail={
                "code": "image_lane_unavailable",
                "reasons": [r.get("reason") for r in failures],
                "manifest": result,
            })
        raise HTTPException(status_code=422, detail={
            "code": "product_picture_refused",
            "reasons": [{"face": r.get("face"), "stage": r.get("stage"),
                         "reason": r.get("reason")} for r in failures],
            "manifest": result,
        })
    return result
