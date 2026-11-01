"""Panel rendering for a complete package: front, back and side.

`pouch_label.render_label` already draws the FRONT panel (logo, product name,
subtitle, claims, certification marks, net weight). That produced a finished
front but a package is three panels plus a back-of-pack legal block, which is
exactly the gap the operator reported: "Bojo does not build a full package: no
front label, back label, side panels, or dieline logic."

This module adds the other two panels and a flat panel sheet, using only
operator-supplied facts. Nothing here invents an ingredient, a claim, an
address or a net quantity — a missing fact is rendered as an explicit
`[MISSING: field]` marker so the gap is visible in the artwork instead of being
silently filled in.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image, ImageDraw

import mockup_compositor as mc
import pouch_label as pl

FIELD = pl.FIELD
INK = pl.INK
ACCENT = pl.ACCENT

FRONT_SIZE = (900, 1200)
BACK_SIZE = (900, 1200)
SIDE_SIZE = (420, 1200)

MISSING = "[MISSING: {}]"


def _missing(name: str) -> str:
    return MISSING.format(name)


def _rule(d: ImageDraw.ImageDraw, W: int, y: int, width_frac: float = 0.30,
          accent=ACCENT) -> None:
    d.line([(W / 2 - W * width_frac / 2, y), (W / 2 + W * width_frac / 2, y)],
           fill=tuple(accent) + (255,), width=max(2, W // 400))


def _heading(d: ImageDraw.ImageDraw, W: int, y: int, text: str,
             ink=INK, size_px: Optional[int] = None) -> int:
    f = mc.load_font("Inter.ttf", size_px or int(W * 0.028), [14, 680])
    mc.centered(d, W / 2, y, text.upper(), f, tuple(ink) + (255,), tracking=W * 0.006)
    return y + int((size_px or int(W * 0.028)) * 1.9)


def _body(d: ImageDraw.ImageDraw, W: int, y: int, lines: Sequence[str],
          ink=INK, size_px: Optional[int] = None, wrap: float = 0.80) -> int:
    """Centred body text with a naive but predictable wrap (no font metrics games)."""
    size = size_px or int(W * 0.026)
    f = mc.load_font("Inter.ttf", size, [14, 420])
    max_chars = int((W * wrap) / (size * 0.52))
    for raw in lines:
        text = str(raw).strip()
        if not text:
            continue
        words, line = text.split(), ""
        for word in words:
            candidate = (line + " " + word).strip()
            if len(candidate) <= max_chars:
                line = candidate
            else:
                mc.centered(d, W / 2, y, line, f, tuple(ink) + (255,))
                y += int(size * 1.45)
                line = word
        if line:
            mc.centered(d, W / 2, y, line, f, tuple(ink) + (255,))
            y += int(size * 1.45)
    return y


def render_back_panel(*, size: Sequence[int] = BACK_SIZE,
                      title: str = "",
                      ingredients: Optional[Sequence[str]] = None,
                      supplement_facts: Optional[Sequence[str]] = None,
                      suggested_use: Optional[str] = None,
                      warnings: Optional[Sequence[str]] = None,
                      company: Optional[str] = None,
                      address: Optional[str] = None,
                      country_of_origin: Optional[str] = None,
                      lot_code: Optional[str] = None,
                      field: Sequence[int] = FIELD, ink: Sequence[int] = INK,
                      accent: Sequence[int] = ACCENT,
                      field_alpha: int = 254) -> Image.Image:
    """Back-of-pack: legal block, barcode zone and lot area.

    Anything the operator did not supply is drawn as `[MISSING: field]` — the
    artwork itself shows what is still needed instead of shipping a plausible
    invention.
    """
    W, H = int(size[0]), int(size[1])
    panel = Image.new("RGBA", (W, H), tuple(field) + (field_alpha,))
    d = ImageDraw.Draw(panel)
    ink_c = tuple(ink) + (255,)

    m = int(W * 0.055)
    d.rectangle([m, m, W - m, H - m], outline=tuple(accent) + (255,),
                width=max(2, W // 300))

    y = int(H * 0.085)
    if title:
        y = _heading(d, W, y, title, ink, int(W * 0.034))
        y += int(H * 0.012)

    if supplement_facts:
        y = _heading(d, W, y, "Supplement Facts", ink)
        y = _body(d, W, y, supplement_facts, ink, int(W * 0.023), wrap=0.78)
        y += int(H * 0.020)
    if ingredients:
        y = _heading(d, W, y, "Ingredients", ink)
        y = _body(d, W, y, ingredients, ink, int(W * 0.023), wrap=0.78)
        y += int(H * 0.020)
    if suggested_use:
        y = _heading(d, W, y, "Suggested Use", ink)
        y = _body(d, W, y, [suggested_use], ink, int(W * 0.023), wrap=0.78)
        y += int(H * 0.020)
    if warnings:
        y = _heading(d, W, y, "Warnings", ink)
        y = _body(d, W, y, warnings, ink, int(W * 0.021), wrap=0.80)
        y += int(H * 0.020)

    # ── footer block: company, origin, barcode, lot ──────────────────────────
    foot = H - int(H * 0.235)
    _rule(d, W, foot - int(H * 0.018), 0.42, accent)

    f_small = mc.load_font("Inter.ttf", int(W * 0.021), [14, 520])
    lines = [
        company or _missing("company name"),
        address or _missing("company address"),
        country_of_origin or _missing("country of origin"),
    ]
    fy = foot
    for line in lines:
        mc.centered(d, W / 2, fy, str(line), f_small, ink_c)
        fy += int(W * 0.033)

    # barcode zone is RESERVED, never drawn as a fake barcode
    bw, bh = int(W * 0.34), int(H * 0.095)
    bx, by = int((W - bw) / 2), H - int(H * 0.135)
    d.rectangle([bx, by, bx + bw, by + bh], outline=ink_c, width=2)
    mc.centered(d, W / 2, by + bh / 2 - int(W * 0.008), "BARCODE ZONE (RESERVED)",
                mc.load_font("Inter.ttf", int(W * 0.019), [14, 620]), ink_c)
    mc.centered(d, W / 2, by + bh / 2 + int(W * 0.016), "supply GTIN/UPC at print",
                mc.load_font("Inter.ttf", int(W * 0.017), [14, 420]), ink_c)

    mc.centered(d, W - int(W * 0.12), H - int(H * 0.028),
                lot_code or "LOT " + _missing("lot code"),
                mc.load_font("Inter.ttf", int(W * 0.017), [14, 420]), ink_c)
    return panel


def render_side_panel(*, size: Sequence[int] = SIDE_SIZE,
                      title: str = "", subtitle: str = "",
                      weight: str = "", claims: Optional[Sequence[str]] = None,
                      icons: Optional[Sequence[str]] = None,
                      company: Optional[str] = None,
                      field: Sequence[int] = FIELD, ink: Sequence[int] = INK,
                      accent: Sequence[int] = ACCENT,
                      field_alpha: int = 254) -> Image.Image:
    """Narrow gusset panel: brand, weight, claims, drawn certification marks."""
    W, H = int(size[0]), int(size[1])
    panel = Image.new("RGBA", (W, H), tuple(field) + (field_alpha,))
    d = ImageDraw.Draw(panel)
    ink_c = tuple(ink) + (255,)

    m = int(W * 0.09)
    d.rectangle([m, m, W - m, H - m], outline=tuple(accent) + (255,),
                width=max(2, W // 220))

    y = int(H * 0.10)
    if company:
        f = mc.load_font("Inter.ttf", int(W * 0.052), [14, 640])
        mc.centered(d, W / 2, y, company.upper(), f, ink_c, tracking=W * 0.008)
        y += int(H * 0.06)
    if title:
        f = mc.fit_font("PlayfairDisplay.ttf", int(W * 0.085), [700], title, W * 0.78, d)
        mc.centered(d, W / 2, y, title, f, ink_c)
        y += int(H * 0.055)
    if subtitle:
        f = mc.load_font("Inter.ttf", int(W * 0.040), [14, 520])
        mc.centered(d, W / 2, y, subtitle.upper(), f, ink_c, tracking=W * 0.004)
        y += int(H * 0.05)

    _rule(d, W, y, 0.62, accent)
    y += int(H * 0.05)

    if claims:
        f = mc.load_font("Inter.ttf", int(W * 0.036), [14, 500])
        for claim in list(claims)[:4]:
            mc.centered(d, W / 2, y, str(claim), f, ink_c)
            y += int(H * 0.045)

    if icons:
        kinds = [k for k in icons if k in mc._ICON_SPECS][:3]
        if kinds:
            r = int(W * 0.072)
            step = int(r * 2.5)
            # Reserve the bottom band for the net weight, then centre the icon
            # column in the space that is left. Drawing from a fixed offset made
            # the weight line collide with the last mark on a 3-icon panel.
            weight_band = int(H * 0.10)
            block = step * (len(kinds) - 1)
            top = min(int(H * 0.60), H - weight_band - block - int(H * 0.06))
            for i, kind in enumerate(kinds):
                mc.draw_cert_icon(d, kind, W / 2, top + i * step, r, ink=accent,
                                  ring=accent, disc=tuple(field),
                                  width=max(2, W // 220))

    if weight:
        f = mc.load_font("Inter.ttf", int(W * 0.044), [14, 600])
        mc.centered(d, W / 2, H - int(H * 0.075), weight, f, ink_c)
    return panel


def panel_sheet(panels: Dict[str, Image.Image], *, gutter: int = 48,
                labels: bool = True) -> Image.Image:
    """One flat sheet with every panel side by side, labelled, on a neutral field."""
    order = [k for k in ("front", "back", "side") if k in panels]
    if not order:
        raise ValueError("no panels to lay out")
    heights = max(p.height for p in panels.values())
    pad = 40
    label_h = 46 if labels else 0
    width = pad * 2 + sum(panels[k].width for k in order) + gutter * (len(order) - 1)
    sheet = Image.new("RGB", (width, heights + pad * 2 + label_h), (238, 234, 226))
    d = ImageDraw.Draw(sheet)
    x = pad
    for key in order:
        sheet.paste(panels[key], (x, pad + label_h), panels[key])
        if labels:
            f = mc.load_font("Inter.ttf", 26, [14, 640])
            mc.centered(d, x + panels[key].width / 2, pad + label_h / 2,
                        key.upper() + " PANEL", f, (28, 46, 38))
        x += panels[key].width + gutter
    return sheet


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def validate_panels(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Report what a print-ready package still needs. Never invents a pass."""
    missing: List[str] = []
    if not spec.get("title"):
        missing.append("product name")
    if not spec.get("weight"):
        missing.append("net weight")
    if not spec.get("ingredients") and not spec.get("supplement_facts"):
        missing.append("ingredients or supplement facts")
    if not spec.get("company"):
        missing.append("company name")
    if not spec.get("address"):
        missing.append("company address")
    if not spec.get("country_of_origin"):
        missing.append("country of origin")
    warnings: List[str] = []
    dims = spec.get("dims") or {}
    # The 1.2-1.9 ratio is a pouch heuristic. A carton, bottle label or tube
    # legitimately has a different face ratio; warning on those trains the
    # operator to ignore validation.
    if str(spec.get("format") or "pouch").strip().lower() == "pouch":
        if dims.get("width_mm") and dims.get("height_mm"):
            ratio = float(dims["height_mm"]) / float(dims["width_mm"])
            if not (1.2 <= ratio <= 1.9):
                warnings.append(
                    f"height/width ratio {ratio:.2f} is outside the usual 1.2-1.9 "
                    f"stand-up-pouch band; confirm with the converter")
    if spec.get("claims"):
        warnings.append(
            "claims are rendered as supplied — screen each one for disease/treatment "
            "language before print (see docs/decisions.md, compliance gate)")
    return {"ready_for_print": not missing, "missing": missing, "warnings": warnings}
