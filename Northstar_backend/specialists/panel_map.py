"""Per-surface panel mapping — the piece of Packify's accuracy we can do in 2-D.

Packify gets print placement right because the artwork is mapped through UVs onto
a real 3-D surface. We do not have a 3-D engine (and do not want a cloud one),
but we DO already have the two things that matter:

  • the parametric dieline, which returns exact panel rectangles
    (`design_studio_print.build_from_template("doypack")` → `meta.panels`), and
  • a measured face quad on the render (`pouch_label.measure_face`).

Warping ONE label across the WHOLE face ignores that a front view of a doypack is
three surfaces — front panel plus two gusset slivers — each foreshortened
differently. This module splits the measured quad into those surfaces so each can
be warped on its own.

Pure geometry, no rendering, no I/O.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

Point = List[float]
Quad = List[Point]  # [TL, TR, BR, BL]


def _lerp(a: Point, b: Point, t: float) -> Point:
    return [round(a[0] + (b[0] - a[0]) * t, 2),
            round(a[1] + (b[1] - a[1]) * t, 2)]


def _sub_quad(quad: Quad, t0: float, t1: float) -> Quad:
    """Slice the quad between two horizontal fractions (0 = left edge, 1 = right)."""
    tl, tr, br, bl = quad
    return [_lerp(tl, tr, t0), _lerp(tl, tr, t1), _lerp(bl, br, t1), _lerp(bl, br, t0)]


def panel_widths(panels: Dict[str, Any]) -> Dict[str, float]:
    """Read the panel dimensions the visible width needs.

    `design_studio_print` returns rects as [x, y, w, h]. The FRONT panel's `w` is
    the pouch width, but the GUSSET panel is drawn rotated 90° on the flat sheet,
    so its `w` is the pouch width again and its `h` is the gusset depth — the
    dimension that actually shows at the edge of a front view.

    Found by building: assuming rect[2] for both gave a 95/95/95 split on a
    95 mm pouch with 80 mm gussets. The gusset depth is the SHORTER side.
    """
    def rect(key: str) -> Sequence[float]:
        r = panels.get(key)
        if isinstance(r, (list, tuple)) and len(r) >= 4:
            try:
                return [float(v) for v in r[:4]]
            except (TypeError, ValueError):
                return []
        return []

    front = rect("front")
    gusset = rect("gusset")
    return {
        "front": front[2] if front else 0.0,
        "gusset": (min(gusset[2], gusset[3]) if gusset else 0.0),
    }


#: A gusset seen from the FRONT is edge-on, so only a fraction of its depth is
#: visible. Using the full depth made a 95 mm pouch with 80 mm gussets allocate
#: 31/37/31 % of the face to gusset/front/gusset — the subtitle was clipped at
#: both ends. 0.35 keeps the geometry honest and the front panel readable.
GUSSET_FORESIGHTEN = 0.35


def visible_fractions(panels: Dict[str, Any],
                      gusset_foreshorten: float = GUSSET_FORESIGHTEN) -> List[Dict[str, Any]]:
    """Left gusset / front / right gusset as fractions of the visible width.

    A front view shows the front panel plus one gusset on each side; each gusset
    is turned away from the camera, so its visible width is its depth times
    `gusset_foreshorten`, not its full depth.
    """
    w = panel_widths(panels)
    front, gusset = w["front"], w["gusset"] * max(0.0, float(gusset_foreshorten))
    if front <= 0 and gusset <= 0:
        return [{"surface": "front", "t0": 0.0, "t1": 1.0, "share": 1.0}]
    if gusset <= 0:
        return [{"surface": "front", "t0": 0.0, "t1": 1.0, "share": 1.0}]
    total = front + 2 * gusset
    g = gusset / total
    f = front / total
    return [
        {"surface": "gusset_left", "t0": 0.0, "t1": g, "share": g},
        {"surface": "front", "t0": g, "t1": g + f, "share": f},
        {"surface": "gusset_right", "t0": g + f, "t1": 1.0, "share": g},
    ]


def panel_quads(face_quad: Sequence[Sequence[float]],
                panels: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Split one measured face quad into per-surface quads.

    Returns [{surface, quad, share, note}] in left-to-right order. A pack with no
    gusset returns the original quad unchanged, so this is safe for flat formats.
    """
    quad: Quad = [[float(p[0]), float(p[1])] for p in face_quad]
    if len(quad) != 4:
        raise ValueError("face_quad must be 4 points [TL, TR, BR, BL]")

    out: List[Dict[str, Any]] = []
    for part in visible_fractions(panels):
        out.append({
            "surface": part["surface"],
            "quad": _sub_quad(quad, part["t0"], part["t1"]),
            "share": part["share"],
            "note": ("foreshortened gusset: warp its own artwork here, not the front panel"
                     if part["surface"].startswith("gusset") else
                     "front panel: the main artwork surface"),
        })
    return out


def describe(panels: Dict[str, Any]) -> str:
    """One-line, human-readable summary for tool output."""
    parts = visible_fractions(panels)
    return ", ".join(f"{p['surface']} {p['share'] * 100:.0f}%" for p in parts)
