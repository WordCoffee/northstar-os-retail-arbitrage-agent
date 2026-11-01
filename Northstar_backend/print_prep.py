"""Print prepress: 300 DPI validation + measured dieline sidecar.

The creative flow produces a MOCKUP render. That is honest for a listing image,
but a print hand-off needs numbers: the measured face quad, the physical face it
represents, the resulting pixels-per-millimetre, and whether the asset reaches
the 300 DPI target (300 / 25.4 = 11.811 px/mm).

`dpi_report` measures the quad the compositor actually used; `validate_print`
raises when a print-required job falls short; `emit_sidecar` writes the
`.dieline.json` beside the composited PNG with the quad, scale factors, colour
profile metadata and DPI metrics. No ICC transform is performed: the sidecar
declares the working RGB and the CMYK target, and says so.

Pure Python + numpy, no network.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np

TARGET_DPI = 300
PX_PER_MM = TARGET_DPI / 25.4          # 11.811...
SCHEMA = "northstar.dieline.v1"


class PrintDPIError(ValueError):
    """The measured face cannot reach the requested print resolution."""


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return float(np.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1])))


def face_pixels(quad: Sequence[Sequence[float]]) -> Dict[str, float]:
    """Width/height of a TL, TR, BR, BL quad (mean of opposite edges)."""
    if len(quad) != 4:
        raise ValueError("a dieline quad needs exactly four corners")
    tl, tr, br, bl = quad
    if not all(math.isfinite(float(c)) for point in quad for c in point):
        raise ValueError("dieline quad corners must be finite numbers")
    width = (_dist(tl, tr) + _dist(bl, br)) / 2.0
    height = (_dist(tl, bl) + _dist(tr, br)) / 2.0
    if width <= 0 or height <= 0:
        raise ValueError("dieline quad has zero or negative face dimensions")
    return {"width": round(width, 3), "height": round(height, 3)}


def physical_face(profile: Dict[str, Any]) -> Dict[str, float]:
    """The physical label/face the measured quad represents, in millimetres."""
    kind = str(profile.get("kind") or "").strip().lower()
    if kind == "box":
        face = profile.get("face") or {}
        if not face.get("w") or not face.get("h"):
            raise ValueError("box profile has no front-face dimensions")
        return {"width": float(face["w"]), "height": float(face["h"])}
    if kind == "pouch":
        return {"width": float(profile["width_mm"]),
                "height": float(profile["usable_height_mm"])}
    if kind == "bottle":
        width = profile.get("label_width_mm")
        if not width:
            width = (float(profile["diameter_mm"])
                     * float(profile.get("render_wrap_fraction") or 0.75))
        height = profile.get("label_height_mm") or profile["usable_height_mm"]
        return {"width": float(width), "height": float(height)}
    if kind == "tube":
        return {"width": float(profile["diameter_mm"]),
                "height": float(profile["usable_height_mm"])}
    raise KeyError(f"unknown packaging format {kind!r}")


def dpi_report(profile: Dict[str, Any], image_size: Sequence[int],
               quad: Sequence[Sequence[float]], *,
               target_dpi: int = TARGET_DPI) -> Dict[str, Any]:
    """Measure the face and report whether it reaches the print target."""
    px = face_pixels(quad)
    mm = physical_face(profile)
    px_per_mm_x = px["width"] / max(1e-9, mm["width"])
    px_per_mm_y = px["height"] / max(1e-9, mm["height"])
    dpi_x = px_per_mm_x * 25.4
    dpi_y = px_per_mm_y * 25.4
    required_x = mm["width"] * (float(target_dpi) / 25.4)
    required_y = mm["height"] * (float(target_dpi) / 25.4)
    worst = min(dpi_x, dpi_y)
    return {
        "target": int(target_dpi),
        "x": round(dpi_x, 2),
        "y": round(dpi_y, 2),
        "worst": round(worst, 2),
        "ok": bool(worst >= float(target_dpi) * 0.999),
        "px_per_mm": {"x": round(px_per_mm_x, 4), "y": round(px_per_mm_y, 4),
                      "target": round(float(target_dpi) / 25.4, 4)},
        "required_px": {"width": round(required_x, 1),
                        "height": round(required_y, 1)},
        "deficit_px": {
            "width": round(max(0.0, required_x - px["width"]), 1),
            "height": round(max(0.0, required_y - px["height"]), 1),
        },
        "image_size": [int(image_size[0]), int(image_size[1])],
    }


def validate_print(profile: Dict[str, Any], image_size: Sequence[int],
                   quad: Sequence[Sequence[float]], *,
                   target_dpi: int = TARGET_DPI) -> Dict[str, Any]:
    """Raise `PrintDPIError` when a print-required face is below target."""
    report = dpi_report(profile, image_size, quad, target_dpi=target_dpi)
    if not report["ok"]:
        raise PrintDPIError(
            f"print_dpi_below_target: {report['worst']:.1f} DPI at the measured "
            f"face (target {target_dpi}; deficit {report['deficit_px']['width']}x"
            f"{report['deficit_px']['height']} px). Render a larger plate or "
            "reduce the physical face before print hand-off.")
    return report


def _sha256(path: Optional[Path]) -> Optional[str]:
    if not path or not Path(path).is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def emit_sidecar(path: Path | str, *, kind: str, profile: Dict[str, Any],
                 image_size: Sequence[int], quad: Sequence[Sequence[float]],
                 method: str = "", residual_px: Optional[float] = None,
                 source_plate: Optional[Path | str] = None,
                 target_profile: str = "CMYK",
                 extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Write the `.dieline.json` sidecar beside a composited asset."""
    path = Path(path)
    px = face_pixels(quad)
    mm = physical_face(profile)
    report = dpi_report(profile, image_size, quad)
    data: Dict[str, Any] = {
        "schema": SCHEMA,
        "kind": str(kind),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "asset": {
            "image": path.name.replace(".dieline.json", ""),
            "image_size": [int(image_size[0]), int(image_size[1])],
        },
        "quad": [[round(float(x), 2), round(float(y), 2)] for x, y in quad],
        "face_px": px,
        "physical_mm": {"width": round(mm["width"], 3),
                        "height": round(mm["height"], 3)},
        "scale_factors": {
            "px_per_mm_x": report["px_per_mm"]["x"],
            "px_per_mm_y": report["px_per_mm"]["y"],
            "target_px_per_mm": report["px_per_mm"]["target"],
        },
        "dpi": report,
        "color_profile": {
            "working": "RGB",
            "target": target_profile,
            "icc": None,
            "note": "metadata only; no ICC transform is applied by this emitter",
        },
        "method": method,
        "residual_px": residual_px,
        "print_ready": report["ok"],
        "source_plate_sha256": _sha256(Path(source_plate) if source_plate else None),
        "notes": [
            "quad measured from the rendered plate, not a converter die drawing",
            "confirm panel geometry and bleed with the converter before print",
        ],
    }
    if extra:
        data.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


__all__ = ["PrintDPIError", "TARGET_DPI", "PX_PER_MM", "face_pixels",
           "physical_face", "dpi_report", "validate_print", "emit_sidecar"]
