"""Resolve wave-2 source coordinates (3D, segmentation, OCR backbones).

Same contract as wave 1: licence, branch, HEAD commit, matching paths. No file
contents are copied.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import expansion_blueprint_sources as ebs  # noqa: E402

ebs.OUT = ROOT / "state" / "evidence" / "expansion_wave2_20261104" / "blueprint_sources_wave2.json"
ebs.REPOS = {
    "microsoft/TRELLIS": ["trellis", "pipeline", "render", "mesh"],
    "TencentARC/InstantMesh": ["system", "mesh", "export", "render"],
    "facebookresearch/sam2": ["sam2", "predictor", "mask"],
    "LiheYoung/depth-anything": ["depth", "infer", "metric"],
    "microsoft/table-transformer": ["structure", "detection", "inference"],
    "clovaai/donut": ["model", "inference", "document"],
}

if __name__ == "__main__":
    raise SystemExit(ebs.main())
