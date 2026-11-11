"""The brand-art dispatch layer: one entry point for every packaging form.

`mogra_label_art` draws the Mogra stand-up pouch — a dietary-supplement label
with a real Supplement Facts block, written for that one SKU. That is the
*pouch* form, and it is the only design the app could print until now:
`mogra_label_art.design_for('word-coffee')` raised `unknown label design`, so a
second brand had no reachable path through `product_picture.build` at all.

This module is the layer `product_picture` calls instead:

* a design that declares ``supplement_facts`` renders through ``mogra_label_art``
  (byte-identical output: the shipping pouch is not touched);
* any other design renders through the generic print system
  (``package_art.render_front_box`` / ``render_back_box``) on the face size the
  design declares, so a new brand is a data entry, not a code change.

Every design is deterministic, offline, and free: pure PIL, no provider call, no
network, no cost. A claim is drawn only when the design declares it — nothing
here invents a certification or a nutrition fact.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image

import mogra_label_art
import package_art

POUCH = "stand_up_pouch"
GIFT_BOX = "gift_box"

FORM_NAMES: Dict[str, str] = {
    POUCH: "stand-up pouch, front and back panels",
    GIFT_BOX: "folding carton (gift box), front and back panels",
}

#: Word Coffee — a slim pale-pink and cream gift box. The briefs in
#: `ty/seller_briefs_heldout_modes.json` (PO-002/004/006/008/010/012) describe
#: exactly this object, and until now no renderer could draw it.
WORD_COFFEE: Dict[str, Any] = {
    "id": "word-coffee",
    "brand": "WORD COFFEE",
    "product": "FOR MOM",
    "form": GIFT_BOX,
    "face_mm": {"front": [100.0, 200.0], "back": [100.0, 200.0]},
    "theme": "blush",
    "script_line": "For Mom",
    "subtitle": "12 COFFEE SACHETS",
    "tagline": "Empowering Moms, One Message at a Time",
    "descriptor": "Ground coffee  ·  medium roast  ·  100% arabica",
    "net_weight": "120 g (4.2 oz)",
    "net_weight_line": "NET WT. 120 g (4.2 oz)",
    "servings": "12 sachets · 10 g each",
    "inside": ("Twelve single-serve sachets of medium-roast arabica, each printed "
               "with a message for her."),
    "ingredients": "Ground roasted coffee (100% arabica).",
    "roast": "Medium roast, ground for filter and pour-over.",
    "brew": [
        "1. Empty one sachet into a cup.",
        "2. Pour 250 ml of water just off the boil.",
        "3. Steep 3 minutes, stir, and serve.",
    ],
    "about": ("Word Coffee pairs a good cup with something worth reading. The box "
              "is made to be given, not just opened."),
    "company": "DISTRIBUTED BY T2 HOLDINGS LLC",
    "lot_code": "LOT  WC-0000",
    "best_by": "BEST BY  00/0000",
    "barcode_digits": "8 50000 00000 4",
    "draft_note": "DRAFT  ·  VERIFY BEFORE PRINT",
    "back_draft_note": "DRAFT  ·  VERIFY INGREDIENTS AND UPC BEFORE PRINT",
    "status": "DRAFT - copy, ingredients and UPC must be verified before print",
    "claims": {"organic_seal": False, "fda": False,
               "note": "no certification is claimed that the brand has not got"},
}

_DESIGN_IDS = {
    "mogra-lions-mane": "mogra-lions-mane",
    "mogra_lions_mane": "mogra-lions-mane",
    "mogra": "mogra-lions-mane",
    "word-coffee": "word-coffee",
    "word_coffee": "word-coffee",
}

#: Seller brief `product_line` -> design id. Explicit: a brief that names a line
#: nobody has designed raises, and never silently renders a different brand.
_PRODUCT_LINES = {
    "lions-mane": "mogra-lions-mane",
    "mogra-lions-mane": "mogra-lions-mane",
    "mogra": "mogra-lions-mane",
    "word-coffee": "word-coffee",
    "word_coffee": "word-coffee",
}


def known() -> List[str]:
    """The design ids this app can actually print."""
    return sorted({v for v in _DESIGN_IDS.values()})


def design_for(product: str = "mogra-lions-mane") -> Dict[str, Any]:
    """A copy of the declared design; callers may edit it without side effects."""
    key = _DESIGN_IDS.get(str(product or "").strip().lower())
    if key is None:
        raise ValueError(
            f"unknown label design {product!r}; known designs: {', '.join(known())}")
    if key == "word-coffee":
        return copy.deepcopy(WORD_COFFEE)
    return mogra_label_art.design_for(key)


def design_for_brief(brief: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the design a seller brief asks for, by its declared product line.

    A brief with no line, or a line with no design, raises and names the brief —
    the harness's circuit breaker treats that as a stopped pass, not a brief that
    quietly renders as Mogra.
    """
    line = str((brief or {}).get("product_line") or "").strip().lower()
    brief_id = str((brief or {}).get("id") or "?")
    if not line:
        raise ValueError(f"brief {brief_id} declares no product_line")
    key = _PRODUCT_LINES.get(line)
    if key is None:
        raise ValueError(
            f"brief {brief_id} asks for product_line {line!r}, which has no "
            f"design; known lines: {', '.join(sorted(_PRODUCT_LINES))}")
    return design_for(key)


def form_of(design: Dict[str, Any]) -> str:
    form = str(design.get("form") or "").strip()
    if form in FORM_NAMES:
        return form
    # A design with a Supplement Facts panel is the pouch form; that is what the
    # panel can legally appear on.
    return POUCH if design.get("supplement_facts") else GIFT_BOX


def face_mm(design: Dict[str, Any], face: str = "front") -> Tuple[float, float]:
    declared = (design.get("face_mm") or {}).get(face)
    if isinstance(declared, (list, tuple)) and len(declared) == 2:
        return float(declared[0]), float(declared[1])
    if form_of(design) == GIFT_BOX:
        return (100.0, 200.0)
    w, h = mogra_label_art.BASE_SIZE
    return (w / mogra_label_art.DPI * 25.4, h / mogra_label_art.DPI * 25.4)


def _spec(design: Dict[str, Any]) -> Dict[str, Any]:
    spec = dict(design)
    spec.setdefault("theme", "blush")
    spec.setdefault("weight", design.get("net_weight_line") or design.get("net_weight"))
    spec.setdefault("motif", "bean")
    return spec


def front_panel(design: Optional[Dict[str, Any]] = None,
                size: Optional[Sequence[int]] = None) -> Image.Image:
    """Front artwork for whatever form the design declares."""
    dsn = design or mogra_label_art.MOGRA_LIONS_MANE
    if form_of(dsn) == POUCH:
        return mogra_label_art.front_panel(dsn, size=size)
    width_mm, height_mm = face_mm(dsn, "front")
    img = package_art.render_front_box(_spec(dsn), width_mm=width_mm,
                                       height_mm=height_mm)
    if size is not None:
        img = img.resize((int(size[0]), int(size[1])), Image.LANCZOS)
    return img


def back_panel(design: Optional[Dict[str, Any]] = None,
               size: Optional[Sequence[int]] = None) -> Image.Image:
    """Back artwork for whatever form the design declares."""
    dsn = design or mogra_label_art.MOGRA_LIONS_MANE
    if form_of(dsn) == POUCH:
        return mogra_label_art.back_panel(dsn, size=size)
    width_mm, height_mm = face_mm(dsn, "back")
    img = package_art.render_back_box(_spec(dsn), width_mm=width_mm,
                                      height_mm=height_mm)
    if size is not None:
        img = img.resize((int(size[0]), int(size[1])), Image.LANCZOS)
    return img


def panels(design: Optional[Dict[str, Any]] = None) -> Dict[str, Image.Image]:
    return {"front": front_panel(design), "back": back_panel(design)}


def manifest(design: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    dsn = design or mogra_label_art.MOGRA_LIONS_MANE
    form = form_of(dsn)
    width_mm, height_mm = face_mm(dsn, "front")
    return {
        "id": dsn.get("id") or "",
        "brand": dsn["brand"],
        "product": dsn["product"],
        "form": form,
        "format": FORM_NAMES[form],
        "theme": dsn.get("theme"),
        "face_mm": [round(width_mm, 2), round(height_mm, 2)],
        "net_weight": dsn.get("net_weight"),
        "status": dsn.get("status") or "DRAFT",
        "claims": dsn.get("claims") or {},
    }


__all__ = ["POUCH", "GIFT_BOX", "FORM_NAMES", "WORD_COFFEE", "known",
           "design_for", "design_for_brief", "form_of", "face_mm",
           "front_panel", "back_panel", "panels", "manifest"]
