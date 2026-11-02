"""Print master: upscale a render to a real 300 DPI physical size, or refuse.

A 1024 px render is a screen asset. A printer asks two numbers: physical size and
pixels per inch at that size. This module runs the installed Real-ESRGAN 4x
upscaler through ComfyUI, then measures the result with the same DPI arithmetic
the prepress gate already uses (`print_prep.dpi_report`), and refuses when the
master still cannot reach the target instead of calling a blurry file "print
ready".

No fabrication: the report states the source size, the factor actually applied,
the measured DPI at the requested physical size, and the shortfall in pixels.
The manifest ships with the artwork so the number travels with the file.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

import print_prep

DELIVERABLES = Path(__file__).resolve().parents[1] / "state" / "deliverables"
UPSCALE_MODEL = "RealESRGAN_x4plus.pth"
FACTOR = 4


class PrintMasterShortfall(ValueError):
    """The master cannot reach the target DPI at the requested physical size."""

    def __init__(self, report: Dict[str, Any], needed_factor: float):
        self.report = report
        self.needed_factor = needed_factor
        super().__init__(
            f"print_master_shortfall: {report['worst']:.1f} DPI at the requested size "
            f"(target {report['target']}); a {needed_factor:.2f}x source would be needed")


#: The installed x4 model aborted the ComfyUI process on a 1216 px input (recorded
#: in design_studio_lanes.py). A 1024 px source was measured working end to end on
#: 2026-11-02 (1024 -> 4096 in 6.4 s), so the lane accepts up to that and refuses
#: larger with the reason instead of risking the shared engine.
MAX_MODEL_INPUT_PX = 1024


def check_source_size(size: Sequence[int]) -> None:
    longest = max(int(size[0]), int(size[1]))
    if longest > MAX_MODEL_INPUT_PX:
        raise ValueError(
            f"print_master_source_too_large: {longest}px exceeds the {MAX_MODEL_INPUT_PX}px "
            "ceiling for the installed x4 model (a 1216px input aborted ComfyUI once). "
            "Downscale the source first or run the prepress check instead.")


def _safe(run_id: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", str(run_id or "")).strip("._")
    return base[:80] or f"print_{int(time.time())}"


def _graph(image_name: str, filename_prefix: str) -> Dict[str, Any]:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UpscaleModelLoader",
              "inputs": {"model_name": UPSCALE_MODEL}},
        "3": {"class_type": "ImageUpscaleWithModel",
              "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "SaveImage",
              "inputs": {"images": ["3", 0], "filename_prefix": filename_prefix}},
    }


def upscale(png: bytes, *, timeout_s: float = 900.0) -> bytes:
    """Run Real-ESRGAN 4x on the operator's ComfyUI. Local only."""
    import studio_generation as sg

    if not sg.media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    name = sg.upload_image(png, filename=f"ns_master_{int(time.time())}.png")
    files = sg._run_graph(_graph(name, f"ns_print_master_{int(time.time())}"), timeout_s)
    if not files:
        raise RuntimeError("the upscaler returned no file")
    return sg._fetch_output(files[0])


def master_report(master_px: Sequence[int], *, width_mm: float, height_mm: float,
                  target_dpi: int = print_prep.TARGET_DPI) -> Dict[str, Any]:
    """Measured DPI of the master at the requested physical size."""
    w, h = int(master_px[0]), int(master_px[1])
    profile = {"kind": "box", "face": {"w": float(width_mm), "h": float(height_mm)}}
    quad = [[0, 0], [w, 0], [w, h], [0, h]]
    report = print_prep.dpi_report(profile, [w, h], quad, target_dpi=target_dpi)
    report["physical_mm"] = {"width": round(float(width_mm), 2),
                             "height": round(float(height_mm), 2)}
    return report


def _needed_factor(report: Dict[str, Any]) -> float:
    worst = float(report.get("worst") or 0.0)
    target = float(report.get("target") or 300)
    if worst <= 0:
        return float("inf")
    return target / worst


def make_master(png: bytes, *, width_mm: float, height_mm: float,
                target_dpi: int = print_prep.TARGET_DPI,
                upscaler: Optional[Callable[[bytes], bytes]] = None) -> Dict[str, Any]:
    """Upscale, measure, and refuse if the result still misses the target."""
    if float(width_mm) <= 0 or float(height_mm) <= 0:
        raise ValueError("width_mm and height_mm must be positive")
    from PIL import Image
    import io

    with Image.open(io.BytesIO(png)) as im:
        source_size = [im.width, im.height]
    check_source_size(source_size)

    run = upscaler or upscale
    master = run(png)
    with Image.open(io.BytesIO(master)) as im:
        master_size = [im.width, im.height]

    report = master_report(master_size, width_mm=width_mm, height_mm=height_mm,
                           target_dpi=target_dpi)
    if not report["ok"]:
        raise PrintMasterShortfall(report, _needed_factor(report))
    return {"png": master, "source_size": source_size, "size": master_size,
            "factor": round(master_size[0] / max(1, source_size[0]), 2),
            "report": report}


def package(master: Dict[str, Any], *, run_id: str, asset_id: Optional[str] = None,
            out_root: Optional[Path] = None) -> Dict[str, Any]:
    """Write the master and its measured report as one deliverable folder."""
    root = Path(out_root) if out_root else DELIVERABLES
    folder = root / _safe(run_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "master.png").write_bytes(master["png"])
    report = master["report"]
    manifest: Dict[str, Any] = {
        "run_id": _safe(run_id),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "print_master",
        "source_size": list(master["source_size"]),
        "master_size": list(master["size"]),
        "factor": master["factor"],
        "physical_mm": report["physical_mm"],
        "dpi": {k: report[k] for k in ("target", "x", "y", "worst", "ok",
                                       "required_px", "deficit_px")},
        "dieline": {
            "built": True,
            "reason": ("physical face declared by the caller; the master is the "
                       "artwork for that face, not a converter die"),
            "face_mm": report["physical_mm"],
        },
        "color_profile": {"working": "RGB", "target": "CMYK", "converted": False,
                          "note": "run the prepress ICC check before hand-off"},
        "files": ["master.png", "manifest.json"],
    }
    if asset_id:
        manifest["asset_id"] = asset_id
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"folder": str(folder), "manifest": manifest, "report": report}


__all__ = ["PrintMasterShortfall", "upscale", "master_report", "make_master",
           "package", "UPSCALE_MODEL", "FACTOR"]
