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
import math
import re
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageFont

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
    # A pale-pink carton with a cream panel and a lilac accent: the Word Coffee
    # gift-box family. Ink is a deep plum so the type stays legible on the pale
    # ground at print size.
    "blush": {"ground": (243, 226, 226), "ink": (58, 40, 62),
              "accent": (150, 116, 178), "muted": (122, 96, 118),
              "band": (250, 244, 236)},
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


# ── the folding-carton form ──────────────────────────────────────────────────
#
# A gift box is not a stand-up pouch: there is no weld, no gusset, and no
# Supplement Facts panel. It needs its own composition — a script line where a
# pouch puts a product name, a tagline, and a cream band carrying the net weight.
# The two renderers below are the box form; `render_front` stays the bag form and
# is not modified, so the shipped Mogra artwork cannot change by accident.

_SCRIPT_FONTS = (
    Path(r"C:\Windows\Fonts\segoesc.ttf"),
    Path(r"C:\Windows\Fonts\PALSCRI.TTF"),
)


def _script_font(size_mm: float):
    """A script face for the display line; the repo's italic serif if absent."""
    px = max(10, pd.P(size_mm))
    for path in _SCRIPT_FONTS:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), px)
            except Exception:  # noqa: BLE001 - a missing face is not a failure
                continue
    return pd.F("CormorantGaramond-Italic.ttf", size_mm)


def _wrap_lines(d: ImageDraw.ImageDraw, text: str, font, max_w_mm: float) -> list:
    limit = pd.P(max_w_mm)
    lines: list = []
    current = ""
    for word in str(text or "").split():
        trial = f"{current} {word}".strip()
        if d.textlength(trial, font=font) <= limit or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_script(d: ImageDraw.ImageDraw, text: str, *, size_mm: float,
                max_w_mm: float) -> object:
    """Shrink a script line until it fits the safe area, never below 9 mm."""
    size = size_mm
    while size > 9.0:
        font = _script_font(size)
        if d.textlength(text, font=font) <= pd.P(max_w_mm):
            return font
        size -= 0.8
    return _script_font(9.0)


def _bean(d: ImageDraw.ImageDraw, cx_mm: float, cy_mm: float, w_mm: float,
          h_mm: float, color, width_mm: float = 0.45) -> None:
    """A drawn coffee bean: an oval with the centre crease. Original geometry."""
    x0, y0 = pd.P(cx_mm - w_mm / 2), pd.P(cy_mm - h_mm / 2)
    x1, y1 = pd.P(cx_mm + w_mm / 2), pd.P(cy_mm + h_mm / 2)
    w = max(2, pd.P(width_mm))
    d.ellipse([x0, y0, x1, y1], outline=tuple(color), width=w)
    # crease: a shallow S through the long axis, drawn as short segments
    steps = 18
    pts = []
    for i in range(steps + 1):
        t = i / steps
        yy = y0 + (y1 - y0) * t
        xx = pd.P(cx_mm) + int(pd.P(w_mm) * 0.20 * math.sin(t * math.pi))
        pts.append((xx, yy))
    d.line(pts, fill=tuple(color), width=w)


def render_front_box(spec: Dict[str, Any], *, logo: Optional[Image.Image] = None,
                     width_mm: float = 100.0, height_mm: float = 200.0) -> Image.Image:
    """Front of a folding carton: brand, script line, tagline, weight band."""
    W, H = float(width_mm), float(height_mm)
    theme = _theme(spec)
    ink, accent, muted = theme["ink"], theme["accent"], theme["muted"]
    band = theme.get("band", (250, 244, 236))

    img = Image.new("RGB", (pd.P(W), pd.P(H)), theme["ground"])
    d = ImageDraw.Draw(img)

    inset = max(4.0, min(8.0, W * 0.06))
    pd.frame(d, W, H, accent, inset_mm=inset, width_mm=0.55,
             inset2_mm=inset + max(0.8, W * 0.012))
    safe_w = W - 2 * inset - 6

    brand = str(spec.get("brand") or spec.get("company") or "NORTHSTAR").strip()
    if logo is not None:
        _paste_logo(img, logo, W, H * 0.085,
                    max_w=min(42.0, W * 0.62), max_h=min(16.0, H * 0.07))
    else:
        # Tracking on a wordmark is decoration; too much of it and OCR reads the
        # brand as two unrelated words, which fails the picture's own gate.
        pd.ctext(d, W / 2, H * 0.085, brand.upper(),
                 pd.F("Inter.ttf", max(2.6, W * 0.048), [14, 700]), ink,
                 tracking_mm=max(0.5, W * 0.010))
    pd.rule(d, W / 2 - W * 0.22, H * 0.125, W / 2 + W * 0.22, accent, 0.35)

    script_line = str(spec.get("script_line") or "").strip()
    if script_line:
        f_script = _fit_script(d, script_line, size_mm=H * 0.115, max_w_mm=safe_w)
        pd.ctext(d, W / 2, H * 0.245, script_line, f_script, accent)

    title = str(spec.get("title") or "").strip()
    y = H * 0.335
    if title and not script_line:
        f_title = pd.fit_size("PlayfairDisplay.ttf", max(3.6, H * 0.058), [700],
                              title.upper(), safe_w)
        pd.ctext(d, W / 2, y, title.upper(), f_title, ink)
        y += H * 0.055
    subtitle = str(spec.get("subtitle") or "").strip()
    if subtitle:
        pd.ctext(d, W / 2, y, subtitle.upper(),
                 pd.F("Inter.ttf", max(2.0, H * 0.019), [14, 650]), ink,
                 tracking_mm=max(0.6, W * 0.012))
        y += H * 0.040

    tagline = str(spec.get("tagline") or "").strip()
    if tagline:
        f_tag = pd.F("CormorantGaramond-Italic.ttf", max(2.4, H * 0.024))
        lines = _wrap_lines(d, tagline, f_tag, safe_w - 6)
        ty = y + H * 0.012
        for line in lines[:3]:
            pd.ctext(d, W / 2, ty, line, f_tag, muted)
            ty += H * 0.032

    # motif: three beans in a row, contained by the safe width
    if str(spec.get("motif") or "bean") == "bean":
        span = min(34.0, safe_w * 0.55)
        for i in (-1, 0, 1):
            _bean(d, W / 2 + i * span / 2.4, H * 0.615,
                  w_mm=max(7.0, W * 0.085), h_mm=max(11.0, W * 0.13),
                  color=accent, width_mm=0.4)

    # cream band: the legal weight line, high contrast, one string
    band_top, band_bottom = H * 0.735, H * 0.865
    d.rectangle([pd.P(inset + 1.5), pd.P(band_top), pd.P(W - inset - 1.5), pd.P(band_bottom)],
                fill=tuple(band))
    weight_line = str(spec.get("net_weight_line") or spec.get("weight") or "").strip()
    band_ink = (58, 40, 62) if sum(band) / 3 > 120 else ink
    if weight_line:
        # No letter-spacing on the legal weight line: tracking opens gaps between
        # glyphs and OCR then reads "NET WT.120" and "G" as separate runs.
        pd.ctext(d, W / 2, band_top + (band_bottom - band_top) * 0.42,
                 weight_line.upper(),
                 pd.F("Inter.ttf", max(2.6, H * 0.026), [14, 700]), band_ink)
    descriptor = str(spec.get("descriptor") or "").strip()
    if descriptor:
        pd.ctext(d, W / 2, band_top + (band_bottom - band_top) * 0.78,
                 descriptor.upper(),
                 pd.F("Inter.ttf", max(1.7, H * 0.014), [14, 500]), band_ink,
                 tracking_mm=max(0.5, W * 0.010))

    draft = str(spec.get("draft_note") or "").strip()
    if draft:
        pd.ctext(d, W / 2, H * 0.945, draft.upper(),
                 pd.F("Inter.ttf", max(1.6, H * 0.0115)), muted, tracking_mm=0.8)

    return pd.apply_paper(img, seed=_seed(spec))


def render_back_box(spec: Dict[str, Any], *, logo: Optional[Image.Image] = None,
                    width_mm: float = 100.0, height_mm: float = 200.0) -> Image.Image:
    """Back of a folding carton: what is inside, ingredients, brew, codes, UPC.

    No Supplement Facts block: this form is not a dietary supplement, and a
    printed supplement panel on a coffee box would be a false label.
    """
    W, H = float(width_mm), float(height_mm)
    theme = _theme(spec)
    ink, accent, muted = theme["ink"], theme["accent"], theme["muted"]

    img = Image.new("RGB", (pd.P(W), pd.P(H)), theme["ground"])
    d = ImageDraw.Draw(img)

    inset = max(4.0, min(8.0, W * 0.06))
    pd.frame(d, W, H, accent, inset_mm=inset, width_mm=0.55)
    tx = inset + 4
    right = W - inset - 4
    col_w = right - tx

    brand = str(spec.get("brand") or spec.get("company") or "NORTHSTAR").strip()
    pd.ctext(d, W / 2, H * 0.065, brand.upper(),
             pd.F("Inter.ttf", max(2.6, W * 0.045), [14, 700]), ink,
             tracking_mm=max(1.2, W * 0.022))
    pd.rule(d, tx, H * 0.095, right, accent, 0.4)

    # The net weight is part of the legal panel, and it appears on the back too,
    # so a rear product picture can be checked for it (the same reason the pouch
    # back carries it).
    weight_line = str(spec.get("net_weight_line") or spec.get("weight") or "").strip()
    if weight_line:
        pd.ctext(d, W / 2, H * 0.111, weight_line.upper(),
                 pd.F("Inter.ttf", max(2.2, H * 0.016), [14, 700]), ink,
                 tracking_mm=max(0.5, W * 0.008))

    f_head = pd.F("Inter.ttf", max(2.2, H * 0.0155), [14, 700])
    f_body = pd.F("Inter.ttf", max(2.0, H * 0.0135), [14, 400])
    f_small = pd.F("Inter.ttf", max(1.7, H * 0.0115), [14, 400])

    y = H * 0.132
    pd.ltext(d, tx, y, "WHAT'S INSIDE", f_head, accent)
    y += H * 0.022
    for line in _wrap_lines(d, str(spec.get("inside") or spec.get("tagline") or ""),
                            f_body, col_w):
        pd.ltext(d, tx, y, line, f_body, ink)
        y += H * 0.019

    y += H * 0.012
    pd.ltext(d, tx, y, "INGREDIENTS", f_head, accent)
    y += H * 0.022
    for line in _wrap_lines(d, str(spec.get("ingredients") or ""), f_body, col_w):
        pd.ltext(d, tx, y, line, f_body, ink)
        y += H * 0.019

    y += H * 0.012
    pd.ltext(d, tx, y, "ROAST", f_head, accent)
    y += H * 0.022
    pd.ltext(d, tx, y, str(spec.get("roast") or ""), f_body, ink)
    y += H * 0.021

    y += H * 0.014
    pd.ltext(d, tx, y, "HOW TO BREW", f_head, accent)
    y += H * 0.022
    for step in (spec.get("brew") or []):
        for line in _wrap_lines(d, str(step), f_body, col_w):
            pd.ltext(d, tx, y, line, f_body, ink)
            y += H * 0.019
        y += H * 0.004

    y += H * 0.010
    pd.rule(d, tx, y, right, accent, 0.28)
    y += H * 0.014
    for line in _wrap_lines(d, str(spec.get("about") or ""), f_small, col_w):
        pd.ltext(d, tx, y, line, f_small, muted)
        y += H * 0.017

    # codes: lot + best-by on the left, a drawn UPC on the right
    sv = str(spec.get("servings") or "").strip()
    if sv:
        pd.ltext(d, tx, H * 0.845, sv.upper(), f_small, ink)

    box_top = H * 0.862
    d.rectangle([pd.P(tx), pd.P(box_top), pd.P(tx + col_w * 0.42), pd.P(box_top + H * 0.045)],
                outline=tuple(muted), width=2)
    pd.ltext(d, tx + 1.6, box_top + H * 0.013, str(spec.get("lot_code") or ""), f_small, ink)
    pd.ltext(d, tx + 1.6, box_top + H * 0.030, str(spec.get("best_by") or ""), f_small, ink)

    digits = re.sub(r"\D", "", str(spec.get("barcode_digits") or ""))
    if len(digits) >= 11:
        digits = (digits + "000000000000")[:12]
        uw = col_w * 0.52
        pd.draw_upc(d, right - uw, box_top + H * 0.004, uw, H * 0.038, digits)

    rep = str(spec.get("company") or "").strip()
    if rep:
        pd.ctext(d, W / 2, H * 0.925, rep.upper(), f_small, muted, tracking_mm=0.6)
    draft = str(spec.get("back_draft_note") or spec.get("draft_note") or "").strip()
    if draft:
        pd.ctext(d, W / 2, H * 0.952, draft.upper(), f_small, muted, tracking_mm=0.6)

    return pd.apply_paper(img, seed=_seed(spec) + 1)


__all__ = ["THEMES", "themes", "render_front", "render_front_box", "render_back_box"]
