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

import brand_art as art
import mogra_label_art as mg
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
    #: A generated asset id used as the reference product photo (FLUX 3 mi2i).
    #: The plate then carries the real pouch; the vector panel still replaces
    #: the label area, so typography is drawn, never diffused.
    reference_asset_id: Optional[str] = Field(None, max_length=80)
    #: Per-face references, e.g. {"front": "<asset id>", "back": "<asset id>"}.
    #: When both are given this wins over reference_asset_id.
    references: Optional[Dict[str, str]] = None


def _reference_bytes(asset_id: str, acct: str) -> bytes:
    from pathlib import Path

    from data_layer import get_northstar_db

    asset = get_northstar_db().design_studio.assets.get_by_id(
        str(asset_id), account_id=acct)
    if not asset or not asset.get("storage_key"):
        raise HTTPException(status_code=422, detail={
            "code": "reference_asset_not_found", "asset_id": str(asset_id)})
    name = Path(str(asset["storage_key"])).name  # basename only - no traversal
    path = Path(__file__).resolve().parent / "data" / "studio_generated" / name
    if not path.is_file():
        raise HTTPException(status_code=422, detail={
            "code": "reference_asset_missing_file", "asset_id": str(asset_id)})
    return path.read_bytes()


@router.get("/designs")
def designs(acct: str = Depends(studio_account)):
    """Every design the app can actually print, with the form and its briefs."""
    entries = []
    for design_id in art.known():
        design = art.design_for(design_id)
        form = art.form_of(design)
        w_mm, h_mm = art.face_mm(design, "front")
        briefs = pp.FORM_PLATE_BRIEFS[form]
        entries.append({
            "id": design_id,
            "brand": design["brand"],
            "product": design["product"],
            "form": form,
            "format": art.FORM_NAMES[form],
            "face_mm": [round(w_mm, 2), round(h_mm, 2)],
            "net_weight": design["net_weight"],
            "panel_px": ([mg.BASE_SIZE[0], mg.BASE_SIZE[1]] if form == art.POUCH
                         else [int(round(w_mm * 300 / 25.4)),
                               int(round(h_mm * 300 / 25.4))]),
            "faces": list(briefs),
            "plate_briefs": dict(briefs),
            "status": design.get("status"),
        })
    return {
        "designs": entries,
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
    form = art.form_of(design)
    briefs = pp.FORM_PLATE_BRIEFS.get(form) or pp.PLATE_BRIEFS
    faces = [str(f).strip().lower() for f in body.faces]
    if not faces:
        raise HTTPException(status_code=422, detail="faces must name at least one face")
    unknown = [f for f in faces if f not in briefs]
    if unknown:
        raise HTTPException(status_code=422,
                            detail=f"unknown face(s) {unknown}; known: {list(briefs)}")

    reference = None
    if body.references:
        wanted = {str(face).lower(): str(aid) for face, aid in body.references.items() if aid}
        unknown_refs = [face for face in wanted if face not in briefs]
        if unknown_refs:
            raise HTTPException(status_code=422, detail={
                "code": "unknown_reference_face", "faces": unknown_refs,
                "known": list(briefs)})
        reference = {face: _reference_bytes(aid, acct) for face, aid in wanted.items()}
    elif body.reference_asset_id:
        reference = _reference_bytes(body.reference_asset_id, acct)

    try:
        result = pp.build(design, out_dir=body.out_dir, faces=faces,
                          width=body.width, height=body.height,
                          tier=body.tier, seed=body.seed, reference=reference)
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
