"""Geometric invariants for a dieline build: refuse impossible geometry, never clamp.

A draft dieline that silently "fixes" a bad spec is worse than no dieline: the
drawing looks printable, the text sits outside the safe zone, and the error is
found at the converter. The older builders did exactly that - a safe margin
wider than the label was clamped to 0.5 mm, and negative panels produced a
self-intersecting outline without complaint.

This module is the single place those rules live:

    audit(build)          -> {"ok": bool, "violations": [{code, detail, mm}]}
    require_valid(build)  -> build, or DielineGeometryError carrying the codes
    art_boxes(build)      -> the rectangles artwork and type may occupy
    audit_artwork(build, box) -> containment check against those rectangles

Pure geometry, no network, no image libraries. Millimetres throughout, matching
the print engine's coordinate space where the origin is the bleed corner.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: A dieline with no bleed guarantees a white edge after trimming.
MIN_BLEED_MM = 0.5
#: Below this the safe zone and the trim are the same line.
MIN_SAFE_MM = 0.5
#: Smaller than this no converter will tool a die, and text cannot be legible.
MIN_FACE_MM = 10.0
#: Used for artwork when a build declares no safe margin (carton builders).
DEFAULT_SAFE_MM = 3.0
#: Coordinate comparisons are on rounded drawing values.
TOL = 0.02

Bounds = Tuple[float, float, float, float]


class DielineGeometryError(ValueError):
    """The requested geometry cannot be drawn without a defect."""

    def __init__(self, violations: Sequence[Dict[str, Any]]):
        self.violations = list(violations)
        codes = ", ".join(v["code"] for v in self.violations)
        first = self.violations[0]["detail"] if self.violations else "invalid geometry"
        super().__init__(f"dieline_geometry: {codes}: {first}")


def _violation(code: str, detail: str, **extra: Any) -> Dict[str, Any]:
    return {"code": code, "detail": detail, **extra}


def _element_bounds(el: Dict[str, Any]) -> Optional[Bounds]:
    kind = el.get("kind")
    if kind == "rect":
        return (float(el["x"]), float(el["y"]),
                float(el["x"]) + float(el["w"]), float(el["y"]) + float(el["h"]))
    if kind == "ellipse":
        cx, cy = float(el["cx"]), float(el["cy"])
        rx, ry = abs(float(el["rx"])), abs(float(el["ry"]))
        return (cx - rx, cy - ry, cx + rx, cy + ry)
    if kind == "line":
        xs = [float(el["x1"]), float(el["x2"])]
        ys = [float(el["y1"]), float(el["y2"])]
        return (min(xs), min(ys), max(xs), max(ys))
    return None  # text is a drafting note, not geometry


def _layer_bounds(build: Dict[str, Any], layer: str) -> Optional[Bounds]:
    boxes = [b for el in build.get("layers") or []
             if el.get("layer") == layer
             for b in [_element_bounds(el)] if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _inside(inner: Bounds, outer: Bounds, tol: float = TOL) -> bool:
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol
            and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def _face(build: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    trim = _layer_bounds(build, "trim")
    if trim is None:
        return None
    return (trim[2] - trim[0], trim[3] - trim[1])


def _panel_rects(panels: Any) -> Dict[str, Tuple[float, float, float, float]]:
    """Panel maps carry [x, y, w, h] rects (pouch) or scalars (annotations)."""
    if not isinstance(panels, dict):
        return {}
    out: Dict[str, Tuple[float, float, float, float]] = {}
    for name, value in panels.items():
        if isinstance(value, (list, tuple)) and len(value) == 4:
            try:
                out[str(name)] = tuple(float(v) for v in value)  # type: ignore[assignment]
            except (TypeError, ValueError):
                continue
    return out


def _audit_panel_rects(panels: Dict[str, Any], trim: Optional[Bounds]) -> List[Dict[str, Any]]:
    """A placed-panel map must stay on the sheet and must not overlap itself."""
    violations: List[Dict[str, Any]] = []
    rects = _panel_rects(panels)
    if not rects:
        return violations
    boxes: List[Tuple[str, Bounds]] = []
    for name, (x, y, w, h) in rects.items():
        if w <= 0 or h <= 0:
            violations.append(_violation(
                "panels_invalid", f"panel {name!r} is {w:.1f}x{h:.1f}mm"))
            continue
        box = (x, y, x + w, y + h)
        if trim and not _inside(box, trim):
            violations.append(_violation(
                "panel_outside_trim",
                f"panel {name!r} leaves the trim area at ({x:.1f},{y:.1f})-({x + w:.1f},{y + h:.1f})"))
        boxes.append((name, box))
    for i, (name_a, a) in enumerate(boxes):
        for name_b, b in boxes[i + 1:]:
            if (a[0] < b[2] - TOL and b[0] < a[2] - TOL
                    and a[1] < b[3] - TOL and b[1] < a[3] - TOL):
                violations.append(_violation(
                    "panels_overlap", f"panels {name_a!r} and {name_b!r} overlap on the sheet"))
    return violations


def audit(build: Dict[str, Any]) -> Dict[str, Any]:
    """Every invariant a printable dieline must satisfy, as data."""
    violations: List[Dict[str, Any]] = []
    meta = build.get("meta") or {}
    declared_bleed = meta.get("bleed_mm")
    face = _face(build)
    bleed = float(declared_bleed) if declared_bleed is not None else None
    safe = float(meta["safe_mm"]) if meta.get("safe_mm") is not None else None

    if face is None:
        violations.append(_violation("no_trim", "build has no trim layer to print to"))
        return {"ok": False, "violations": violations}

    width, height = face
    if min(width, height) < MIN_FACE_MM - TOL:
        violations.append(_violation(
            "face_below_min",
            f"trim face {width:.1f}x{height:.1f}mm is below the {MIN_FACE_MM}mm tooling floor",
            mm=round(min(width, height), 2)))

    if bleed is not None:
        if bleed < MIN_BLEED_MM - TOL:
            violations.append(_violation(
                "bleed_missing",
                f"bleed {bleed:.2f}mm is below the {MIN_BLEED_MM}mm minimum; "
                "trim tolerance would show the substrate",
                mm=round(bleed, 2)))
        if min(width, height) > 0 and bleed * 2 >= min(width, height):
            violations.append(_violation(
                "bleed_exceeds_face",
                f"bleed {bleed:.1f}mm on a {width:.1f}x{height:.1f}mm face leaves no face",
                mm=round(bleed, 2)))

    if safe is not None:
        if safe < MIN_SAFE_MM - TOL:
            violations.append(_violation(
                "safe_missing",
                f"safe margin {safe:.2f}mm leaves type on the trim line",
                mm=round(safe, 2)))
        elif safe * 2 >= min(width, height):
            violations.append(_violation(
                "safe_inverted",
                f"safe margin {safe:.1f}mm inverts on a {width:.1f}x{height:.1f}mm face",
                mm=round(safe, 2)))

    trim = _layer_bounds(build, "trim")
    safe_box = _layer_bounds(build, "safe")
    if safe_box and trim and not _inside(safe_box, trim):
        violations.append(_violation(
            "safe_outside_trim",
            "the safe layer leaves the trim area, so its inset is not a margin"))

    build_box = _layer_bounds(build, "bleed") or (0.0, 0.0, float(build.get("width_mm") or 0),
                                                 float(build.get("height_mm") or 0))
    for el in build.get("layers") or []:
        if el.get("layer") in ("info", "marks"):
            continue
        box = _element_bounds(el)
        if box and not _inside(box, build_box):
            violations.append(_violation(
                "element_outside_bleed",
                f"{el.get('layer')} {el.get('kind')} leaves the bleed box "
                f"({box[0]:.1f},{box[1]:.1f})-({box[2]:.1f},{box[3]:.1f})"))
            break

    panels = meta.get("panels")
    if isinstance(panels, dict):
        violations.extend(_audit_panel_rects(panels, trim))
    elif panels is not None:
        bad = [p for p in panels if float(p) <= 0]
        if bad or not panels:
            violations.append(_violation(
                "panels_invalid",
                f"panel widths must all be positive, got {list(panels)}"))
        body_h = meta.get("body_h")
        if body_h is not None:
            body_h = float(body_h)
            if body_h <= 0:
                violations.append(_violation(
                    "body_height_invalid", f"body height {body_h}mm must be positive"))
            else:
                for key in ("top_depths", "bottom_depths"):
                    depths = [float(d) for d in (meta.get(key) or [])]
                    deepest = max(depths) if depths else 0.0
                    if deepest >= body_h:
                        violations.append(_violation(
                            "tab_deeper_than_body",
                            f"{key} reach {deepest:.1f}mm on a {body_h:.1f}mm body; "
                            "the flap would fold past the opposite edge",
                            mm=round(body_h, 2)))

    return {"ok": not violations, "violations": violations}


def require_valid(build: Dict[str, Any]) -> Dict[str, Any]:
    """`audit` as a refusal. Builders call this before returning a drawing."""
    report = audit(build)
    if not report["ok"]:
        raise DielineGeometryError(report["violations"])
    return build


def _trim_rect(build: Dict[str, Any]) -> Optional[Bounds]:
    return _layer_bounds(build, "trim")


def art_boxes(build: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Where artwork and type are allowed to live.

    Labels get one box; a folded blank gets one box per panel body, because type
    that crosses a fold is creased, not "flowing". Each box is the panel inset by
    the declared safe margin (or the default, reported as such).
    """
    trim = _trim_rect(build)
    if trim is None:
        return []
    meta = build.get("meta") or {}
    safe_declared = meta.get("safe_mm")
    safe = float(safe_declared) if safe_declared is not None else DEFAULT_SAFE_MM
    source = "declared" if safe_declared is not None else "default"

    panels = meta.get("panels")
    if isinstance(panels, dict):
        boxes: List[Dict[str, Any]] = []
        for name, (x, y, w, h) in _panel_rects(panels).items():
            box = {"x": round(x + safe, 2), "y": round(y + safe, 2),
                   "w": round(max(0.0, w - 2 * safe), 2),
                   "h": round(max(0.0, h - 2 * safe), 2)}
            if box["w"] > 0 and box["h"] > 0:
                boxes.append({**box, "safe_mm": round(safe, 2), "safe_source": source,
                              "panel": name})
        return boxes
    if not panels:
        return [{"x": round(trim[0] + safe, 2), "y": round(trim[1] + safe, 2),
                 "w": round(max(0.0, (trim[2] - trim[0]) - 2 * safe), 2),
                 "h": round(max(0.0, (trim[3] - trim[1]) - 2 * safe), 2),
                 "safe_mm": round(safe, 2), "safe_source": source, "panel": 0}]

    body_h = float(meta.get("body_h") or (trim[3] - trim[1]))
    top = max([float(d) for d in (meta.get("top_depths") or [])] or [0.0])
    y0 = trim[1] + top + safe
    y1 = trim[1] + top + body_h - safe
    boxes: List[Dict[str, Any]] = []
    x = trim[0]
    for i, width in enumerate(float(p) for p in panels):
        boxes.append({"x": round(x + safe, 2), "y": round(y0, 2),
                      "w": round(max(0.0, float(width) - 2 * safe), 2),
                      "h": round(max(0.0, y1 - y0), 2),
                      "safe_mm": round(safe, 2), "safe_source": source, "panel": i})
        x += float(width)
    return boxes


def audit_artwork(build: Dict[str, Any], box: Dict[str, float]) -> Dict[str, Any]:
    """Refuse an artwork rect that leaves the safe area or straddles a fold."""
    boxes = art_boxes(build)
    if not boxes:
        return {"ok": False, "violations": [_violation("no_trim", "no safe area to place into")]}
    inner = (float(box["x"]), float(box["y"]),
             float(box["x"]) + float(box["w"]), float(box["y"]) + float(box["h"]))
    for allowed in boxes:
        outer = (allowed["x"], allowed["y"],
                 allowed["x"] + allowed["w"], allowed["y"] + allowed["h"])
        if _inside(inner, outer):
            return {"ok": True, "panel": allowed["panel"], "safe_mm": allowed["safe_mm"],
                    "safe_source": allowed["safe_source"], "violations": []}
    return {"ok": False, "violations": [_violation(
        "artwork_outside_safe",
        f"artwork ({inner[0]:.1f},{inner[1]:.1f})-({inner[2]:.1f},{inner[3]:.1f}) "
        f"does not fit any of the {len(boxes)} safe panel(s)")]}


def panel_fold_mm(build: Dict[str, Any]) -> List[float]:
    """Absolute x of each vertical fold, for drawing and for tests."""
    trim = _trim_rect(build)
    panels = (build.get("meta") or {}).get("panels")
    if trim is None or not panels:
        return []
    folds: List[float] = []
    x = trim[0]
    for width in [float(p) for p in panels][:-1]:
        x += width
        folds.append(round(x, 2))
    return folds


__all__ = ["DielineGeometryError", "audit", "require_valid", "art_boxes",
           "audit_artwork", "panel_fold_mm",
           "MIN_BLEED_MM", "MIN_FACE_MM", "DEFAULT_SAFE_MM"]
