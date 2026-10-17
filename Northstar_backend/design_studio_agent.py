"""Design Studio — chat-to-design-brief agent (deterministic core).

Competitive-RE build (2026-10-16): both competitors convert a chat message into
a STRUCTURED design spec before any pixels are made (Packify's "Initial
Analysis" step; DYP's ``[CUSTOM PROMPT]/[SCENE]/[PRODUCT]`` assembly). This
module ships that conversion for Northstar:

- `POST /agent/brief` — message (+ optional product context) -> structured brief
  (palette, suggested dieline templates, copy blocks, directives, negative
  prompt) plus an assembled ``[PRODUCT]/[FORMAT]/[PALETTE]/[COPY]/[DIRECTIVES]/
  [NEGATIVE]`` prompt string. Deterministic, offline, and fully testable.
- Optional ``enqueue=true`` submits the assembled prompt to the async
  generation lane (design_studio_async.submit_generation) — same engine gates,
  same credit policy.
- Optional LLM sharpening: set ``DESIGN_AGENT_LLM=1`` to let the local
  AutothinK adapter suggest extra directives. FAIL-OPEN by design — any import
  or runtime problem falls back to the deterministic brief.

No provider calls, no cost.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from design_studio_api import studio_account
from design_studio_print import TEMPLATES

try:  # async lane is optional at import time (keeps this module standalone-testable)
    from design_studio_async import submit_generation
except Exception:  # pragma: no cover
    submit_generation = None  # type: ignore[assignment]

router = APIRouter(prefix="/api/design-studio", tags=["design-studio-agent"])

_PALETTES: Dict[str, Dict[str, Any]] = {
    "eco": {"name": "natural kraft + forest green", "colors": ["#3f3a2f", "#2f5d3a", "#f3efe6"]},
    "sustainab": {"name": "natural kraft + forest green", "colors": ["#3f3a2f", "#2f5d3a", "#f3efe6"]},
    "luxury": {"name": "deep charcoal + gold", "colors": ["#1c1c1e", "#c9a227", "#f6f3ea"]},
    "premium": {"name": "deep charcoal + gold", "colors": ["#1c1c1e", "#c9a227", "#f6f3ea"]},
    "bold": {"name": "black + accent red", "colors": ["#111111", "#e63946", "#ffffff"]},
    "pastel": {"name": "soft pastel", "colors": ["#f6d6d6", "#cfe8d4", "#e7e0f6"]},
    "minimal": {"name": "paper white + slate", "colors": ["#ffffff", "#334155", "#f1f5f9"]},
    "kids": {"name": "bright primary", "colors": ["#f59e0b", "#3b82f6", "#ef4444"]},
}
_DEFAULT_PALETTE = {"name": "warm neutral + deep green", "colors": ["#f6f1e7", "#1f3d2b", "#c8b08a"]}

_FORMAT_HINTS = [
    ("pouch", "label_rounded_rectangle"),
    ("bag", "label_rectangle"),
    ("bottle", "label_rounded_rectangle"),
    ("jar", "label_circle"),
    ("can", "label_rectangle"),
    ("tube", "label_rectangle"),
    ("cup", "label_rounded_rectangle"),
    ("box", "rsc_box"),
    ("carton", "rsc_box"),
    ("sleeve", "sleeve"),
    ("tuck", "tuck_end"),
]

_VALID_TEMPLATE_IDS = {t["id"] for t in TEMPLATES}

_DIRECTIVES = [
    "High shelf readability at 1 metre (brand first, product second, variant third).",
    "Leave an 8mm clear margin on every panel for retailer/deal stickers.",
    "Legal panel layout: nutrition/dosage block on the back panel, quiet background.",
]
_NEGATIVE = ("no tiny type, no low-contrast copy, no clip-art, no mockup watermarks, "
             "no invented certifications or claims")


def pick_palette(text: str) -> Dict[str, Any]:
    low = (text or "").lower()
    for key, palette in _PALETTES.items():
        if key in low:
            return palette
    return _DEFAULT_PALETTE


def suggest_templates(text: str) -> List[str]:
    low = (text or "").lower()
    out: List[str] = []
    for keyword, template_id in _FORMAT_HINTS:
        if keyword in low and template_id not in out:
            out.append(template_id)
    if not out:
        out = ["label_rounded_rectangle", "rsc_box"]
    return [t for t in out if t in _VALID_TEMPLATE_IDS] or ["label_rounded_rectangle"]


def assemble_prompt(spec: Dict[str, Any]) -> str:
    """The structured assembly both competitors use; ours is explicit + testable."""
    product = spec.get("product") or {}
    title = product.get("title") or "untitled product"
    category = f" ({product['category']})" if product.get("category") else ""
    copy = spec.get("copy") or {}
    lines = [
        f"[PRODUCT] {title}{category}",
        f"[FORMAT] {', '.join((spec.get('format') or {}).get('suggested_templates', []))}",
        f"[PALETTE] {spec['palette']['name']} :: {' '.join(spec['palette']['colors'])}",
        "[COPY] " + str(copy.get("front_headline", "")) + " | " + "; ".join(copy.get("benefits", [])),
        "[DIRECTIVES] " + "; ".join(spec.get("directives", [])),
        f"[NEGATIVE] {spec.get('negative', '')}",
    ]
    return "\n".join(lines)


def build_brief(message: str, product: Optional[Dict[str, Any]] = None,
                kind: str = "image") -> Dict[str, Any]:
    """Deterministic message -> structured design brief."""
    msg = (message or "").strip()
    product = dict(product or {})
    title = product.get("title") or (msg[:80] if msg else "untitled product")
    blob = f"{msg} {title} {product.get('category', '')} {product.get('brand', '')}"

    benefits = ["Made for daily use", "Small-batch quality", "Easy to store, easy to love"]
    spec: Dict[str, Any] = {
        "version": 1,
        "kind": kind,
        "product": {
            "title": product.get("title") or title,
            "category": product.get("category"),
            "brand": product.get("brand") or "Northstar draft brand",
            "asin": product.get("asin"),
        },
        "palette": pick_palette(blob),
        "format": {
            "suggested_templates": suggest_templates(blob),
            "render_hint": "POST /api/design-studio/print/dielines {template_id, params}",
        },
        "copy": {
            "front_headline": product.get("title") or "Draft headline — confirm copy",
            "benefits": benefits,
            "instructions": "Back panel: preparation/usage copy to be confirmed by the operator.",
        },
        "directives": list(_DIRECTIVES),
        "negative": _NEGATIVE,
        "sections": ["PRODUCT", "FORMAT", "PALETTE", "COPY", "DIRECTIVES", "NEGATIVE"],
    }
    spec["prompt_text"] = assemble_prompt(spec)
    return spec


def _maybe_llm_enhance(spec: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Optional local-LLM sharpening; fail-open to the deterministic spec."""
    if os.environ.get("DESIGN_AGENT_LLM", "0").strip().lower() not in ("1", "true", "yes"):
        return spec
    try:
        import importlib
        import sys as _sys
        from pathlib import Path as _Path
        _repo_root = str(_Path(__file__).resolve().parent.parent)
        if _repo_root not in _sys.path:
            _sys.path.insert(0, _repo_root)  # the autothink package lives at repo root
        adapter_mod = importlib.import_module("autothink.backend.llm_adapter")
        adapter_cls = getattr(adapter_mod, "UnifiedLLMAdapter", None)
        if adapter_cls is None:
            spec["llm_enhanced"] = False
            return spec
        # The module exposes a CLASS with .generate(query) -> dict; the old
        # code asked the MODULE for a `generate` function that never existed,
        # so this enhancement always fell through to the deterministic brief.
        result = adapter_cls().generate(
            f"List 3 short packaging design directives for: {message[:400]}. One per line.",
            system_prompt="You write terse packaging design directives. One per line, no numbering.",
        )
        if not isinstance(result, dict) or not result.get("ok"):
            spec["llm_enhanced"] = False
            return spec
        text = str(result.get("content") or "")
        extra = [ln.strip("-*• \t") for ln in text.splitlines() if ln.strip()][:3]
        if extra:
            spec["directives"] = extra + spec["directives"]
            spec["prompt_text"] = assemble_prompt(spec)
            spec["llm_enhanced"] = True
    except Exception:
        spec["llm_enhanced"] = False
    return spec


class BriefIn(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)
    product: Optional[Dict[str, Any]] = None
    kind: str = Field(default="image")
    project_id: Optional[str] = None
    enqueue: bool = False


@router.post("/agent/brief")
def agent_brief(body: BriefIn, acct: str = Depends(studio_account)):
    """Chat message -> structured brief (+ optional enqueue into the async lane)."""
    if body.kind not in ("image", "video"):
        raise HTTPException(status_code=422, detail="kind must be image or video")
    spec = build_brief(body.message, body.product, body.kind)
    spec = _maybe_llm_enhance(spec, body.message)
    out: Dict[str, Any] = {
        "reply": (f"Draft plan for {spec['product'].get('title') or 'your product'}: "
                  f"{spec['palette']['name']} palette; suggested dielines "
                  f"{', '.join(spec['format']['suggested_templates'])}. "
                  "Render a dieline via /print/dielines or enqueue a local generation."),
        "brief": spec,
        "enqueued": None,
    }
    if body.enqueue:
        if submit_generation is None:
            raise HTTPException(status_code=503, detail="async generation lane unavailable")
        out["enqueued"] = submit_generation(
            acct, brief=spec["prompt_text"], kind=body.kind,
            purpose="design-agent", project_id=body.project_id,
        )
    return out
