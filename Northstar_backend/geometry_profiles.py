"""Packaging geometry profiles: box, bottle, tube (Phase 2, item 3).

Every format answers the same three questions with numbers, so the compositor
never guesses:

    usable area   - where a label may legally live
    target quad   - the four corners the label is warped onto
    clearances    - what must never be printed on (welds, crimps, caps, tucks)

Units are millimetres in, pixels out via an explicit `px_per_mm`. Nothing here
touches an image; `pouch_label` consumes these dicts the same way it consumes a
measured quad.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

MIN_DPI = 300


def _q(quad: List[Tuple[float, float]]) -> List[List[float]]:
    return [[round(float(x), 3), round(float(y), 3)] for x, y in quad]


def px(mm: float, px_per_mm: float) -> float:
    return round(float(mm) * float(px_per_mm), 3)


def required_px_per_mm(dpi: int = MIN_DPI) -> float:
    return round(float(dpi) / 25.4, 4)


def _check_positive(**kw: float) -> None:
    for name, value in kw.items():
        if float(value) <= 0:
            raise ValueError(f"{name} must be > 0 (got {value})")


def rigid_box(*, width: float, depth: float, height: float,
              glue_tab: float = 15.0, bleed: float = 3.0,
              tuck: float = 12.0, px_per_mm: float = 6.0) -> Dict[str, Any]:
    """Straight tuck box: four panels + glue tab, bleed on the outside.

    The dieline perimeter is 2*(w+d) + glue_tab; corner bleed exists because a
    printed sheet is guillotined at the die line and paper registration is not
    exact, so the 3mm ring must be printable on every panel.
    """
    _check_positive(width=width, depth=depth, height=height, glue_tab=glue_tab)
    perimeter = 2 * (width + depth)
    panels = [
        {"name": "front", "w": width, "h": height, "x": 0.0},
        {"name": "right", "w": depth, "h": height, "x": width},
        {"name": "back", "w": width, "h": height, "x": width + depth},
        {"name": "left", "w": depth, "h": height, "x": 2 * width + depth},
        {"name": "glue", "w": glue_tab, "h": height, "x": perimeter},
    ]
    return {
        "kind": "box",
        "unit": "mm",
        "width_mm": width,
        "depth_mm": depth,
        "height_mm": height,
        "bleed_mm": bleed,
        "glue_tab_mm": glue_tab,
        "tuck_mm": tuck,
        "dieline": {
            "width": round(perimeter + glue_tab, 3),
            "height": round(height + 2 * tuck, 3),
            "perimeter": round(perimeter, 3),
        },
        "panels": panels,
        "face": {"w": width, "h": height},          # printable front panel
        # NOMINAL front-face quad at px_per_mm. A real plate must supply a
        # MEASURED quad; this is the default the compositor scales to fit.
        "quad": _q([(0.0, 0.0), (px(width, px_per_mm), 0.0),
                    (px(width, px_per_mm), px(height, px_per_mm)),
                    (0.0, px(height, px_per_mm))]),
        "clearances": {
            "corner_bleed_mm": bleed,
            "tuck_top_mm": tuck,
            "tuck_bottom_mm": tuck,
            "glue_tab_mm": glue_tab,
        },
        "notes": ["corner bleed must be neutralised before the label is warped",
                  "tuck flaps are not printable - keep copy off the top/bottom 12mm"],
    }


def bottle(*, diameter: float, height: float, label_height: float,
           label_top_offset: float, cap_height: float = 25.0,
           seam_clearance: float = 6.0, px_per_mm: float = 6.0) -> Dict[str, Any]:
    """Cylindrical bottle: an arc-mapped label with a seam gap.

    A flat label cannot wrap a cylinder without distortion: the horizontal axis
    compresses by sin(theta) toward the silhouette. `arc_map` gives the sampling
    curve so the compositor can resample columns instead of stretching them.
    """
    _check_positive(diameter=diameter, height=height, label_height=label_height)
    circumference = 3.141592653589793 * diameter
    usable_h = height - cap_height - seam_clearance
    if label_height > usable_h:
        raise ValueError(
            f"label_height {label_height}mm exceeds usable height {usable_h:.1f}mm "
            f"(height {height} - cap {cap_height} - seam {seam_clearance})")
    if label_top_offset < cap_height:
        raise ValueError("label_top_offset starts inside the cap clearance zone")

    wrap_fraction = min(1.0, (circumference - seam_clearance) / circumference)
    r = px(diameter / 2.0, px_per_mm)
    top = px(label_top_offset, px_per_mm)
    bottom = px(label_top_offset + label_height, px_per_mm)
    return {
        "kind": "bottle",
        "unit": "mm",
        "diameter_mm": diameter,
        "height_mm": height,
        "label_height_mm": label_height,
        "label_width_mm": round(circumference * wrap_fraction, 3),
        "circumference_mm": round(circumference, 3),
        "wrap_fraction": round(wrap_fraction, 4),
        # Physical coverage and VISIBLE coverage are different numbers. The
        # label may wrap 97% of the circumference, but a 97%-wide label puts
        # its text on the edge-on silhouette. The compositor uses the visible
        # share so type stays legible on the front of the bottle.
        "render_wrap_fraction": 0.75,
        "usable_height_mm": round(usable_h, 3),
        "px_per_mm": px_per_mm,
        "radius_px": r,
        "quad": _q([(0.0, top), (2 * r, top), (2 * r, bottom), (0.0, bottom)]),
        "clearances": {
            "cap_mm": cap_height,
            "seam_mm": seam_clearance,
            "label_top_mm": label_top_offset,
            "label_bottom_mm": round(height - (label_top_offset + label_height) - seam_clearance, 3),
        },
        "arc_map": {
            "model": "sinusoidal",
            "note": "column u -> theta = u * wrap_fraction * 2pi; horizontal gain = sin(theta)",
            "seam_angle_deg": round(360.0 * (1.0 - wrap_fraction), 2),
        },
        "notes": ["never print across the seam", "cap zone is clearance, not bleed"],
    }


def tube(*, diameter: float, height: float, crimp_top: float = 8.0,
         crimp_bottom: float = 8.0, cap_height: float = 20.0,
         px_per_mm: float = 6.0) -> Dict[str, Any]:
    """Crimp tube: crimp zones are sealed, so copy must stay inside them."""
    _check_positive(diameter=diameter, height=height, crimp_top=crimp_top)
    usable = height - crimp_top - crimp_bottom - cap_height
    if usable <= 0:
        raise ValueError(f"no usable label height: {height} - crimps - cap <= 0")
    circumference = 3.141592653589793 * diameter
    aspect = round(usable / circumference, 4)
    if aspect < 0.35:
        raise ValueError(f"usable area too squat for a label (aspect {aspect} < 0.35)")
    r = px(diameter / 2.0, px_per_mm)
    top = px(crimp_top + cap_height, px_per_mm)
    return {
        "kind": "tube",
        "unit": "mm",
        "diameter_mm": diameter,
        "height_mm": height,
        "circumference_mm": round(circumference, 3),
        "usable_height_mm": round(usable, 3),
        "label_aspect": aspect,
        "px_per_mm": px_per_mm,
        "quad": _q([(0.0, top), (2 * r, top), (2 * r, top + px(usable, px_per_mm)),
                    (0.0, top + px(usable, px_per_mm))]),
        "clearances": {
            "crimp_top_mm": crimp_top,
            "crimp_bottom_mm": crimp_bottom,
            "cap_mm": cap_height,
        },
        "notes": ["crimp zones are heat-sealed - zero ink",
                  "cap clearance is measured from the crimp, not the tube end"],
    }


def pouch(*, width: float, height: float, top_weld: float = 12.0,
          bottom_gusset: float = 30.0, px_per_mm: float = 6.0) -> Dict[str, Any]:
    """Stand-up pouch - the format already proven by `pouch_label.measure_face`."""
    _check_positive(width=width, height=height)
    usable = height - top_weld - bottom_gusset
    if usable <= 0:
        raise ValueError("no usable label height between weld and gusset")
    return {
        "kind": "pouch",
        "unit": "mm",
        "width_mm": width,
        "height_mm": height,
        "usable_height_mm": round(usable, 3),
        "px_per_mm": px_per_mm,
        "quad": _q([(0.0, px(top_weld, px_per_mm)),
                    (px(width, px_per_mm), px(top_weld, px_per_mm)),
                    (px(width, px_per_mm), px(top_weld + usable, px_per_mm)),
                    (0.0, px(top_weld + usable, px_per_mm))]),
        "clearances": {"top_weld_mm": top_weld, "bottom_gusset_mm": bottom_gusset},
        "notes": ["the zipper header is a weld - no ink",
                  "the gusset curves away from the camera; copy there reads as squashed"],
    }


PROFILES = {"box": rigid_box, "bottle": bottle, "tube": tube, "pouch": pouch}

#: Field defaults so a job can name a format without restating industry-standard dims.
DEFAULT_DIMS: Dict[str, Dict[str, float]] = {
    "pouch": {"width": 100.0, "height": 200.0},
    "box": {"width": 80.0, "depth": 40.0, "height": 180.0},
    "bottle": {"diameter": 60.0, "height": 200.0, "label_height": 80.0, "label_top_offset": 30.0},
    "tube": {"diameter": 40.0, "height": 160.0},
}


def profile(kind: str, **dims: Any) -> Dict[str, Any]:
    """Dispatch by format name. Unknown formats are refused, never defaulted."""
    fn = PROFILES.get(str(kind or "").strip().lower())
    if fn is None:
        raise KeyError(f"unknown packaging format {kind!r}; known: {sorted(PROFILES)}")
    merged = {**DEFAULT_DIMS.get(str(kind or "").strip().lower(), {}), **(dims or {})}
    out = fn(**merged)
    out["dpi_check"] = {
        "required_px_per_mm": required_px_per_mm(MIN_DPI),
        "configured_px_per_mm": out.get("px_per_mm"),
        "ok": float(out.get("px_per_mm") or 0) >= required_px_per_mm(MIN_DPI) * 0.999,
    }
    return out


__all__ = ["rigid_box", "bottle", "tube", "pouch", "profile", "PROFILES",
           "px", "required_px_per_mm", "MIN_DPI"]
