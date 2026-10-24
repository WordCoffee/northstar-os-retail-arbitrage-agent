"""Amazon Image & A+ agent — module planning with exact, verified sizes.

Module sizes and content rules are VERIFIED against
`xianyu110/ecommerce-image-skills`, `skills/amazon-a-plus/SKILL.md`
("A+ module sizes (Basic A+)" + the rule line below the table):

    970x600 header with text | 600x180 company logo | 970x300 image + text overlay
    300x400 main / 350x175 sidebar | 4 x 220x220 | 3 x 300x300 | 300x300 left/right
    Premium A+ 1464x600 desktop / 600x450 mobile
    max 2 MB per image; JPG/PNG; no prices, promos, shipping claims or competitor refs

The agent plans and validates. Generation stays with the local image lane; nothing
here calls a provider.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

MAX_MODULE_BYTES = 2 * 1024 * 1024

#: module_id -> (label, width, height, tiles)
MODULES: Dict[str, Dict[str, Any]] = {
    "header": {"label": "Standard image header with text", "w": 970, "h": 600, "tiles": 1},
    "logo": {"label": "Standard company logo", "w": 600, "h": 180, "tiles": 1},
    "banner": {"label": "Standard image & dark/light text overlay", "w": 970, "h": 300, "tiles": 1},
    "sidebar": {"label": "Standard single image & sidebar", "w": 300, "h": 400, "tiles": 1},
    "sidebar_thumb": {"label": "Standard sidebar thumbnail", "w": 350, "h": 175, "tiles": 1},
    "four_tiles": {"label": "Standard four image & text", "w": 220, "h": 220, "tiles": 4},
    "three_tiles": {"label": "Standard three images & text", "w": 300, "h": 300, "tiles": 3},
    "single": {"label": "Standard single left/right image", "w": 300, "h": 300, "tiles": 1},
    "premium_desktop": {"label": "Premium A+ full image (desktop)", "w": 1464, "h": 600, "tiles": 1},
    "premium_mobile": {"label": "Premium A+ full image (mobile)", "w": 600, "h": 450, "tiles": 1},
}

#: The studied default story order.
DEFAULT_PLAN = ("header", "three_tiles", "banner", "four_tiles", "comparison")

#: Prohibited in A+ imagery/copy, per the same source.
FORBIDDEN_PATTERNS = {
    "price": re.compile(r"\$\s?\d|\busd\b|\bprice\b|\bmsrp\b", re.I),
    "promotion": re.compile(r"\b(sale|discount|% off|coupon|deal|free shipping)\b", re.I),
    "shipping": re.compile(r"\b(free shipping|ships in|delivery by|prime delivery)\b", re.I),
    "competitor": re.compile(r"\b(better than|vs\.?\s+[A-Z]|outperforms)\b", re.I),
    "medical": re.compile(r"\b(cures?|treats?|prevents?|reverses?)\b", re.I),
}

IDENTITY_LOCK_FIELDS = ("shape", "colour", "logo_text", "parts", "must_not")


def identity_lock(spec: Dict[str, Any]) -> str:
    """The studied identity-lock block. Unknown fields say so instead of guessing."""
    get = lambda k: str(spec.get(k) or "[MISSING: %s]" % k)  # noqa: E731
    return (
        "PRODUCT IDENTITY LOCK (do not change):\n"
        f"- Shape & proportions: {get('shape')}\n"
        f"- Colour & finish: {get('colour')}\n"
        f"- Logo & printed text: {get('logo_text')}\n"
        f"- Parts & details: {get('parts')}\n"
        f"- Must NOT appear: {get('must_not')}\n")


def screen_copy(text: str) -> List[Dict[str, str]]:
    """Flag A+ prohibited content. Returns the hits, never silently passes."""
    hits: List[Dict[str, str]] = []
    for kind, pattern in FORBIDDEN_PATTERNS.items():
        for m in pattern.finditer(str(text or "")):
            hits.append({"kind": kind, "match": m.group(0)})
    return hits


def missing_inputs(spec: Dict[str, Any]) -> List[Dict[str, str]]:
    gaps: List[Dict[str, str]] = []
    for key in ("product",):
        if not spec.get(key):
            gaps.append({"field": key, "question": "which product is this A+ page for?"})
    return gaps


def plan(*, spec: Dict[str, Any], allow_incomplete: bool = False) -> Dict[str, Any]:
    """Build the module plan, prompts and validation for one A+ page."""
    gaps = missing_inputs(spec)
    if gaps and not allow_incomplete:
        return {"ok": False, "status": "needs_input",
                "summary": f"{len(gaps)} thing(s) first.", "questions": gaps,
                "assets": []}

    requested = spec.get("modules") or list(DEFAULT_PLAN)
    modules: List[Dict[str, Any]] = []
    for mid in requested:
        if mid == "comparison":
            modules.append({
                "module": "comparison",
                "label": "Comparison chart (own range only)",
                "size": None,
                "note": "comparison charts compare YOUR products; competitor references are "
                        "prohibited",
                "tiles": 0,
            })
            continue
        m = MODULES.get(mid)
        if not m:
            continue
        modules.append({
            "module": mid, "label": m["label"],
            "size": f"{m['w']}x{m['h']}",
            "tiles": m["tiles"],
            "bytes_max": MAX_MODULE_BYTES,
            "prompt": _prompt(mid, m, spec),
        })

    lock = identity_lock(spec)
    copy = str(spec.get("copy") or "")
    return {
        "ok": True,
        "status": "planned",
        "summary": (f"{len(modules)} A+ module(s) planned at exact pixel sizes"
                    + ("" if spec.get("modules") else " (standard 5-module story)")
                    + ". Generate each with the local image lane, then validate before upload."),
        "used_default_plan": not bool(spec.get("modules")),
        "identity_lock": lock,
        "modules": modules,
        "rules": [
            "max 2 MB per image", "JPG or PNG",
            "no prices, promotions, shipping claims or competitor references",
            "text shown in an image should also appear in the alt text",
        ],
        "copy_check": screen_copy(copy) if copy else [],
        "validation": validate_plan(modules),
        "assets": [],
    }


def _prompt(mid: str, m: Dict[str, Any], spec: Dict[str, Any]) -> str:
    product = spec.get("product") or "the product"
    style = spec.get("style") or "clean premium studio"
    return (f"A+ module '{mid}' for {product}. {style}. Composition must work at "
            f"{m['w']}x{m['h']} px with no text baked in (copy is authored as a layer). "
            f"No prices, promotions, shipping claims or competitor references.")


def validate_plan(modules: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    problems: List[str] = []
    if not modules:
        problems.append("no modules planned")
    ids = [m["module"] for m in modules]
    if ids.count("header") > 1:
        problems.append("more than one header module")
    if "header" not in ids and len(ids) > 2:
        problems.append("a page of this length usually wants a header module")
    return {"ok": not problems, "problems": problems, "modules": len(modules)}


def validate_module_image(path: str | Path, module_id: str) -> Dict[str, Any]:
    """Size, weight and format for one rendered module tile."""
    from PIL import Image

    m = MODULES.get(module_id)
    if not m:
        return {"ok": False, "problems": [f"unknown module {module_id!r}"], "metrics": {}}
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "problems": [f"file not found: {p}"], "metrics": {}}
    size_bytes = p.stat().st_size
    img = Image.open(p)
    problems: List[str] = []
    if (img.width, img.height) != (m["w"], m["h"]):
        problems.append(f"{img.width}x{img.height} does not match the {m['w']}x{m['h']} module")
    if size_bytes > MAX_MODULE_BYTES:
        problems.append(f"{size_bytes / 1_048_576:.2f} MB exceeds the 2 MB limit")
    if (img.format or "").upper() not in ("JPEG", "JPG", "PNG"):
        problems.append(f"format {img.format} is not JPG or PNG")
    return {"ok": not problems, "problems": problems,
            "metrics": {"width": img.width, "height": img.height,
                        "bytes": size_bytes, "format": img.format}}
