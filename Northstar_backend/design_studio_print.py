"""Design Studio — print engine (layered dielines/labels + PDF/ZIP export).

Competitive-RE build (2026-10-16): the missing "print lane" identified against
Packify.ai / DYP.ai. Both competitors lock users in with
prompt -> parametric dieline (SVG) -> canvas editor -> print-ready export.
This module ships the parametric layer-honest half of that chain for Northstar:

- Pure geometry builders for labels and cartons that emit LAYERED vector art
  (bleed / trim / fold / safe / marks / info) as real, editable SVG groups —
  the "layered editable dieline" trick, our version, no AI required.
- Native PDF rendering via reportlab (no svglib/cairo dependency), plus a
  project ZIP export with a manifest.
- Template catalog + strict param sanitisation, so everything is testable and
  deterministic. NO provider calls, no cost, no network.

Honesty boundaries (burned into every artifact):
- These are DRAFT templates: geometry is approximate (e.g. RSC flap depth
  defaults to half the smaller side, a common commercial default). Sizes and
  fold allowances must be confirmed with the actual manufacturer/board.

Never import this module before data_layer (it is imported by main.py inside a
guard, same as design_studio_api).
"""

from __future__ import annotations

import base64
import html
import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response as _Response
from pydantic import BaseModel, Field

from data_layer import get_northstar_db
from design_studio_api import studio_account
import dieline_geometry as _dg

router = APIRouter(prefix="/api/design-studio/print", tags=["design-studio-print"])

MM_PT = 72.0 / 25.4  # points per millimetre

# ── Geometry primitives ─────────────────────────────────────────────────────
# A "build" is a resolution-independent drawing in millimetre space:
#   {"width_mm": float, "height_mm": float, "layers": [ {kind, layer, ...} ], ...}
# Renderers project it to SVG or PDF. Layers are deliberate: the SAME geometry
# the competitors only expose through their canvas editor.

LAYER_ORDER = ["bleed", "marks", "trim", "fold", "safe", "info"]

LAYER_STYLE = {
    "bleed": {"stroke": "#cbd5e1", "width": 0.25, "dash": None},
    "marks": {"stroke": "#9ca3af", "width": 0.25, "dash": None},
    "trim": {"stroke": "#111827", "width": 0.35, "dash": None},
    "fold": {"stroke": "#2563eb", "width": 0.25, "dash": "3 2"},
    "safe": {"stroke": "#94a3b8", "width": 0.25, "dash": "1 1.5"},
    "info": {"stroke": "#64748b", "width": 0.0, "dash": None},
}


def _round(v: float, n: int = 2) -> float:
    return round(float(v) + 1e-9, n)


def _fmt(v: float) -> str:
    """Compact number formatting for SVG attributes (56.0 -> '56')."""
    return f"{float(v):g}"


def _rect(x, y, w, h, layer, radius: float = 0.0):
    return {"kind": "rect", "x": _round(x), "y": _round(y), "w": _round(w),
            "h": _round(h), "radius": _round(radius), "layer": layer}


def _ellipse(cx, cy, rx, ry, layer):
    return {"kind": "ellipse", "cx": _round(cx), "cy": _round(cy),
            "rx": _round(rx), "ry": _round(ry), "layer": layer}


def _line(x1, y1, x2, y2, layer, dash: Optional[str] = None):
    return {"kind": "line", "x1": _round(x1), "y1": _round(y1),
            "x2": _round(x2), "y2": _round(y2), "layer": layer,
            "dash": dash}


def _text(x, y, s, layer="info", size: float = 3.0):
    return {"kind": "text", "x": _round(x), "y": _round(y),
            "text": str(s), "size": size, "layer": layer}


def _stamp(build: dict, title: str) -> dict:
    build["title"] = title
    build["generated_at"] = datetime.now(timezone.utc).isoformat()
    build["generator"] = "Northstar OS design-studio print engine (draft templates)"
    build["note"] = ("Draft geometry for layout/quoting. Confirm dimensions, "
                     "flap depths and bleeds with the manufacturer before production.")
    return build


def _info_block(x, y, lines: List[str], size: float = 3.0) -> List[dict]:
    out = []
    for i, line in enumerate(lines):
        out.append(_text(x, y + i * (size * 1.5), line, layer="info", size=size))
    return out


# ── Label builders ──────────────────────────────────────────────────────────

LABEL_SHAPES = ("rounded_rectangle", "rectangle", "square", "circle", "oval")


def build_label(shape: str, width_mm: float, height_mm: float, *,
                bleed_mm: float = 3.0, safe_mm: float = 3.0,
                radius_mm: Optional[float] = None) -> dict:
    """Build a layered label dieline. Coordinates include the bleed margin."""
    shape = (shape or "").strip().lower()
    if shape not in LABEL_SHAPES:
        raise ValueError(f"unknown label shape {shape!r}; use one of {LABEL_SHAPES}")
    w, h = float(width_mm), float(height_mm)
    b, s = float(bleed_mm), float(safe_mm)
    if w <= 0 or h <= 0:
        raise ValueError("width_mm and height_mm must be positive")
    # No clamping: a safe margin wider than the label is a bad spec, and the audit
    # at the end of this builder refuses it. Silently shrinking it to 0.5mm used to
    # produce a printable-looking drawing whose type sat on the trim line.
    if min(w, h) - 2 * s <= 0:
        raise _dg.DielineGeometryError([{
            "code": "safe_inverted",
            "detail": (f"safe margin {s:.1f}mm inverts on a {w:.1f}x{h:.1f}mm face; "
                       "reduce the margin or enlarge the label"),
            "mm": round(s, 2)}])

    layers: List[dict] = []
    total_w, total_h = w + 2 * b, h + 2 * b

    layers.append(_rect(0, 0, total_w, total_h, "bleed"))

    if shape in ("circle", "oval"):
        rx, ry = w / 2.0, h / 2.0
        cx, cy = b + rx, b + ry
        layers.append(_ellipse(cx, cy, rx, ry, "trim"))
        layers.append(_ellipse(cx, cy, rx + b, ry + b, "bleed"))
        sr_x, sr_y = rx - s, ry - s
        layers.append(_ellipse(cx, cy, sr_x, sr_y, "safe"))
    else:
        r = 0.0
        if shape == "rounded_rectangle":
            r = float(radius_mm) if radius_mm is not None else min(w, h) * 0.12
            r = max(0.0, min(r, min(w, h) / 2.0))
        if shape == "square" and abs(w - h) > 0.01:
            raise ValueError("square requires width_mm == height_mm")
        layers.append(_rect(b, b, w, h, "trim", radius=r))
        layers.append(_rect(0, 0, total_w, total_h, "bleed", radius=r + b))
        layers.append(_rect(b + s, b + s, w - 2 * s, h - 2 * s,
                            "safe", radius=max(r - s, 0.0)))

    layers += _info_block(b, total_h - 1.0, [
        f"Label {shape} {_round(w)}x{_round(h)}mm · bleed {_round(b)}mm · safe {_round(s)}mm",
        "Northstar OS draft template — verify with printer",
    ], size=2.4)

    build = {"width_mm": _round(total_w), "height_mm": _round(total_h),
             "layers": layers,
             "meta": {"kind": "label", "shape": shape, "width_mm": _round(w),
                      "height_mm": _round(h), "bleed_mm": _round(b),
                      "safe_mm": _round(s), "radius_mm": _round(radius_mm or 0)}}
    return _dg.require_valid(_stamp(build, f"Label — {shape} {_round(w)}x{_round(h)}mm"))


# ── Carton builders ─────────────────────────────────────────────────────────

def _panel_blank(panels: List[float], body_h: float, top_depths: List[float],
                 bottom_depths: List[float], *, bleed_mm: float,
                 label_axis: str = "x") -> dict:
    """Generic straight-fold blank from panel widths and tab depths.

    panels: body column widths (left->right), one tab depth per column.
    Top tabs extend upward by top_depths[i]; bottom tabs downward.
    Adjacent equal-depth tabs get a CUT slit; differing depths become outline
    steps. Vertical folds separate columns across the body only.
    """
    if len(top_depths) != len(panels) or len(bottom_depths) != len(panels):
        raise ValueError("panels and tab depth lists must align")
    total_w = sum(panels)
    max_top = max(top_depths) if top_depths else 0.0
    max_bot = max(bottom_depths) if bottom_depths else 0.0
    fold_top = bleed_mm + max_top
    fold_bot = fold_top + body_h
    total_h = body_h + max_top + max_bot + 2 * bleed_mm

    layers: List[dict] = []
    layers.append(_rect(0, 0, total_w + 2 * bleed_mm, total_h, "bleed"))

    # Outline (trim): top profile left->right, right edge, bottom profile
    # right->left, left edge. Steps encode depth transitions between tabs.
    def top_y(i: int) -> float:
        return fold_top - top_depths[i]

    def bot_y(i: int) -> float:
        return fold_bot + bottom_depths[i]

    pts: List[tuple] = []
    x = bleed_mm
    pts.append((x, top_y(0)))
    for i in range(len(panels)):
        x_next = x + panels[i]
        pts.append((x_next, top_y(i)))
        if i < len(panels) - 1:
            pts.append((x_next, top_y(i + 1)))  # step between tabs
        x = x_next
    pts.append((x, bot_y(len(panels) - 1)))
    for i in range(len(panels) - 1, -1, -1):
        x_prev = x - panels[i]
        pts.append((x_prev, bot_y(i)))
        if i > 0:
            pts.append((x_prev, bot_y(i - 1)))
        x = x_prev
    pts.append((x, top_y(0)))
    for i in range(1, len(pts)):
        x1, y1 = pts[i - 1]
        x2, y2 = pts[i]
        if abs(x1 - x2) > 1e-6 or abs(y1 - y2) > 1e-6:
            layers.append(_line(x1, y1, x2, y2, "trim"))

    # Internal cut slits between equal-depth adjacent tabs.
    x = bleed_mm
    for i in range(len(panels) - 1):
        x += panels[i]
        if abs(top_depths[i] - top_depths[i + 1]) < 1e-6 and top_depths[i] > 0:
            layers.append(_line(x, fold_top - top_depths[i], x, fold_top, "trim"))
        if abs(bottom_depths[i] - bottom_depths[i + 1]) < 1e-6 and bottom_depths[i] > 0:
            layers.append(_line(x, fold_bot, x, fold_bot + bottom_depths[i], "trim"))

    # Fold lines: horizontal across tabbed columns; vertical across body.
    tabbed_w = sum(panels[i] for i in range(len(panels)) if top_depths[i] > 0)
    if tabbed_w > 0:
        layers.append(_line(bleed_mm, fold_top, bleed_mm + tabbed_w, fold_top, "fold"))
    tabbed_w_b = sum(panels[i] for i in range(len(panels)) if bottom_depths[i] > 0)
    if tabbed_w_b > 0:
        layers.append(_line(bleed_mm, fold_bot, bleed_mm + tabbed_w_b, fold_bot, "fold"))
    x = bleed_mm
    for i in range(len(panels) - 1):
        x += panels[i]
        layers.append(_line(x, fold_top, x, fold_bot, "fold"))

    layers += _info_block(bleed_mm, total_h - 1.0, [
        f"Blank {_round(total_w)} x {_round(total_h)}mm (panels {[ _round(p) for p in panels ]})",
        "Northstar OS draft template — verify with manufacturer",
    ], size=2.4)

    build = {"width_mm": _round(total_w + 2 * bleed_mm), "height_mm": _round(total_h),
             "layers": layers,
             "meta": {"panels": [_round(p) for p in panels],
                      "body_h": _round(body_h),
                      "top_depths": [_round(d) for d in top_depths],
                      "bottom_depths": [_round(d) for d in bottom_depths],
                      "bleed_mm": _round(bleed_mm)}}
    return build


CARTON_TEMPLATES = ("rsc_box", "tuck_end", "sleeve", "doypack")

#: Published stand-up-pouch ladder (fill weight -> width, height, gusset in mm).
#: Source: the packaging blueprint's calibration table (Sparal's published 6-size
#: ladder, cross-checked against PackagingBest templates and real mylar dielines).
#: Used ONLY to flag specs that look wrong; the converter's die is the authority.
DOYPACK_LADDER = (
    (50, 100.0, 150.0, 60.0),
    (100, 120.0, 180.0, 70.0),
    (250, 140.0, 200.0, 80.0),
    (500, 160.0, 240.0, 90.0),
    (1000, 200.0, 300.0, 100.0),
)


def build_doypack(width_mm: float, height_mm: float, gusset_mm: float = 40.0, *,
                  weld_mm: float = 6.0, top_weld_mm: float = 8.0,
                  zip_offset_mm: float = 25.0, bleed_mm: float = 3.0,
                  safe_mm: float = 5.0, fill_g: Optional[float] = None) -> dict:
    """Stand-up pouch (doypack) flat planning dieline in true millimetres.

    Structure, top -> bottom on the flat sheet: TOP SEAL (zipper strip + zipper
    keep-out band) / FRONT / BOTTOM SEAL / GUSSET upper half / gusset centre
    crease / GUSSET lower half / BOTTOM SEAL / BACK, with SIDE SEAL zones down
    both edges and a print-safe boundary inside the seals.

    Honesty (unchanged from the blueprint): this is a CALIBRATED PLANNING
    DIELINE, not a die. Seal widths, the bottom seal style (K-seal vs pillow),
    dart/crease positions and the zipper model are converter-specific; the
    proportion check below flags specs that sit outside the published
    fill-weight ladder so a wrong gusset is caught BEFORE plates are cut.
    """
    W, H, G = float(width_mm), float(height_mm), float(gusset_mm)
    w, t = float(weld_mm), float(top_weld_mm)
    z = float(zip_offset_mm)
    b, s = float(bleed_mm), float(safe_mm)
    if min(W, H, G, w, t, z, b, s) <= 0:
        raise ValueError("doypack params must be positive")
    if G >= H:
        raise ValueError("gusset_mm must be smaller than height_mm for a stand-up pouch")

    sheet_w = W + 2 * w + 2 * b
    sheet_h = (t + H + w + G + w + H) + 2 * b   # top seal + front + 2 seals + gusset + back
    layers: List[dict] = []
    layers.append(_rect(0, 0, sheet_w, sheet_h, "bleed"))
    layers.append(_rect(b, b, sheet_w - 2 * b, sheet_h - 2 * b, "trim"))

    x_l, x_r = b + w, b + w + W
    y_top_seal = b
    y_front_top = b + t
    y_front_bot = y_front_top + H
    y_seal_1 = y_front_bot + w
    y_gusset_mid = y_seal_1 + G / 2.0
    y_gusset_end = y_seal_1 + G
    y_seal_2 = y_gusset_end + w
    # The second weld IS the top of the back panel: adding another weld thickness
    # here pushed the back panel `w` mm past the trim line (found by
    # dieline_geometry.audit: panel_outside_trim on a 150x210+80 pouch).
    y_back = y_seal_2
    y_back_end = y_back + H

    # side weld zones (the film edges that become the pouch's side seams)
    layers.append(_rect(b, b, w, sheet_h - 2 * b, "marks"))
    layers.append(_rect(x_r, b, w, sheet_h - 2 * b, "marks"))

    # panel + seal boundaries
    for yy, label in ((y_front_top, "front top"), (y_front_bot, "front/gusset seal"),
                      (y_seal_1, "seal top"), (y_gusset_end, "gusset/seal"),
                      (y_seal_2, "seal top"), (y_back, "back top")):
        layers.append(_line(x_l, yy, x_r, yy, "fold"))

    # the gusset's own centre crease (the fold that lets the pouch stand)
    layers.append(_line(x_l, y_gusset_mid, x_r, y_gusset_mid, "fold"))
    layers.append(_text(x_l + 2, y_gusset_mid + 2, "gusset centre crease", size=2.6))

    # zipper line + its keep-out band (no print inside the weld/zip zone)
    y_zip = y_front_top + z
    keep = 6.0
    layers.append(_rect(x_l, max(b, y_zip - keep), W, keep * 2, "safe"))
    layers.append(_line(x_l, y_zip, x_r, y_zip, "fold"))
    layers.append(_text(x_l + 2, y_zip - 4.5, "zipper line (keep-out band shaded)", size=2.6))

    # print-safe boundary: seals + margin are no-print zones
    layers.append(_rect(x_l + s, y_front_top + s, W - 2 * s, H - 2 * s, "safe"))
    layers.append(_rect(x_l + s, y_back + s, W - 2 * s, H - 2 * s, "safe"))

    checks = check_doypack_proportions(W, H, G, fill_g=fill_g)
    layers += _info_block(x_l, sheet_h - b - 1.0, [
        f"Doypack planning dieline {_round(W)}x{_round(H)}mm + {_round(G)}mm gusset "
        f"(sheet {_round(sheet_w)}x{_round(sheet_h)}mm, bleed {_round(b)}mm)",
        f"seals: sides {_round(w)}mm / top {_round(t)}mm / bottom {_round(w)}mm - confirm "
        "with the converter",
        f"proportion check: {checks['status']}",
    ], size=2.4)
    for i, warning in enumerate(checks["warnings"][:3]):
        layers.append(_text(x_l + 2, sheet_h - b - 12.0 - i * 4.0, warning, size=2.2))

    build = {"width_mm": _round(sheet_w), "height_mm": _round(sheet_h),
             "layers": layers,
             "meta": {"template": "doypack", "width_mm": _round(W), "height_mm": _round(H),
                      "gusset_mm": _round(G), "weld_mm": _round(w), "top_weld_mm": _round(t),
                      "zip_offset_mm": _round(z), "bleed_mm": _round(b),
                      "safe_mm": _round(s),
                      "seal_style": "assumed K-seal (confirm with converter)",
                      "confidence": "planning dieline - not a die",
                      "proportion_check": checks,
                      "panels": {
                          "front": [_round(x_l), _round(y_front_top), _round(W), _round(H)],
                          "gusset": [_round(x_l), _round(y_seal_1), _round(W), _round(G)],
                          "gusset_centre_y": _round(y_gusset_mid),
                          "back": [_round(x_l), _round(y_back), _round(W), _round(H)],
                          "zip_y": _round(y_zip),
                      }}}
    return _stamp(build, f"Doypack {_round(W)}x{_round(H)}mm + {_round(G)}mm gusset")


def check_doypack_proportions(width_mm: float, height_mm: float, gusset_mm: float, *,
                              fill_g: Optional[float] = None) -> Dict[str, Any]:
    """Flag pouch specs that sit outside published fill-weight proportions.

    Ladder source: the published stand-up-pouch sizing table used by the
    packaging blueprint (Sparal 6-size standard ladder, cross-checked against
    PackagingBest templates and real mylar dielines). Warnings only - the
    operator's numbers are never silently reshaped.
    """
    W, H, G = float(width_mm), float(height_mm), float(gusset_mm)
    warnings: List[str] = []
    row = None
    if fill_g:
        row = min(DOYPACK_LADDER, key=lambda r: abs(r[0] - float(fill_g)))
        f, lw, lh, lg = row
        if G < lg * 0.75:
            warnings.append(
                f"gusset {G:g}mm is far below the published {lg:g}mm for a {f:g}g pouch "
                f"(ladder row {lw:g}x{lh:g}+{lg:g}) - measure a competitor pouch and "
                "confirm before plates")
        if abs(W - lw) / lw > 0.25 or abs(H - lh) / lh > 0.25:
            warnings.append(
                f"panel {W:g}x{H:g}mm sits >25% off the {f:g}g ladder row "
                f"{lw:g}x{lh:g}mm - confirm the fill actually fits")
    ratio = H / W if W else 0.0
    if not 1.2 <= ratio <= 1.8:
        warnings.append(f"height/width ratio {ratio:.2f} is outside the usual 1.2-1.8 "
                        "stand-up-pouch band (heuristic)")
    status = "ok" if not warnings else "warnings"
    return {"status": status, "warnings": warnings,
            "ladder_row": ({"fill_g": row[0], "width_mm": row[1], "height_mm": row[2],
                            "gusset_mm": row[3]} if row else None),
            "ladder_source": "Sparal published stand-up-pouch ladder (6 sizes), "
                             "cross-checked vs PackagingBest templates",
            "note": "Heuristics flag risk; a converter's die drawing is the authority."}


def build_carton(template: str, length_mm: float, width_mm: float, height_mm: float, *,
                 flap_mm: Optional[float] = None, glue_mm: float = 15.0,
                 tuck_mm: Optional[float] = None, dust_mm: Optional[float] = None,
                 bleed_mm: float = 3.0) -> dict:
    """Build a layered carton blank (draft geometry)."""
    template = (template or "").strip().lower()
    if template not in CARTON_TEMPLATES:
        raise ValueError(f"unknown carton template {template!r}; use one of {CARTON_TEMPLATES}")
    L, W, H = float(length_mm), float(width_mm), float(height_mm)
    if min(L, W, H) <= 0:
        raise ValueError("length/width/height must be positive")
    g = float(glue_mm)

    if template == "rsc_box":
        # FEFCO 0201-style regular slotted carton. Flap depth defaults to half
        # the smaller side (common commercial default; verify with supplier).
        f = float(flap_mm) if flap_mm is not None else min(L, W) / 2.0
        panels = [L, W, L, W, g]
        depths = [f, f, f, f, 0.0]
        build = _panel_blank(panels, H, depths, depths, bleed_mm=bleed_mm)
        build["meta"].update({"template": template, "length_mm": _round(L),
                              "width_mm": _round(W), "height_mm": _round(H),
                              "flap_mm": _round(f), "glue_mm": _round(g)})
        build = _stamp(build, f"RSC box {_round(L)}x{_round(W)}x{_round(H)}mm (FEFCO 0201-style)")
    elif template == "tuck_end":
        # Straight tuck-end carton (simplified; no locking lip arc).
        t = float(tuck_mm) if tuck_mm is not None else W * 0.5 + 6.0
        d = float(dust_mm) if dust_mm is not None else W * 0.35
        panels = [L, W, L, W, g]
        top = [t, d, t, d, 0.0]
        bottom = [d, t, d, t, 0.0]  # bottom closes in the opposite order
        build = _panel_blank(panels, H, top, bottom, bleed_mm=bleed_mm)
        build["meta"].update({"template": template, "length_mm": _round(L),
                              "width_mm": _round(W), "height_mm": _round(H),
                              "tuck_mm": _round(t), "dust_mm": _round(d),
                              "glue_mm": _round(g)})
        build = _stamp(build, f"Tuck-end carton {_round(L)}x{_round(W)}x{_round(H)}mm")
    else:  # sleeve
        panels = [L, W, L, W, g]
        depths = [0.0] * 5
        build = _panel_blank(panels, H, depths, depths, bleed_mm=bleed_mm)
        build["meta"].update({"template": template, "length_mm": _round(L),
                              "width_mm": _round(W), "height_mm": _round(H),
                              "glue_mm": _round(g)})
        build = _stamp(build, f"Sleeve {_round(L)}x{_round(W)}x{_round(H)}mm")
    # Same gate as the labels: no carton leaves this function with a flap deeper
    # than its body, a non-positive panel, or art outside the bleed box.
    return _dg.require_valid(build)


# ── Renderers ───────────────────────────────────────────────────────────────

def render_svg(build: dict) -> str:
    """Project a build to layered, editable SVG groups (mm units)."""
    w, h = _fmt(build["width_mm"]), _fmt(build["height_mm"])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        f'width="{w}mm" height="{h}mm" '
        f'viewBox="0 0 {w} {h}" data-generator="northstar-design-studio">',
        f"<title>{html.escape(build.get('title', 'dieline'))}</title>",
        f"<desc>{html.escape(build.get('note', ''))}</desc>",
    ]
    for layer in LAYER_ORDER:
        style = LAYER_STYLE[layer]
        parts.append(
            f'<g id="layer-{layer}" inkscape:label="{layer}" '
            f'stroke="{style["stroke"]}" stroke-width="{style["width"]}" '
            f'fill="none"'
            + (f' stroke-dasharray="{style["dash"]}"' if style["dash"] else "")
            + (f' stroke-linecap="round"' if layer == "fold" else "")
            + ">"
        )
        for it in build["layers"]:
            if it.get("layer") != layer:
                continue
            if it["kind"] == "rect":
                rx = f' rx="{it["radius"]}"' if it.get("radius") else ""
                parts.append(f'<rect x="{it["x"]}" y="{it["y"]}" '
                             f'width="{it["w"]}" height="{it["h"]}"{rx}/>')
            elif it["kind"] == "ellipse":
                parts.append(f'<ellipse cx="{it["cx"]}" cy="{it["cy"]}" '
                             f'rx="{it["rx"]}" ry="{it["ry"]}"/>')
            elif it["kind"] == "line":
                dash = f' stroke-dasharray="{it["dash"]}"' if it.get("dash") else ""
                parts.append(f'<line x1="{it["x1"]}" y1="{it["y1"]}" '
                             f'x2="{it["x2"]}" y2="{it["y2"]}"{dash}/>')
            elif it["kind"] == "text":
                parts.append(
                    f'<text x="{it["x"]}" y="{it["y"]}" font-family="sans-serif" '
                    f'font-size="{it["size"]}" fill="{LAYER_STYLE["info"]["stroke"]}" '
                    f'stroke="none">{html.escape(it["text"])}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def render_pdf(build: dict) -> bytes:
    """Project a build to a single-page PDF via reportlab (no extra deps)."""
    from reportlab.pdfgen import canvas as _canvas  # local import: heavy module

    w_pt, h_pt = build["width_mm"] * MM_PT, build["height_mm"] * MM_PT
    buf = io.BytesIO()
    c = _canvas.Canvas(buf, pagesize=(w_pt, h_pt))
    c.setTitle(build.get("title", "dieline"))
    c.setAuthor("Northstar OS design-studio print engine")
    c.setSubject(build.get("note", ""))

    def y_pdf(y_mm: float) -> float:
        return h_pt - y_mm * MM_PT

    for layer in LAYER_ORDER:
        style = LAYER_STYLE[layer]
        c.setStrokeColorRGB(*_hex_rgb(style["stroke"]))
        c.setLineWidth(max(style["width"], 0.05) * MM_PT)
        c.setDash([float(d) * MM_PT for d in style["dash"].split()] if style["dash"] else [])
        for it in build["layers"]:
            if it.get("layer") != layer:
                continue
            if it["kind"] == "rect":
                r_pt = it.get("radius", 0) * MM_PT
                if r_pt > 0:
                    c.roundRect(it["x"] * MM_PT, y_pdf(it["y"] + it["h"]),
                                it["w"] * MM_PT, it["h"] * MM_PT, r_pt,
                                stroke=1, fill=0)
                else:
                    c.rect(it["x"] * MM_PT, y_pdf(it["y"] + it["h"]),
                           it["w"] * MM_PT, it["h"] * MM_PT, stroke=1, fill=0)
            elif it["kind"] == "ellipse":
                c.ellipse((it["cx"] - it["rx"]) * MM_PT, y_pdf(it["cy"] + it["ry"]),
                          (it["cx"] + it["rx"]) * MM_PT, y_pdf(it["cy"] - it["ry"]),
                          stroke=1, fill=0)
            elif it["kind"] == "line":
                c.line(it["x1"] * MM_PT, y_pdf(it["y1"]),
                       it["x2"] * MM_PT, y_pdf(it["y2"]))
            elif it["kind"] == "text":
                c.setFont("Helvetica", it["size"] * MM_PT)
                c.setFillColorRGB(*_hex_rgb(style["stroke"]))
                c.drawString(it["x"] * MM_PT, y_pdf(it["y"]), it["text"])
                c.setFillColorRGB(0, 0, 0)
    c.showPage()
    c.save()
    return buf.getvalue()


def _hex_rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


# ── Catalog & validation ────────────────────────────────────────────────────

TEMPLATES: List[dict] = [
    {"id": "label_rounded_rectangle", "name": "Rounded-rectangle label", "kind": "label",
     "params": {"width_mm": 90, "height_mm": 60, "radius_mm": 8, "bleed_mm": 3, "safe_mm": 3},
     "editable": ["width_mm", "height_mm", "radius_mm", "bleed_mm", "safe_mm"]},
    {"id": "label_rectangle", "name": "Rectangle label", "kind": "label",
     "params": {"width_mm": 100, "height_mm": 70, "bleed_mm": 3, "safe_mm": 3},
     "editable": ["width_mm", "height_mm", "bleed_mm", "safe_mm"]},
    {"id": "label_square", "name": "Square label", "kind": "label",
     "params": {"width_mm": 60, "height_mm": 60, "radius_mm": 0, "bleed_mm": 3, "safe_mm": 3},
     "editable": ["width_mm", "height_mm", "radius_mm", "bleed_mm", "safe_mm"]},
    {"id": "label_circle", "name": "Circle label", "kind": "label",
     "params": {"width_mm": 60, "height_mm": 60, "bleed_mm": 3, "safe_mm": 3},
     "editable": ["width_mm", "height_mm", "bleed_mm", "safe_mm"]},
    {"id": "label_oval", "name": "Oval label", "kind": "label",
     "params": {"width_mm": 100, "height_mm": 60, "bleed_mm": 3, "safe_mm": 3},
     "editable": ["width_mm", "height_mm", "bleed_mm", "safe_mm"]},
    {"id": "rsc_box", "name": "RSC box (FEFCO 0201-style)", "kind": "carton",
     "params": {"length_mm": 200, "width_mm": 150, "height_mm": 100, "flap_mm": 75, "glue_mm": 15, "bleed_mm": 3},
     "editable": ["length_mm", "width_mm", "height_mm", "flap_mm", "glue_mm", "bleed_mm"]},
    {"id": "tuck_end", "name": "Tuck-end carton", "kind": "carton",
     "params": {"length_mm": 90, "width_mm": 60, "height_mm": 160, "tuck_mm": 36, "dust_mm": 21, "glue_mm": 15, "bleed_mm": 3},
     "editable": ["length_mm", "width_mm", "height_mm", "tuck_mm", "dust_mm", "glue_mm", "bleed_mm"]},
    {"id": "sleeve", "name": "Open sleeve", "kind": "carton",
     "params": {"length_mm": 150, "width_mm": 100, "height_mm": 80, "glue_mm": 15, "bleed_mm": 3},
     "editable": ["length_mm", "width_mm", "height_mm", "glue_mm", "bleed_mm"]},
    {"id": "doypack", "name": "Stand-up pouch (doypack)", "kind": "carton",
     "params": {"width_mm": 130, "height_mm": 210, "gusset_mm": 40, "weld_mm": 6,
                "top_weld_mm": 8, "zip_offset_mm": 25, "bleed_mm": 3, "safe_mm": 5,
                "fill_g": 0},
     "editable": ["width_mm", "height_mm", "gusset_mm", "weld_mm", "top_weld_mm",
                  "zip_offset_mm", "bleed_mm", "safe_mm", "fill_g"]},
]

_TEMPLATE_BY_ID = {t["id"]: t for t in TEMPLATES}

# clamp ranges (mm) per param name
_BOUNDS = {
    "width_mm": (5, 2000), "height_mm": (5, 2000), "length_mm": (5, 2000),
    "radius_mm": (0, 500), "bleed_mm": (0, 20), "safe_mm": (0, 40),
    "flap_mm": (5, 1000), "glue_mm": (5, 40), "tuck_mm": (5, 1000), "dust_mm": (5, 1000),
    "gusset_mm": (10, 150), "weld_mm": (3, 20), "top_weld_mm": (4, 30),
    "zip_offset_mm": (5, 80), "fill_g": (0, 5000),
}


def sanitize_params(template_id: str, params: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Validate/normalise template params. Unknown keys are rejected loudly."""
    tpl = _TEMPLATE_BY_ID.get(template_id)
    if tpl is None:
        raise ValueError(f"unknown template_id {template_id!r}; see GET /print/templates")
    allowed = set(tpl["editable"])
    clean: Dict[str, float] = dict(tpl["params"])
    for key, raw in (params or {}).items():
        if key not in allowed:
            raise ValueError(f"param {key!r} is not editable for {template_id!r}; allowed: {sorted(allowed)}")
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            continue  # cleared field: keep the template default, never error
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"param {key!r} must be numeric, got {raw!r}")
        lo, hi = _BOUNDS[key]
        if not (lo <= val <= hi):
            raise ValueError(f"param {key!r}={val} out of range [{lo}, {hi}] mm")
        clean[key] = val
    return clean


def build_from_template(template_id: str, params: Optional[Dict[str, Any]]) -> dict:
    clean = sanitize_params(template_id, params)
    if template_id.startswith("label_"):
        build = build_label(
            template_id.replace("label_", ""), clean["width_mm"], clean["height_mm"],
            bleed_mm=clean.get("bleed_mm", 3.0), safe_mm=clean.get("safe_mm", 3.0),
            radius_mm=clean.get("radius_mm"))
    elif template_id == "doypack":
        build = build_doypack(
            clean["width_mm"], clean["height_mm"], clean.get("gusset_mm", 40.0),
            weld_mm=clean.get("weld_mm", 6.0), top_weld_mm=clean.get("top_weld_mm", 8.0),
            zip_offset_mm=clean.get("zip_offset_mm", 25.0),
            bleed_mm=clean.get("bleed_mm", 3.0), safe_mm=clean.get("safe_mm", 5.0),
            fill_g=(clean.get("fill_g") or None))
    else:
        build = build_carton(
            template_id, clean["length_mm"], clean["width_mm"], clean["height_mm"],
            flap_mm=clean.get("flap_mm"), glue_mm=clean.get("glue_mm", 15.0),
            tuck_mm=clean.get("tuck_mm"), dust_mm=clean.get("dust_mm"),
            bleed_mm=clean.get("bleed_mm", 3.0))
    # One gate for every template: a dieline that cannot be printed is refused
    # here, before an SVG is rendered or an asset is persisted.
    return _dg.require_valid(build)


# ── Persistence ─────────────────────────────────────────────────────────────

def _out_dir():
    d = Path(__file__).resolve().parent / "data" / "studio_generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _persist(build: dict, svg: str, pdf: Optional[bytes], *, acct: str,
             project_id: Optional[str], name: Optional[str]) -> List[dict]:
    """Write artifact files and register them as studio assets."""
    db = get_northstar_db()
    out = []
    base_name = name or build.get("title") or "dieline"
    for kind, payload, mime, ext in (
        ("svg", svg.encode("utf-8"), "image/svg+xml", "svg"),
        ("pdf", pdf, "application/pdf", "pdf"),
    ):
        if payload is None:
            continue
        fname = f"dieline_{uuid.uuid4().hex}.{ext}"
        (_out_dir() / fname).write_bytes(payload)
        aid = db.design_studio.assets.create({
            "account_id": acct, "project_id": project_id,
            "name": f"{base_name} ({kind.upper()})",
            "asset_type": "dieline",
            "mime_type": mime,
            "storage_key": fname,
            "size_bytes": len(payload),
            "metadata": {"print_engine": {"template_title": build.get("title"),
                                          "meta": build.get("meta", {}),
                                          "layers": LAYER_ORDER,
                                          "format": kind},
                         "note": build.get("note")},
        })
        out.append({"format": kind, "asset_id": aid,
                    "file_url": f"/api/design-studio/assets/{aid}/file"})
    return out


# ── API ─────────────────────────────────────────────────────────────────────

class DielineIn(BaseModel):
    template_id: str = Field(..., min_length=3, max_length=60)
    params: Optional[Dict[str, Any]] = None
    persist: bool = True
    include_svg: bool = False   # inline SVG string in the response
    include_pdf: bool = False   # inline base64 PDF in the response
    project_id: Optional[str] = None
    name: Optional[str] = Field(None, max_length=120)


@router.get("/templates")
def list_templates(acct: str = Depends(studio_account)):
    """Catalog of parametric dieline/label templates (no cost, no provider)."""
    return {"templates": TEMPLATES,
            "units": "mm",
            "notes": [
                "Draft geometry: confirm dims/flap depths/bleeds with the manufacturer.",
                "SVG output is layered (bleed/trim/fold/safe/marks/info) for editing.",
            ]}


@router.post("/dielines")
def create_dieline(body: DielineIn, acct: str = Depends(studio_account)):
    """Build a layered dieline. persist=True writes SVG+PDF assets; the response
    can additionally inline the SVG or PDF (include_svg / include_pdf)."""
    try:
        build = build_from_template(body.template_id, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    svg = render_svg(build)
    pdf = render_pdf(build)
    assets = []
    if body.persist:
        assets = _persist(build, svg, pdf, acct=acct,
                          project_id=body.project_id, name=body.name)
    resp = {
        "template_id": body.template_id,
        "title": build.get("title"),
        "size_mm": {"width": build["width_mm"], "height": build["height_mm"]},
        "layers": LAYER_ORDER,
        "meta": build.get("meta", {}),
        "note": build.get("note"),
        "assets": assets,
    }
    if body.include_svg:
        resp["svg"] = svg
    if body.include_pdf:
        resp["pdf_base64"] = base64.b64encode(pdf).decode("ascii")
    return resp


@router.get("/projects/{pid}/export.zip")
def export_project_zip(pid: str, acct: str = Depends(studio_account)):
    """Bundle every stored artifact of a project + a manifest as one ZIP."""
    db = get_northstar_db()
    try:
        assets = db.design_studio.assets.list_by_project(account_id=acct, limit=5000) or []
    except TypeError:
        assets = db.design_studio.assets.list_by_project(acct, limit=5000) or []
    assets = [a for a in assets if str(a.get("project_id") or "") == str(pid)]
    try:
        jobs = db.design_studio.jobs.list_by_project(account_id=acct, limit=2000) or []
    except TypeError:
        jobs = db.design_studio.jobs.list_by_project(acct, limit=2000) or []
    jobs = [j for j in jobs if str(j.get("project_id") or "") == str(pid)]
    try:
        project = db.design_studio.projects.get_by_id(pid, account_id=acct)
    except Exception:
        project = None
    if project is None and not assets:
        raise HTTPException(status_code=404, detail="Project not found (or no artifacts)")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for a in assets:
            sk = a.get("storage_key")
            if not sk:
                continue
            f = _out_dir() / Path(str(sk)).name  # basename only - no traversal
            if f.is_file():
                zf.write(str(f), arcname=f"assets/{f.name}")
        manifest = {
            "format": "northstar-design-studio-export/1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "project": project,
            "assets": assets,
            "jobs": jobs,
            "note": ("Print lane draft artifacts. Verify dielines/dimensions with the "
                     "manufacturer; generated media follows the studio's provenance rules."),
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
    return _Response(
        content=buf.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="design-studio-{pid[:12]}-export.zip"'},
    )


@router.get("/health")
def print_health(acct: str = Depends(studio_account)):
    return {"ok": True, "templates": len(TEMPLATES),
            "units": "mm", "renderers": ["svg", "pdf"]}


# ── Prepress — ICC gamut + ink limit (2026-10-19) ───────────────────────────
# A screen render is not a print file. These endpoints run a REAL ICC transform
# (littleCMS) over a stored studio image and report the two numbers a printer
# asks for: colour shift through the press profile (CIE76 dE) and total area
# coverage. Local, deterministic, no network, no provider.

class PrepressIn(BaseModel):
    asset_id: str = Field(..., min_length=3, max_length=80)
    profile: Optional[str] = Field(None, max_length=120)
    limit_pct: float = Field(300.0, ge=50.0, le=400.0)
    tolerance_dE76: float = Field(8.0, ge=1.0, le=40.0)
    persist_cmyk: bool = False      # write a CMYK TIFF (+ soft proof PNG) asset


@router.get("/prepress/profiles")
def prepress_profiles(acct: str = Depends(studio_account)):
    import prepress as pp
    return {"profiles": [{"name": p.name, "description": p.description}
                         for p in pp.available_cmyk_profiles()],
            "note": ("Profiles present on this machine (Windows ships a SWOP "
                     "CMYK profile). Drop the co-packer's profile in and select "
                     "it by name; nothing is substituted silently.")}


@router.post("/prepress/check")
def prepress_check(body: PrepressIn, acct: str = Depends(studio_account)):
    import prepress as pp
    db = get_northstar_db()
    asset = db.design_studio.assets.get_by_id(body.asset_id, account_id=acct)
    if not asset or not asset.get("storage_key"):
        raise HTTPException(status_code=404, detail="Asset not found")
    path = _out_dir() / Path(str(asset["storage_key"])).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found on disk")
    try:
        report = pp.prepress_report(path.read_bytes(), profile=body.profile,
                                    limit_pct=body.limit_pct,
                                    de_tolerance=body.tolerance_dE76)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    resp = {"asset_id": body.asset_id, "name": asset.get("name"), **report}
    if body.persist_cmyk:
        conv = pp.to_cmyk(path.read_bytes(), profile=body.profile)
        proof = pp.soft_proof(path.read_bytes(), profile=body.profile)
        out_dir = _out_dir()
        cmyk_name = f"cmyk_{uuid.uuid4().hex}.tif"
        proof_name = f"proof_{uuid.uuid4().hex}.png"
        (out_dir / cmyk_name).write_bytes(conv["bytes"])
        (out_dir / proof_name).write_bytes(proof["bytes"])
        base = asset.get("name") or "artwork"
        cmyk_id = db.design_studio.assets.create({
            "account_id": acct, "project_id": asset.get("project_id"),
            "name": f"{base} (CMYK)", "asset_type": "print_file",
            "mime_type": "image/tiff", "storage_key": cmyk_name,
            "size_bytes": len(conv["bytes"]),
            "metadata": {"prepress": {"role": "cmyk", "profile": conv["profile"],
                                      "profile_description": conv["profile_description"],
                                      "intent": conv["intent"], "engine": conv["engine"],
                                      "source_asset_id": body.asset_id},
                         "report": report},
        })
        proof_id = db.design_studio.assets.create({
            "account_id": acct, "project_id": asset.get("project_id"),
            "name": f"{base} (soft proof)", "asset_type": "print_file",
            "mime_type": "image/png", "storage_key": proof_name,
            "size_bytes": len(proof["bytes"]),
            "metadata": {"prepress": {"role": "soft_proof", "profile": proof["profile"],
                                      "source_asset_id": body.asset_id}},
        })
        resp["cmyk_asset"] = {"asset_id": cmyk_id,
                              "file_url": f"/api/design-studio/assets/{cmyk_id}/file",
                              "profile": conv["profile"]}
        resp["proof_asset"] = {"asset_id": proof_id,
                               "file_url": f"/api/design-studio/assets/{proof_id}/file"}
    return resp


# ── Box library — external Boxes.py bridge (2026-10-16) ──────────────────
# The structures come from Boxes.py (GPL-3.0), run as a SEPARATE PROCESS on
# this machine; we consume its SVG output and never embed its code.

class BoxGenerateIn(BaseModel):
    generator: str = Field(..., min_length=1, max_length=60)
    x: Optional[float] = None
    y: Optional[float] = None
    h: Optional[float] = None
    thickness: Optional[float] = None


@router.get("/box-library")
def box_library(acct: str = Depends(studio_account)):
    from design_studio_boxes import BOX_LIBRARY, BOXES_LICENSE_NOTE, PARAM_SPEC, boxes_binary
    return {
        "generators": BOX_LIBRARY,
        "params": PARAM_SPEC,
        "available": boxes_binary() is not None,
        "license_note": BOXES_LICENSE_NOTE,
        "note": ("Structures are generated locally by Boxes.py. If it is not installed the "
                 "library reads unavailable and generation is refused — never faked."),
    }


@router.post("/box-generate")
def box_generate(body: BoxGenerateIn, acct: str = Depends(studio_account)):
    from design_studio_boxes import BoxesUnavailable, generate_box
    params = {k: v for k, v in {"x": body.x, "y": body.y, "h": body.h, "thickness": body.thickness}.items() if v is not None}
    try:
        return generate_box(body.generator, params)
    except BoxesUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "boxes_unavailable", "message": str(exc)})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "box_generation_refused", "message": str(exc)})
