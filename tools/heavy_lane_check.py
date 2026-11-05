"""Read-only readiness check for the heavy V3 model lanes.

It does not install or import the heavy stacks. It answers one question per
lane: are the packages, weights and runtime hooks present on this box? A lane
that is missing something is reported as blocked, never as ready.

    python tools/heavy_lane_check.py
    python tools/heavy_lane_check.py --out reports/heavy_lanes_readiness.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
COMFY = Path(r"C:\Users\T2Hol\ComfyUI")
INCOMING = COMFY / "models" / "_incoming"

LANES: Dict[str, Dict[str, Any]] = {
    "b2_layout_ocr": {
        "purpose": "Docling/Paddle layout + table structure for labels and dielines",
        "packages": ["docling", "paddleocr"],
        "weights": [],
        "nodes": [],
        "note": "Install in a staging venv first; it pulls a second OCR stack.",
    },
    "b3_relight": {
        "purpose": "IC-Light foreground relighting for product scenes",
        "packages": ["torch", "transformers"],
        "weights": [
            COMFY / "models" / "checkpoints" / "Realistic_Vision_V6.0_NV_B1_fp16.safetensors",
        ],
        "nodes": ["ComfyUI-IC-Light-Native"],
        "note": "SD15-class base + the IC-Light node; run after FLUX, never beside it.",
    },
    "b4_image_to_3d": {
        "purpose": "TRELLIS / InstantMesh image-to-mesh packshots",
        "packages": ["torch"],
        "weights": [
            Path(r"C:\Users\T2Hol\models\trellis\TRELLIS-image-large\model.safetensors"),
            Path(r"C:\Users\T2Hol\models\instantmesh\instantmesh.safetensors"),
        ],
        "nodes": [],
        "note": "No TRELLIS/InstantMesh weights on disk yet; 4B-class VRAM plan required.",
    },
    "video_a14b": {
        "purpose": "Wan 2.2 A14B chained 30 s master",
        "packages": ["torch"],
        "weights": [
            INCOMING / "QuantStack__Wan2.2-I2V-A14B-GGUF" / "HighNoise" / "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
            INCOMING / "QuantStack__Wan2.2-I2V-A14B-GGUF" / "LowNoise" / "Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf",
        ],
        "comfy_weights": [
            COMFY / "models" / "diffusion_models" / "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
            COMFY / "models" / "diffusion_models" / "Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf",
        ],
        "nodes": [],
        "note": "Weights are staged in _incoming; ComfyUI has no A14B graph and cannot see them.",
    },
}


def _package(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def check_lane(name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    missing_packages = [p for p in spec.get("packages") or [] if not _package(p)]
    missing_weights = [str(p) for p in spec.get("weights") or [] if not Path(p).is_file()]
    comfy_missing = [str(p) for p in spec.get("comfy_weights") or []
                     if not Path(p).is_file()]
    missing_nodes = [n for n in spec.get("nodes") or []
                     if not (COMFY / "custom_nodes" / n).is_dir()]
    integrated = not missing_packages and not missing_weights and not comfy_missing
    if missing_packages:
        status = "missing_packages"
    elif missing_weights or comfy_missing:
        status = "weights_not_installed"
    elif missing_nodes:
        status = "missing_nodes"
    else:
        status = "ready_for_validation"
    return {"lane": name, "purpose": spec.get("purpose"),
            "status": status, "integrated": integrated,
            "missing_packages": missing_packages,
            "missing_weights": missing_weights,
            "missing_comfy_weights": comfy_missing,
            "missing_nodes": missing_nodes, "note": spec.get("note")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    lanes = [check_lane(name, spec) for name, spec in LANES.items()]
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "comfy_root": str(COMFY),
        "lanes": lanes,
        "ready": [lane["lane"] for lane in lanes if lane["status"] == "ready_for_validation"],
        "blocked": [lane["lane"] for lane in lanes if lane["status"] != "ready_for_validation"],
    }
    if args.out:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ready": report["ready"], "blocked": report["blocked"],
                      "out": args.out or None}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
