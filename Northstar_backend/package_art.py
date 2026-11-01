"""Dynamic package-front design system.

`package_designs.py` holds a large Mogra-specific design catalogue. This module
adds the missing generic layer: it renders a designed front panel from the
product's own copy, logo and motif using the same print primitives (300 dpi,
mm-true layout, paper grain, drawn certification icons), so a non-Mogra SKU is
not forced into hard-coded copy.

The renderer is deterministic and offline. It never invents a certification:
an organic seal appears only when the caller sets ``organic_certified``.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw

import package_designs as pd

# Palette name -> ground / ink / accent / secondary. All are print-safe solids.
THEMES: Dict[str, Dict[str, Any]] = {
    "forest": {"ground": pd.FOREST, "ink": pd.CREAM, "accent": pd.GOLD_A,
               "muted": (176, 196, 174)},
    "midnight": {"ground": pd.INK, "ink": pd.CREAM, "accent": pd.GOLD_A,
                 "muted": (193, 187, 173)},
    "kraft": {"ground": pd.KRAFT, "ink": pd.INK, "accent": pd.FOREST,
              "muted": (92, 78, 60)},
    "bone": {"ground": pd.BONE, "ink": pd.FOREST2, "accent": pd.TERRA,
             "muted": (112, 102, 90)},
    "clay": {"ground": pd.CLAY, "ink": pd.BONE, "accent": pd.GOLD_A,
             "muted": (244, 222, 204)},
    "sage": {"ground": pd.SAGE3, "ink": pd.FOREST3, "accent": pd.OCHRE,
             "muted": (74, 88, 66)},
    "slate": {"ground": pd.SLATE3, "ink": pd.PARCHMENT, "accent": pd.GOLD_A,
              "muted": (200, 205, 208)},
}


def themes() -> list:
    return sorted(THEMES)


def _theme(spec: Dict[str, Any]) -> Dict[str, Any]:
    key = str(spec.get("theme") or "forest").strip().lower()
    return THEMES.get(key, THEMES["forest"])


def _seed(spec: Dict[str, Any]) -> int:
    raw = "|".join(str(spec.get(k) or "") for k in
                   ("title", "subtitle", "weight", "theme", "brand"))
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16) % 9001


def _wrap_title(title: str, limit: int = 18) -> list:
    """Split a product name into at most three balanced display lines."""
    words = [w for w in re.split(r"\s+", str(title or "").strip()) if w]
    if not words:
        return ["YOUR PRODUCT"]
    lines: list = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= limit or not lines and len(current) < 9:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    if len(lines) > 3:
        lines = [" ".join(lines[:2]), " ".join(lines[2:])]
    return lines


def _facts(spec: Dict[str, Any]) -> list:
    weight = str(spec.get("weight") or "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(oz|g|grams?|ml|lb)\b", weight, re.I)
    if not match:
        return [(weight or "NET WT", "NET WT")]
    amount = f"{match.group(1)} {match.group(2).upper()}"
    cells = [(amount, "NET WT")]
    grams = re.search(r"\((\d+(?:\.\d+)?)\s*g\)", weight, re.I)
    if grams:
        cells.append((f"{grams.group(1)} g", "WEIGHT"))
    servings = str(spec.get("servings") or "").strip()
    if servings:
        cells.append((servings, "SERVINGS"))
    return cells[:3]


def _paste_logo(canvas: Image.Image, logo: Optional[Image.Image], W: float, y: float,
                max_w: float = 34.0, max_h: float = 18.0) -> bool:
    if logo is None:
        return False
    width = int(pd.P(max_w))
    height = max(2, int(width * logo.height / max(1, logo.width)))
    if height > pd.P(max_h):
        height = pd.P(max_h)
        width = max(2, int(height * logo.width / max(1, logo.height)))
    art = logo.resize((width, height), Image.LANCZOS)
    canvas.paste(art, (int(pd.P(W / 2) - width / 2), int(pd.P(y) - height / 2)), art)
    return True


def _motif(canvas: Image.Image, motif: Optional[Image.Image], theme: Dict[str, Any],
           W: float, y: float, max_w: float, max_h: float) -> None:
    if motif is not None:
        try:
            tinted = pd.recolor(motif, theme["accent"])
        except Exception:  # noqa: BLE001 - a plain motif is still usable
            tinted = motif
        pd.place_motif(canvas, tinted, W / 2, y, max_w, max_h)
        return
    # Drawn fallback: a restrained botanical sprig, never a fake photo.
    d = ImageDraw.Draw(canvas)
    pd._sprig(d, W / 2, y, 24.0, theme["accent"], max(2, pd.P(0.45)))


def render_front(spec: Dict[str, Any], *, logo: Optional[Image.Image] = None,
                 motif: Optional[Image.Image] = None,
                 width_mm: float = 130.0, height_mm: float = 210.0) -> Image.Image:
    """Render a front-of-pack design at 300 dpi, laid out for the actual face.

    The layout is proportional rather than a fixed bag template: a 40x124 mm
    tube label and an 80x180 mm carton face both get a balanced composition,
    not a squashed bag design.
    """
    W, H = float(width_mm), float(height_mm)
    theme = _theme(spec)
    img = Image.new("RGB", (pd.P(W), pd.P(H)), theme["ground"])
    d = ImageDraw.Draw(img)
    accent, ink, muted = theme["accent"], theme["ink"], theme["muted"]
    brand = str(spec.get("brand") or spec.get("company") or "NORTHSTAR").strip()
    title = str(spec.get("title") or "").strip() or "YOUR PRODUCT"
    subtitle = str(spec.get("subtitle") or "").strip()
    claims = [str(c) for c in (spec.get("claims") or []) if str(c).strip()][:3]
    narrow = W < 62.0

    # frame: scale down on a narrow label so it never eats the safe area
    inset = max(2.2, min(5.2, W * 0.055))
    inner = inset + max(1.0, min(2.0, W * 0.018))
    pd.frame(d, W, H, accent, inset_mm=inset, width_mm=max(0.35, min(0.7, W / 180)),
             inset2_mm=inner if W > 52 else None)

    # brand block at ~8% height; the supplied logo always wins over drawn text
    brand_y = H * 0.085
    if not _paste_logo(img, logo, W, brand_y,
                       max_w=min(34.0, W * 0.55),
                       max_h=min(18.0, H * 0.10)):
        pd.ctext(d, W / 2, brand_y, brand.upper(),
                 pd.F("Inter.ttf", max(1.55, H * 0.016), [14, 700]),
                 ink, tracking_mm=max(1.0, min(2.6, W * 0.03)))

    # organic seal is a claim; only draw when the caller says it is certified
    seal_r = max(2.5, min(8.2, W * 0.085))
    if spec.get("organic_certified"):
        pd.organic_seal(img, W - inset - seal_r, H * 0.19, seal_r)

    # product name, sized to the face and balanced over at most three lines
    lines = _wrap_title(title, limit=max(9, int(W / 6.8)))
    f_title = pd.fit_size("PlayfairDisplay.ttf", max(3.6, H * 0.063), [700],
                          max(lines, key=len), W - 2 * inset - 6)
    title_top = H * 0.245
    line_gap = H * 0.069
    y = title_top
    for line in lines[:3]:
        pd.ctext(d, W / 2, y, line, f_title, ink)
        y += line_gap
    if subtitle:
        sub_text = subtitle.upper()
        # Tracking is beautiful on a broad carton face and unreadable on a
        # 40 mm tube; disable it below a real label width.
        sub_track = 0.0 if W < 62 else max(0.25, min(1.6, W * 0.009))
        # fit_size measures the glyphs only; reserve the tracking advance too
        # or a tracked subtitle overflows the artwork on narrow faces.
        max_sub = (W - 2 * inset - 4
                   - sub_track * max(0, len(sub_text) - 1))
        f_sub = pd.fit_size("Inter.ttf", max(1.2, H * 0.0155), [14, 680],
                            sub_text, max(8.0, max_sub))
        pd.ctext(d, W / 2, y + H * 0.006, sub_text, f_sub, accent,
                 tracking_mm=sub_track)
        y += H * 0.032

    pd.rule(d, W / 2 - W * 0.17, y + H * 0.012,
            W / 2 + W * 0.17, accent, max(0.2, min(0.5, W / 260)))

    # hero motif, contained by the available width
    _motif(img, motif, theme, W, H * 0.59,
           max(10.0, min(62.0, W - 2 * inset - 8)),
           max(8.0, min(58.0, H * 0.27)))

    # claim stack (tight labels get fewer lines)
    display_claims = claims[:1] if H < 105 else claims
    if display_claims:
        f_claim = pd.F("Inter.ttf", max(1.25, H * 0.0122), [14, 540])
        cy = H * 0.755
        for claim in display_claims:
            pd.ctext(d, W / 2, cy, claim, f_claim, muted if narrow else ink)
            cy += H * 0.027

    # certification icons (only the ones supplied)
    icons = [str(i) for i in (spec.get("icons") or [])
             if i in ("organic_sprout", "non_gmo", "gluten_free",
                      "fruiting_body", "vegan", "paleo")]
    if icons and not narrow:
        from mockup_compositor import draw_cert_icon
        r_px = pd.P(max(1.2, H * 0.0145))
        gap_px = pd.P(max(4.5, H * 0.048))
        iy = pd.P(H * 0.865)
        for i, kind in enumerate(icons[:3]):
            cx = pd.P(W / 2) + (i - (len(icons) - 1) / 2.0) * gap_px
            draw_cert_icon(d, kind, cx, iy, r_px, ink=accent, ring=accent,
                           disc=theme["ground"], width=max(2, pd.P(0.3)))

    # bulk-supplement style net-weight capsule
    cells = _facts(spec)
    if len(cells) == 1:
        pd.ctext(d, W / 2, H - H * 0.07, cells[0][0],
                 pd.F("Inter.ttf", max(1.4, H * 0.0145), [14, 650]), ink)
    else:
        pd.value_capsule(img, W, W / 2, H - H * 0.075, W - 2 * inset - 4,
                         max(5.5, H * 0.062), cells,
                         bg=accent, fg=theme["ground"], sep=theme["ground"])

    # Keep the bottom edge for the net-weight capsule. An extra brand line here
    # collided with the capsule on short faces; the logo/brand at the top and
    # the capsule carry the identity without crowding the trim.

    return pd.apply_paper(img, seed=_seed(spec))


__all__ = ["THEMES", "themes", "render_front"]
