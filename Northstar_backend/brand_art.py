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
CYLINDER = "rigid_cylinder"
APPAREL = "apparel_flat"

FORM_NAMES: Dict[str, str] = {
    POUCH: "stand-up pouch, front and back panels",
    GIFT_BOX: "folding carton (gift box), front and back panels",
    CYLINDER: "rigid cylinder (jar, bottle, tube or canister), wrap-around label",
    APPAREL: "apparel with a flat chest print area, front and back",
}

#: Which blank body the *drawn* plate draws for a form. The plate must be the
#: shape the panel belongs on, or the label is printed on the wrong object.
PLATE_KINDS: Dict[str, str] = {
    POUCH: "pouch",
    GIFT_BOX: "gift_box",
    CYLINDER: "cylinder",
    APPAREL: "apparel",
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

#: A rigid-cylinder SKU on the Word Coffee brand: a 250 g canister of the same
#: ground coffee the gift box holds. The label wraps the body, so `face_mm` is
#: the VISIBLE HALF of the circumference by the label height (the compositor maps
#: the panel across the 180-degree arc), not a flat carton face.
WORD_COFFEE_CANISTER: Dict[str, Any] = {
    "id": "word-coffee-canister",
    "plate_subject": "cylindrical coffee canister with a screw lid",
    "brand": "WORD COFFEE",
    "product": "GROUND COFFEE",
    "form": CYLINDER,
    "face_mm": {"front": [118.0, 100.0], "back": [118.0, 100.0]},
    "theme": "blush",
    "script_line": "Every Morning",
    "subtitle": "MEDIUM ROAST  ·  100% ARABICA",
    "tagline": "Empowering Moms, One Message at a Time",
    "descriptor": "Ground coffee  ·  medium roast  ·  100% arabica",
    "net_weight": "250 g (8.8 oz)",
    "net_weight_line": "NET WT. 250 g (8.8 oz)",
    "servings": "25 servings · 10 g each",
    "inside": ("A resealable canister of medium-roast arabica, ground for filter "
               "and pour-over."),
    "ingredients": "Ground roasted coffee (100% arabica).",
    "label_sections": [
        {"head": "ROAST", "body": "Medium roast, ground for filter and pour-over."},
        {"head": "HOW TO BREW", "body": "One heaped tablespoon per 250 ml of water "
                                       "just off the boil. Steep 3 minutes, stir, serve."},
        {"head": "STORAGE", "body": "Keep the lid closed, in a cool dark place."},
    ],
    "about": ("Word Coffee pairs a good cup with something worth reading. The canister "
              "is refillable and made to sit on the counter."),
    "company": "DISTRIBUTED BY T2 HOLDINGS LLC",
    "lot_code": "LOT  WC-1000",
    "best_by": "BEST BY  00/0000",
    "barcode_digits": "8 50000 00000 5",
    "draft_note": "DRAFT  ·  VERIFY BEFORE PRINT",
    "back_draft_note": "DRAFT  ·  VERIFY INGREDIENTS AND UPC BEFORE PRINT",
    "status": "DRAFT - copy, ingredients and UPC must be verified before print",
    "claims": {"organic_seal": False, "fda": False,
               "note": "no certification is claimed that the brand has not got"},
}

#: A printed ceramic mug on the Word Coffee brand: the wrap label is the print.
WORD_COFFEE_MUG: Dict[str, Any] = {
    "id": "word-coffee-mug",
    "plate_subject": "ceramic mug with a handle",
    "brand": "WORD COFFEE",
    "product": "CERAMIC MUG",
    "form": CYLINDER,
    "face_mm": {"front": [129.0, 70.0], "back": [129.0, 70.0]},
    "theme": "blush",
    "script_line": "One Message",
    "subtitle": "CERAMIC  ·  350 ML",
    "tagline": "Empowering Moms, One Message at a Time",
    "net_weight": "350 ml (11.8 fl oz)",
    "net_weight_line": "350 ml (11.8 fl oz)",
    "servings": "Dishwasher and microwave safe",
    "inside": "A glazed stoneware mug, 350 ml, printed around the body.",
    "ingredients": "Stoneware, lead-free glaze, ceramic print.",
    "label_sections": [
        {"head": "CARE", "body": "Dishwasher and microwave safe. Do not use on a "
                                 "direct flame or under a grill."},
        {"head": "MADE", "body": "Printed and fired in small batches."},
    ],
    "about": "The print wraps the body; the handle stays plain.",
    "company": "DISTRIBUTED BY T2 HOLDINGS LLC",
    "lot_code": "LOT  WC-2000",
    "best_by": "NO EXPIRY",
    "barcode_digits": "8 50000 00000 8",
    "draft_note": "DRAFT  ·  VERIFY BEFORE PRINT",
    "back_draft_note": "DRAFT  ·  VERIFY COPY AND UPC BEFORE PRINT",
    "status": "DRAFT - copy and UPC must be verified before print",
    "claims": {"organic_seal": False, "fda": False, "food_safe": False,
               "note": "no certification is claimed that the brand has not got"},
}

#: A body-oil bottle on its own brand. A cylinder label has no carton panels, so
#: the back is driven by `label_sections` rather than by coffee-specific headings.
HARBOR_BODY_OIL: Dict[str, Any] = {
    "id": "harbor-body-oil",
    "plate_subject": "slim amber glass bottle with a pump cap",
    "brand": "HARBOR SAGE",
    "product": "BODY OIL",
    "form": CYLINDER,
    "face_mm": {"front": [63.0, 50.0], "back": [63.0, 50.0]},
    "theme": "sage",
    "script_line": "Calm",
    "subtitle": "BODY OIL  ·  LIGHTWEIGHT",
    "tagline": "Four oils, nothing else",
    "net_weight": "100 ml (3.4 fl oz)",
    "net_weight_line": "100 ml (3.4 fl oz)",
    "servings": "100 ml",
    "inside": "A light body oil of jojoba, sweet almond, rosehip and vitamin E.",
    "ingredients": ("Simmondsia chinensis (jojoba) seed oil, Prunus amygdalus dulcis "
                    "(sweet almond) oil, Rosa canina (rosehip) seed oil, tocopherol."),
    "label_sections": [
        {"head": "HOW TO USE", "body": "Warm two or three drops between the palms and "
                                       "press onto damp skin after a shower."},
        {"head": "STORAGE", "body": "Keep out of direct sunlight, below 25 C."},
    ],
    "about": "Made in small batches. Patch test before first use.",
    "company": "DISTRIBUTED BY T2 HOLDINGS LLC",
    "lot_code": "LOT  HS-0000",
    "best_by": "BEST BY  00/0000",
    "barcode_digits": "8 50000 00000 6",
    "draft_note": "DRAFT  ·  VERIFY BEFORE PRINT",
    "back_draft_note": "DRAFT  ·  VERIFY INGREDIENTS AND UPC BEFORE PRINT",
    "status": "DRAFT - copy, ingredients and UPC must be verified before print",
    "claims": {"organic_seal": False, "fda": False, "cruelty_free": False,
               "note": "no certification is claimed that the brand has not got"},
}

#: A pet supplement tub: a short, wide cylinder. The claims block is explicit
#: that nothing is approved for any condition, because a pet supplement label is
#: where an invented claim would be worst.
PINE_PAWS_JOINT: Dict[str, Any] = {
    "id": "pine-paws-joint",
    "plate_subject": "wide plastic supplement tub with a screw lid",
    "brand": "PINE PAWS",
    "product": "JOINT CHEWS",
    "form": CYLINDER,
    "face_mm": {"front": [141.0, 70.0], "back": [141.0, 70.0]},
    "theme": "forest",
    "script_line": "For the Long Walk",
    "subtitle": "SOFT CHEWS  ·  GLUCOSAMINE",
    "tagline": "A daily chew for older dogs",
    "net_weight": "180 g (60 chews)",
    "net_weight_line": "NET WT. 180 g (60 chews)",
    "servings": "60 soft chews · 3 g each",
    "inside": "Soft chicken-flavoured chews with glucosamine and green-lipped mussel.",
    "ingredients": ("Chicken meal, glycerin, glucosamine hydrochloride, green-lipped "
                    "mussel powder, flaxseed, mixed tocopherols."),
    "label_sections": [
        {"head": "FEEDING GUIDE", "body": "One chew daily for dogs up to 15 kg, two "
                                          "for larger dogs. Fresh water alongside."},
        {"head": "STORAGE", "body": "Reseal after use; keep cool and dry."},
    ],
    "about": ("A supplement, not a medicine. Not evaluated by any authority; no "
              "disease claim is made."),
    "company": "DISTRIBUTED BY T2 HOLDINGS LLC",
    "lot_code": "LOT  PP-0000",
    "best_by": "BEST BY  00/0000",
    "barcode_digits": "8 50000 00000 7",
    "draft_note": "DRAFT  ·  VERIFY BEFORE PRINT",
    "back_draft_note": "DRAFT  ·  VERIFY INGREDIENTS AND UPC BEFORE PRINT",
    "status": "DRAFT - copy, ingredients and UPC must be verified before print",
    "claims": {"organic_seal": False, "fda": False, "vet_approved": False,
               "note": "no certification and no disease claim is made"},
}

#: A cotton tee with a chest print. The print area is a declared physical size in
#: millimetres (a 280 x 350 mm chest panel on an adult large), so the artwork is
#: scaled from the garment's own measurement instead of being stretched to fit.
MOGRA_TEE: Dict[str, Any] = {
    "id": "mogra-tee",
    "plate_subject": "heavyweight cotton t-shirt laid flat",
    "brand": "MOGRA ORGANICS",
    "product": "LION'S MANE",
    "form": APPAREL,
    "face_mm": {"front": [280.0, 350.0], "back": [280.0, 350.0]},
    "theme": "forest",
    "script_line": "One Message at a Time",
    "subtitle": "ORGANIC  ·  SMALL BATCH",
    "tagline": "Wear the mushroom",
    "net_weight": "100% cotton",
    "net_weight_line": "100% COTTON",
    "servings": "ADULT LARGE",
    "inside": "Heavyweight cotton tee with a screen-printed chest panel.",
    "ingredients": "100% combed cotton. Machine wash cold, tumble dry low.",
    "label_sections": [
        {"head": "CARE", "body": "Machine wash cold, inside out. Tumble dry low. "
                                 "Do not iron the print."},
        {"head": "FIT", "body": "Unisex adult large. Pre-shrunk; expect under 3% shrink."},
    ],
    "about": "Printed in small runs. Colours may vary slightly between batches.",
    "company": "PRINTED FOR T2 HOLDINGS LLC",
    "lot_code": "LOT  MT-0000",
    "best_by": "STYLE  MT-0000",
    "barcode_digits": "8 50000 00000 8",
    "draft_note": "DRAFT  ·  VERIFY BEFORE PRINT",
    "back_draft_note": "DRAFT  ·  VERIFY CARE COPY BEFORE PRINT",
    "status": "DRAFT - copy and care instructions must be verified before print",
    "claims": {"organic_seal": False, "fda": False,
               "note": "no certification is claimed that the brand has not got"},
}

_DESIGN_IDS = {
    "mogra-lions-mane": "mogra-lions-mane",
    "mogra_lions_mane": "mogra-lions-mane",
    "mogra": "mogra-lions-mane",
    "word-coffee": "word-coffee",
    "word_coffee": "word-coffee",
    "word-coffee-canister": "word-coffee-canister",
    "word-coffee-mug": "word-coffee-mug",
    "harbor-body-oil": "harbor-body-oil",
    "pine-paws-joint": "pine-paws-joint",
    "mogra-tee": "mogra-tee",
}

#: Seller brief `product_line` -> design id. Explicit: a brief that names a line
#: nobody has designed raises, and never silently renders a different brand.
_PRODUCT_LINES = {
    "lions-mane": "mogra-lions-mane",
    "mogra-lions-mane": "mogra-lions-mane",
    "mogra": "mogra-lions-mane",
    "word-coffee": "word-coffee",
    "word_coffee": "word-coffee",
    "word-coffee-canister": "word-coffee-canister",
    "word_coffee_canister": "word-coffee-canister",
    "word-coffee-mug": "word-coffee-mug",
    "harbor-body-oil": "harbor-body-oil",
    "pine-paws-joint": "pine-paws-joint",
    "mogra-tee": "mogra-tee",
    "mogra_tee": "mogra-tee",
}


def known() -> List[str]:
    """The design ids this app can actually print."""
    return sorted({v for v in _DESIGN_IDS.values()})


#: The designs that live in this module as data (rather than in
#: `mogra_label_art`, whose pouch artwork is shipped and byte-locked).
_LOCAL_DESIGNS: Dict[str, Dict[str, Any]] = {
    "word-coffee": WORD_COFFEE,
    "word-coffee-canister": WORD_COFFEE_CANISTER,
    "word-coffee-mug": WORD_COFFEE_MUG,
    "harbor-body-oil": HARBOR_BODY_OIL,
    "pine-paws-joint": PINE_PAWS_JOINT,
    "mogra-tee": MOGRA_TEE,
}


def design_for(product: str = "mogra-lions-mane") -> Dict[str, Any]:
    """A copy of the declared design; callers may edit it without side effects."""
    key = _DESIGN_IDS.get(str(product or "").strip().lower())
    if key is None:
        raise ValueError(
            f"unknown label design {product!r}; known designs: {', '.join(known())}")
    if key in _LOCAL_DESIGNS:
        return copy.deepcopy(_LOCAL_DESIGNS[key])
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
    if form_of(design) == CYLINDER:
        # A cylinder with no declared label is refused rather than given a
        # made-up circumference: the wrap width IS the physical measurement.
        raise ValueError(
            f"design {design.get('id') or design.get('brand')!r} declares no "
            "face_mm; a cylinder label must declare its visible-half width and height")
    w, h = mogra_label_art.BASE_SIZE
    return (w / mogra_label_art.DPI * 25.4, h / mogra_label_art.DPI * 25.4)


def plate_kind(design: Dict[str, Any]) -> str:
    """The blank body a drawn plate must draw for this design's form."""
    return PLATE_KINDS[form_of(design)]


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
    if form_of(dsn) in (CYLINDER, APPAREL):
        # An apparel print is a flat panel on a garment, the same artwork problem as a
        # cylinder label: no carton panels to fill, so the label renderer draws it.
        img = package_art.render_front_label(_spec(dsn), width_mm=width_mm,
                                             height_mm=height_mm)
    else:
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
    if form_of(dsn) in (CYLINDER, APPAREL):
        img = package_art.render_back_label(_spec(dsn), width_mm=width_mm,
                                            height_mm=height_mm)
    else:
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


__all__ = ["POUCH", "GIFT_BOX", "CYLINDER", "FORM_NAMES", "PLATE_KINDS",
           "WORD_COFFEE", "WORD_COFFEE_CANISTER", "WORD_COFFEE_MUG", "HARBOR_BODY_OIL",
           "PINE_PAWS_JOINT", "known",
           "design_for", "design_for_brief", "form_of", "face_mm", "plate_kind",
           "front_panel", "back_panel", "panels", "manifest"]
