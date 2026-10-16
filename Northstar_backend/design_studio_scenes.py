"""Design Studio — mockup scene/product gallery + structured prompt planning.

Competitive-RE build (2026-10-16), item 2: DYP.ai ships a curated
product-type x scene economy and assembles prompts as
``[SCENE] / [PRODUCT] / [CUSTOM PROMPT]``; this module gives Northstar the
backend half — catalogs + deterministic prompt assembly (+ optional enqueue
into the async lane). Renders still happen on the operator's local engine.

No provider calls, no cost.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from design_studio_api import studio_account

try:  # async lane stays optional at import time (standalone tests)
    from design_studio_async import submit_generation
except Exception:  # pragma: no cover
    submit_generation = None  # type: ignore[assignment]

router = APIRouter(prefix="/api/design-studio", tags=["design-studio-scenes"])

SCENES = [
    {"id": "studio-white", "name": "Studio — seamless white", "category": "studio",
     "prompt": "seamless white studio backdrop, soft top light, gentle contact shadow, product centred"},
    {"id": "studio-warm", "name": "Studio — warm beige", "category": "studio",
     "prompt": "warm beige paper backdrop, soft window light from the left, subtle shadow falloff"},
    {"id": "kitchen-marble", "name": "Kitchen — marble counter", "category": "kitchen",
     "prompt": "bright kitchen marble counter, morning light, shallow depth of field, blurred appliances"},
    {"id": "kitchen-wood", "name": "Kitchen — oak table", "category": "kitchen",
     "prompt": "oak dining table, natural daylight, linen napkin, breakfast props, shallow depth of field"},
    {"id": "bathroom-spa", "name": "Bathroom — spa shelf", "category": "bathroom",
     "prompt": "stone bathroom shelf, eucalyptus sprig, steam-soft light, calm spa mood"},
    {"id": "outdoor-picnic", "name": "Outdoor — picnic grass", "category": "outdoor",
     "prompt": "sunlit picnic blanket on grass, dappled light, summer energy, blurred greenery"},
    {"id": "flatlay-overhead", "name": "Flat lay — overhead props", "category": "flatlay",
     "prompt": "overhead flat lay on textured paper, minimal props framing the product, even soft light"},
    {"id": "gradient-minimal", "name": "Gradient — minimal backdrop", "category": "gradient",
     "prompt": "smooth studio gradient backdrop, no props, crisp edge lighting, e-commerce clean"},
]

PRODUCTS = [
    {"id": "standup-pouch", "name": "Stand-up pouch", "templates": ["label_rounded_rectangle"],
     "note": "Coffee/tea/snacks pouch."},
    {"id": "tincture-bottle", "name": "Tincture bottle", "templates": ["label_rounded_rectangle"],
     "note": "Dropper bottle, tall narrow label."},
    {"id": "cream-jar", "name": "Cream jar", "templates": ["label_circle"],
     "note": "50-100ml cosmetic jar."},
    {"id": "supplement-jar", "name": "Supplement jar", "templates": ["label_circle"],
     "note": "Bulk powder/capsules jar."},
    {"id": "candle-tin", "name": "Candle tin", "templates": ["label_circle"],
     "note": "Round tin lid plus side wrap."},
    {"id": "tube", "name": "Squeeze tube", "templates": ["label_rectangle"],
     "note": "Cosmetics tube wrap."},
    {"id": "folding-carton", "name": "Folding carton", "templates": ["tuck_end"],
     "note": "Retail shelf carton."},
    {"id": "shipping-box", "name": "Shipping/mailer box", "templates": ["rsc_box"],
     "note": "Corrugated e-commerce box."},
]

_SCENE_BY_ID = {s["id"]: s for s in SCENES}
_PRODUCT_BY_ID = {p["id"]: p for p in PRODUCTS}


def assemble_mockup_prompt(*, scene: Optional[dict] = None, product: Optional[dict] = None,
                           custom_prompt: Optional[str] = None,
                           message: Optional[str] = None) -> str:
    """DYP-style structured assembly, made explicit and testable."""
    lines = []
    if product:
        lines.append(f"[PRODUCT] {product['name']} :: {product.get('note', '')}")
    if scene:
        lines.append(f"[SCENE] {scene['name']} :: {scene['prompt']}")
    if custom_prompt:
        lines.append(f"[CUSTOM PROMPT] {custom_prompt.strip()}")
    if message:
        lines.append(f"[BRIEF] {message.strip()}")
    lines.append("[NEGATIVE] no distorted geometry, no warped text, no extra products, no watermarks")
    return "\n".join(lines)


class MockupPlanIn(BaseModel):
    scene_id: Optional[str] = Field(None, max_length=60)
    product_id: Optional[str] = Field(None, max_length=60)
    custom_prompt: Optional[str] = Field(None, max_length=600)
    message: Optional[str] = Field(None, max_length=2000)
    project_id: Optional[str] = None
    enqueue: bool = False
    width: Optional[int] = Field(None, ge=64, le=4096)
    height: Optional[int] = Field(None, ge=64, le=4096)
    tier: str = Field("draft")


@router.get("/scenes")
def list_scenes(acct: str = Depends(studio_account)):
    """Catalog of scenes + product types (prompt fragments; renders stay local)."""
    return {"scenes": SCENES, "products": PRODUCTS,
            "notes": ["Scenes are reusable prompt fragments for the local engine.",
                      "Pair a product with a scene, or write a custom scene prompt."]}


@router.post("/mockup/plan")
def mockup_plan(body: MockupPlanIn, acct: str = Depends(studio_account)):
    """Assemble a structured mockup prompt; optionally queue a local render."""
    scene: Optional[dict] = None
    if body.scene_id:
        scene = _SCENE_BY_ID.get(body.scene_id)
        if scene is None:
            raise HTTPException(status_code=422, detail=f"unknown scene_id {body.scene_id!r}")
    product: Optional[dict] = None
    if body.product_id:
        product = _PRODUCT_BY_ID.get(body.product_id)
        if product is None:
            raise HTTPException(status_code=422, detail=f"unknown product_id {body.product_id!r}")
    if not (scene or product or body.custom_prompt or body.message):
        raise HTTPException(status_code=422,
                            detail="Nothing to plan: pick a product, pick a scene, or write a custom prompt.")
    custom = (body.custom_prompt or "").strip()
    msg = (body.message or "").strip()
    if not (scene or product or custom or msg):
        raise HTTPException(status_code=422,
                            detail="Nothing to plan: pick a product, pick a scene, or write a custom prompt.")

    prompt = assemble_mockup_prompt(scene=scene, product=product,
                                    custom_prompt=custom, message=msg)
    out: Dict[str, Any] = {
        "prompt": prompt,
        "suggested_templates": (product or {}).get("templates", []),
        "scene": scene,
        "product": product,
        "enqueued": None,
    }
    if body.enqueue:
        if submit_generation is None:
            raise HTTPException(status_code=503, detail="async generation lane unavailable")
        out["enqueued"] = submit_generation(
            acct, brief=prompt, kind="image", tier=body.tier, purpose="mockup-plan",
            width=body.width, height=body.height, project_id=body.project_id,
        )
    return out
