"""Northstar image/text workflow — presets.

Single source of truth for the reusable *scene -> text-safe zone -> exact text*
workflow. Any Northstar service can import these presets (containers, products,
surface zones, label styles) instead of hard-coding coordinates or brand copy.

Design rules encoded here (see docs/NORTHSTAR_IMAGE_TEXT_WORKFLOW.md):

* The AI image lane produces the *scene only* — clean, label-free product faces.
* Final text is applied deterministically by ``creative.exact_text``.
* Brand copy is exact and never invented by a model.

Coordinate system
-----------------
A "quad" is four normalized ``[x, y]`` points in reading order:

    ul (top-left)  ->  ur (top-right)  ->  lr (bottom-right)  ->  ll (bottom-left)

Values are ``0.0 .. 1.0`` of the target image width/height, so a preset is
resolution-independent. Curvature (``0.0 .. 0.5``) fakes a cylindrical barrel
bulge for jars; it defaults to ``0`` (flat).
"""

from __future__ import annotations

from typing import Any, Dict, List

SCHEMA = "northstar-image-text-presets-v1"

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------

MOGRA_BRAND: Dict[str, Any] = {
    "key": "mogra_organics",
    "name": "Mogra Organics",          # must always be exactly this
    "tagline": "Fuel Your Focus.",     # default tagline
    "palette": {
        "panel": [246, 242, 233, 255],  # bone / paper
        "ink": [26, 44, 34, 255],       # pine forest ink
        "accent": [31, 94, 63, 255],    # deep pine
        "muted": [98, 112, 101, 255],
    },
    "rules": [
        "Brand name is always exactly 'Mogra Organics'.",
        "Default tagline is 'Fuel Your Focus.'.",
        "No sun, sunrise, sunburst, or celestial mark.",
        "Premium, polished, realistic container style.",
        "Never invent certification seals, nutrition facts, UPCs, lot codes, "
        "supplier names, legal claims, or compliance statements.",
    ],
}

# Tokens that would fabricate regulated / compliance content. ``exact_text``
# refuses these in Mogra brand mode so the workflow can never invent them.
FORBIDDEN_CONTENT_TOKENS: List[str] = [
    "usda", "certified organic seal", "nutrition facts", "supplement facts",
    "upc", "gtin", "lot code", "lot no", "lot #", "batch #", "best by",
    "expiration", "expiry", "fda", "non-gmo project verified",
    "supplier:", "manufactured by", "distributed by",
]

# ---------------------------------------------------------------------------
# Container presets (physical formats)
# ---------------------------------------------------------------------------

CONTAINER_PRESETS: Dict[str, Dict[str, Any]] = {
    "mogra_5lb_clear_handled_pet_jar": {
        "label": "5 lb clear handled PET jar",
        "scene_prompt": (
            "A premium clear handled PET spice jar, five pound size, empty label "
            "panel left clean and blank, brushed pine-green lid, studio product "
            "photography, soft diffused light, subtle reflection, bone-colored "
            "seamless background, photorealistic, high detail, no text, no logos, "
            "no labels, no icons"
        ),
        "quad_norm": [[0.33, 0.24], [0.67, 0.24], [0.67, 0.60], [0.33, 0.60]],
        "curvature": 0.06,
        "default_style": "mogra_label_panel",
    },
    "mogra_32oz_standup_pouch": {
        "label": "32 oz stand-up pouch",
        "scene_prompt": (
            "A premium matte stand-up pouch, thirty-two ounce spice format, front "
            "label area left clean and blank, kraft and pine-green accents, studio "
            "product photography, soft diffused light, bone-colored seamless "
            "background, photorealistic, high detail, no text, no logos, no labels, "
            "no icons"
        ),
        "quad_norm": [[0.30, 0.24], [0.70, 0.22], [0.72, 0.72], [0.28, 0.74]],
        "curvature": 0.0,
        "default_style": "mogra_label_panel",
    },
    "mogra_4oz_window_pouch": {
        "label": "4 oz window pouch",
        "scene_prompt": (
            "A small premium four ounce window pouch, clear window showing the "
            "spice, front label area left clean and blank, matte finish, studio "
            "product photography, soft diffused light, bone-colored seamless "
            "background, photorealistic, high detail, no text, no logos, no "
            "labels, no icons"
        ),
        "quad_norm": [[0.30, 0.20], [0.70, 0.19], [0.72, 0.60], [0.28, 0.62]],
        "curvature": 0.0,
        "default_style": "mogra_label_panel",
    },
}

# ---------------------------------------------------------------------------
# Product presets (Mogra Organics)
# ---------------------------------------------------------------------------

_5LB = "NET WT. 5 LB (2.27 kg)"

PRODUCT_PRESETS: Dict[str, Dict[str, Any]] = {
    "organic_black_peppercorns": {
        "label": "Organic Black Peppercorns",
        "brand": "Mogra Organics",
        "tagline": "Fuel Your Focus.",
        "product_name": "Organic Black Peppercorns",
        "descriptor": "Whole \u2022 Aromatic \u2022 Bold",
        "net_weight": _5LB,
        "scene_words": "whole black peppercorns, dark peppercorn texture",
    },
    "organic_white_onion_powder": {
        "label": "Organic White Onion Powder",
        "brand": "Mogra Organics",
        "tagline": "Fuel Your Focus.",
        "product_name": "Organic White Onion Powder",
        "descriptor": "Smooth \u2022 Savory \u2022 Versatile",
        "net_weight": _5LB,
        "scene_words": "fine white onion powder, soft cream powder texture",
    },
    "organic_turmeric_powder": {
        "label": "Organic Turmeric Powder",
        "brand": "Mogra Organics",
        "tagline": "Fuel Your Focus.",
        "product_name": "Organic Turmeric Powder",
        "descriptor": "Earthy \u2022 Golden \u2022 Vibrant",
        "net_weight": _5LB,
        "scene_words": "golden turmeric powder, warm golden powder texture",
    },
}

# ---------------------------------------------------------------------------
# Surface presets — reusable text-safe zones for ANY Northstar service
# ---------------------------------------------------------------------------

SURFACE_PRESETS: Dict[str, Dict[str, Any]] = {
    "front_label_panel": {
        "label": "Front packaging label panel",
        "description": "Centred front label zone on a container or pouch.",
        "quad_norm": [[0.30, 0.22], [0.70, 0.22], [0.70, 0.70], [0.30, 0.70]],
        "curvature": 0.0,
        "style": "mogra_label_panel",
    },
    "plain_rectangle": {
        "label": "Plain rectangle text overlay",
        "description": "Flat full-frame rectangle for any exact text.",
        "quad_norm": [[0.06, 0.06], [0.94, 0.06], [0.94, 0.94], [0.06, 0.94]],
        "curvature": 0.0,
        "style": "plain_ink",
    },
    "angled_product_face": {
        "label": "Angled product face (quad)",
        "description": "Perspective face for jars, pouches, or skewed products.",
        "quad_norm": [[0.30, 0.20], [0.70, 0.15], [0.75, 0.68], [0.25, 0.73]],
        "curvature": 0.05,
        "style": "mogra_label_panel",
    },
    "card_banner_hero": {
        "label": "Card / banner / hero overlay",
        "description": "Wide band for headline copy on banners and hero art.",
        "quad_norm": [[0.08, 0.30], [0.92, 0.30], [0.92, 0.74], [0.08, 0.74]],
        "curvature": 0.0,
        "style": "hero_card",
    },
    "ui_screenshot_annotation": {
        "label": "UI screenshot annotation",
        "description": "Small caption bar for annotating UI screenshots.",
        "quad_norm": [[0.05, 0.08], [0.62, 0.08], [0.62, 0.20], [0.05, 0.20]],
        "curvature": 0.0,
        "style": "ui_annotation",
    },
}

# ---------------------------------------------------------------------------
# Label styles
# ---------------------------------------------------------------------------

STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "mogra_label_panel": {
        "label": "Mogra label panel (bone / pine)",
        "panel": [246, 242, 233, 255],
        "ink": [26, 44, 34, 255],
        "accent": [31, 94, 63, 255],
        "muted": [98, 112, 101, 255],
        "serif": True,
        "radius_frac": 0.05,
        "padding_frac": 0.11,
        "border_frac": 0.010,
        "shadow": True,
    },
    "mogra_text_only": {
        "label": "Mogra text only (transparent)",
        "panel": None,
        "ink": [26, 44, 34, 255],
        "accent": [31, 94, 63, 255],
        "muted": [60, 74, 64, 255],
        "serif": True,
        "radius_frac": 0.0,
        "padding_frac": 0.06,
        "border_frac": 0.0,
        "shadow": True,
    },
    "plain_ink": {
        "label": "Plain dark text (transparent)",
        "panel": None,
        "ink": [18, 18, 18, 255],
        "accent": [18, 18, 18, 255],
        "muted": [70, 70, 70, 255],
        "serif": False,
        "radius_frac": 0.0,
        "padding_frac": 0.05,
        "border_frac": 0.0,
        "shadow": False,
    },
    "hero_card": {
        "label": "Hero card (dark glass)",
        "panel": [16, 20, 24, 214],
        "ink": [255, 255, 255, 255],
        "accent": [122, 200, 255, 255],
        "muted": [188, 198, 208, 255],
        "serif": True,
        "radius_frac": 0.06,
        "padding_frac": 0.10,
        "border_frac": 0.006,
        "shadow": True,
    },
    "ui_annotation": {
        "label": "UI annotation bar",
        "panel": [20, 24, 28, 232],
        "ink": [236, 240, 245, 255],
        "accent": [122, 180, 255, 255],
        "muted": [170, 180, 190, 255],
        "serif": False,
        "radius_frac": 0.10,
        "padding_frac": 0.08,
        "border_frac": 0.0,
        "shadow": False,
    },
}


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------

def get_container(key: str) -> Dict[str, Any]:
    if key not in CONTAINER_PRESETS:
        raise KeyError(f"unknown container preset: {key}")
    return CONTAINER_PRESETS[key]


def get_product(key: str) -> Dict[str, Any]:
    if key not in PRODUCT_PRESETS:
        raise KeyError(f"unknown product preset: {key}")
    return PRODUCT_PRESETS[key]


def get_surface(key: str) -> Dict[str, Any]:
    if key not in SURFACE_PRESETS:
        raise KeyError(f"unknown surface preset: {key}")
    return SURFACE_PRESETS[key]


def get_style(key: str) -> Dict[str, Any]:
    if key not in STYLE_PRESETS:
        raise KeyError(f"unknown style preset: {key}")
    return dict(STYLE_PRESETS[key])


def catalog() -> Dict[str, Any]:
    """Everything the UI needs in one payload."""
    return {
        "schema": SCHEMA,
        "brand": MOGRA_BRAND,
        "containers": CONTAINER_PRESETS,
        "products": PRODUCT_PRESETS,
        "surfaces": SURFACE_PRESETS,
        "styles": STYLE_PRESETS,
    }
