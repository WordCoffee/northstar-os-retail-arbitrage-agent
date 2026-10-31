"""A+ module layout engine (Phase 1, item 1).

`specialists/image_aplus.py` already owns the VERIFIED canvas sizes and the copy
rules. This module is the missing half: the geometry. It turns a module id into
exact integer rectangles - safe area, image box, copy column, overlay band,
tile positions, comparison table cells - plus the `object-fit: cover` crop maths
and the responsive rules, so a renderer or a React component can place assets
without inventing pixel values.

Pure functions, no I/O. The JS mirror in the UI is parity-tested against the
tables in this file, so the two cannot drift.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

#: canvas per module id - mirrors specialists/image_aplus.MODULES["w"/"h"].
#: For the tile modules the canvas is the ROW (970 wide); the per-tile size is
#: in TILE, because the planner's w/h there is the tile, not the row.
CANVAS: Dict[str, Tuple[int, int]] = {
    "header": (970, 600),
    "logo": (600, 180),
    "banner": (970, 300),
    "sidebar": (300, 400),
    "sidebar_thumb": (350, 175),
    "four_tiles": (970, 220),
    "three_tiles": (970, 300),
    "single": (300, 300),
    "comparison": (970, 600),
    "premium_desktop": (1464, 600),
    "premium_mobile": (600, 450),
}

#: per-tile size, verified against the planner, for the tiled row modules
TILE: Dict[str, Tuple[int, int]] = {
    "three_tiles": (300, 300),
    "four_tiles": (220, 220),
}

SAFE_INSET = 24
TILE_GAP = 20
FOUR_TILE_GAP = 30
COPY_BAND = 0.44          # share of a header/banner width given to copy
COMPARISON_LABEL_W = 250


def _rect(x: int, y: int, w: int, h: int) -> Dict[str, int]:
    return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}


def _inset(w: int, h: int, inset: int = SAFE_INSET) -> Dict[str, int]:
    return _rect(inset, inset, max(1, w - 2 * inset), max(1, h - 2 * inset))


def _tiles(count: int, tile_w: int, tile_h: int, canvas_w: int, gap: int) -> List[Dict[str, int]]:
    """Tiles centred as a group, on integer pixels, with equal end margins."""
    total = count * tile_w + (count - 1) * gap
    margin = max(0, (canvas_w - total) // 2)
    return [_rect(margin + i * (tile_w + gap), 0, tile_w, tile_h) for i in range(count)]


def layout(kind: str, *, copy_side: str = "left") -> Dict[str, Any]:
    """Exact geometry for one module. Raises KeyError on an unknown kind."""
    if kind not in CANVAS:
        raise KeyError(f"unknown A+ module kind: {kind}")
    w, h = CANVAS[kind]
    out: Dict[str, Any] = {
        "kind": kind,
        "canvas": _rect(0, 0, w, h),
        "safe": _inset(w, h),
        "image": _rect(0, 0, w, h),
        "tiles": [],
        "comparison": None,
        "copy": None,
    }

    if kind in ("header", "banner"):
        band = int(round(w * COPY_BAND))
        band = band - (band % 2)  # even keeps text on whole pixels after a 2x render
        x = SAFE_INSET if copy_side == "left" else w - band
        out["copy"] = {
            **_rect(x, 0, band, h),
            "align": "left" if copy_side == "left" else "right",
            "valign": "middle",
            "max_chars": 90 if kind == "header" else 60,
        }

    if kind == "three_tiles":
        tw, th = TILE[kind]
        out["tiles"] = _tiles(3, tw, th, w, TILE_GAP)
    if kind == "four_tiles":
        tw, th = TILE[kind]
        out["tiles"] = _tiles(4, tw, th, w, FOUR_TILE_GAP)

    if kind == "comparison":
        header_h = 90
        col_w = (w - COMPARISON_LABEL_W) // 2
        out["comparison"] = {
            "header": _rect(0, 0, w, header_h),
            "label_col": _rect(0, header_h, COMPARISON_LABEL_W, h - header_h),
            "columns": [
                _rect(COMPARISON_LABEL_W + i * col_w, header_h, col_w, h - header_h)
                for i in range(2)
            ],
            "row_h": (h - header_h) // 4,
            "rows": 4,
        }

    out["responsive"] = responsive_rules(w, h)
    return out


def responsive_rules(w: int, h: int) -> Dict[str, Any]:
    """How the module must behave when the viewport is narrower than the canvas.

    Amazon renders A+ inside a fixed 970 column on desktop; the module itself
    never reflows, it SCALES. On phones the column is ~360 px minus gutters, so
    the module scales to fit and must not letterbox (crop stays centred).
    """
    mobile_w = 360 - 2 * 16
    return {
        "desktop": {"width": w, "height": h, "scale": 1.0, "gutter": 0},
        "tablet": {"width": w, "height": h, "scale": round(min(1.0, 728 / w), 4), "gutter": 16},
        "mobile": {"width": w, "height": h, "scale": round(mobile_w / w, 4), "gutter": 16},
        "object_fit": "cover",
        "min_scale": 0.3,
    }


def crop_rect(src_w: int, src_h: int, box_w: int, box_h: int) -> Dict[str, Any]:
    """object-fit: cover maths - the largest centred source rect that fills box."""
    if min(src_w, src_h, box_w, box_h) <= 0:
        raise ValueError("crop_rect needs positive dimensions")
    box_ratio = box_w / box_h
    src_ratio = src_w / src_h
    if src_ratio > box_ratio:
        sh = src_h
        sw = int(round(src_h * box_ratio))
    else:
        sw = src_w
        sh = int(round(src_w / box_ratio))
    sx = (src_w - sw) // 2
    sy = (src_h - sh) // 2
    return {
        "source": _rect(sx, sy, sw, sh),
        "box": _rect(0, 0, box_w, box_h),
        "scale": round(box_w / sw, 4),
    }


def validate(module: Dict[str, Any]) -> List[str]:
    """Return problems. Empty list means the geometry is placeable."""
    problems: List[str] = []
    canvas = module.get("canvas") or {}
    cw, ch = int(canvas.get("w", 0)), int(canvas.get("h", 0))
    if cw <= 0 or ch <= 0:
        return ["canvas missing or zero-sized"]

    def check(name: str, rect: Dict[str, int]) -> None:
        x, y, w, h = (int(rect.get(k, 0)) for k in ("x", "y", "w", "h"))
        if w <= 0 or h <= 0:
            problems.append(f"{name}: non-positive size")
        if x < 0 or y < 0:
            problems.append(f"{name}: negative origin")
        if x + w > cw or y + h > ch:
            problems.append(f"{name}: overflows the canvas")

    for key in ("image", "safe", "copy"):
        if module.get(key):
            check(key, module[key])
    for i, tile in enumerate(module.get("tiles") or []):
        check(f"tile{i}", tile)

    comp = module.get("comparison")
    if comp:
        check("comparison.header", comp["header"])
        check("comparison.label_col", comp["label_col"])
        for i, col in enumerate(comp["columns"]):
            check(f"comparison.column{i}", col)
    return problems


def pixel_plan(kind: str, **kw: Any) -> Dict[str, Any]:
    """layout() + validate(), refusing to hand back broken geometry."""
    module = layout(kind, **kw)
    problems = validate(module)
    if problems:
        raise ValueError("; ".join(problems))
    module["valid"] = True
    return module


__all__ = ["CANVAS", "layout", "responsive_rules", "crop_rect", "validate", "pixel_plan"]
