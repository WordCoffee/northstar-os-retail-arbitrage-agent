"""Perceptual image diff for the visual regression gate.

The metric has to do two jobs that pull in opposite directions:

* catch a real change — an element moves, a colour changes, a price changes —
  even when that change is small in area;
* ignore antialiasing — the same page rendered 0.3 px lower, or with a slightly
  different subpixel phase, is not a regression.

Raw pixel diffs fail the second job: the *edge* of every glyph changes at full
contrast for a half-pixel shift. Raising the threshold until they pass makes the
first job impossible. So the comparison is envelope-based instead:

    for every pixel of the BASELINE, take the minimum and maximum of that
    channel over a 3x3 neighbourhood; the CANDIDATE pixel passes if it lies
    inside [min - tolerance, max + tolerance].

A ±1 px re-render of the baseline therefore lands inside the envelope, while a
colour change, a 28 px move, or different glyphs do not. Both images are
Gaussian-blurred (radius 0.8) first, which removes single-pixel sensor-style
noise without moving any edge.

Verdict rules, in order:

1. different dimensions            -> fail (``size_mismatch``)
2. changed area > ``max_pixel_ratio`` of the frame -> fail
3. any 8x8 block cluster holding >= ``min_region_px`` changed pixels -> fail

Rule 3 is what catches a text change: one digit can be 40 changed pixels and
0.03 % of a 1440x900 frame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter


@dataclass(frozen=True)
class DiffConfig:
    """Thresholds. Frozen so a run is reproducible from the report alone."""

    pre_blur: float = 0.8
    tolerance: int = 12
    block: int = 8
    block_min_pixels: int = 3
    min_region_px: int = 30
    max_pixel_ratio: float = 0.004


DEFAULT_CONFIG = DiffConfig()


@dataclass(frozen=True)
class DiffResult:
    verdict: str  # "pass" | "fail"
    reason: str  # "unchanged" | "structural_change" | "size_mismatch"
    pixel_diff_ratio: float
    changed_pixels: int
    changed_blocks: int
    cluster_pixels: int
    total_pixels: int
    bbox: Optional[Tuple[int, int, int, int]] = None
    config: DiffConfig = field(default=DEFAULT_CONFIG)

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "pixel_diff_ratio": round(self.pixel_diff_ratio, 6),
            "changed_pixels": self.changed_pixels,
            "changed_blocks": self.changed_blocks,
            "cluster_pixels": self.cluster_pixels,
            "total_pixels": self.total_pixels,
            "bbox": list(self.bbox) if self.bbox else None,
            "config": self.config.__dict__,
        }


def load_rgb(path: str | Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGB")


def _envelope(channel: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """3x3 min/max envelope of one channel (edge-padded, no scipy)."""
    padded = np.pad(channel, 1, mode="edge")
    h, w = channel.shape
    lo = channel.copy()
    hi = channel.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nb = padded[1 + dy : 1 + dy + h, 1 + dx : 1 + dx + w]
            np.minimum(lo, nb, out=lo)
            np.maximum(hi, nb, out=hi)
    return lo, hi


def compare_images(
    baseline: Image.Image,
    candidate: Image.Image,
    config: DiffConfig = DEFAULT_CONFIG,
) -> DiffResult:
    base = baseline.convert("RGB")
    cand = candidate.convert("RGB")
    if base.size != cand.size:
        return DiffResult(
            verdict="fail",
            reason="size_mismatch",
            pixel_diff_ratio=1.0,
            changed_pixels=base.size[0] * base.size[1],
            changed_blocks=0,
            cluster_pixels=base.size[0] * base.size[1],
            total_pixels=base.size[0] * base.size[1],
            config=config,
        )

    a = np.asarray(base.filter(ImageFilter.GaussianBlur(config.pre_blur)), dtype=np.float32)
    b = np.asarray(cand.filter(ImageFilter.GaussianBlur(config.pre_blur)), dtype=np.float32)

    mask = np.zeros(a.shape[:2], dtype=bool)
    for channel in range(3):
        lo, hi = _envelope(a[:, :, channel])
        mask |= (b[:, :, channel] > hi + config.tolerance) | (
            b[:, :, channel] < lo - config.tolerance
        )

    total = int(mask.size)
    changed = int(mask.sum())
    ratio = changed / total if total else 0.0

    h, w = mask.shape
    block = max(1, int(config.block))
    bh, bw = h // block, w // block
    if bh and bw:
        pooled = mask[: bh * block, : bw * block].reshape(bh, block, bw, block).sum(axis=(1, 3))
        changed_blocks = int((pooled >= config.block_min_pixels).sum())
        cluster_pixels = int(pooled[pooled >= config.block_min_pixels].sum())
    else:
        changed_blocks = 0
        cluster_pixels = 0

    bbox: Optional[Tuple[int, int, int, int]] = None
    if changed:
        rows = np.flatnonzero(mask.any(axis=1))
        cols = np.flatnonzero(mask.any(axis=0))
        bbox = (int(cols[0]), int(rows[0]), int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1))

    failed = ratio > config.max_pixel_ratio or cluster_pixels >= config.min_region_px
    return DiffResult(
        verdict="fail" if failed else "pass",
        reason="structural_change" if failed else "unchanged",
        pixel_diff_ratio=ratio,
        changed_pixels=changed,
        changed_blocks=changed_blocks,
        cluster_pixels=cluster_pixels,
        total_pixels=total,
        bbox=bbox,
        config=config,
    )


def compare_files(
    baseline_path: str | Path,
    candidate_path: str | Path,
    config: DiffConfig = DEFAULT_CONFIG,
) -> DiffResult:
    return compare_images(load_rgb(baseline_path), load_rgb(candidate_path), config)


def write_diff_artifact(
    baseline_path: str | Path,
    candidate_path: str | Path,
    out_path: str | Path,
    config: DiffConfig = DEFAULT_CONFIG,
) -> None:
    """Write a greyscale heat-map of the changed pixels (evidence, not input)."""
    a = load_rgb(baseline_path)
    b = load_rgb(candidate_path)
    if a.size != b.size:
        Image.new("L", a.size, 255).save(out_path)
        return
    diff = np.abs(
        np.asarray(a.filter(ImageFilter.GaussianBlur(config.pre_blur)), dtype=np.float32)
        - np.asarray(b.filter(ImageFilter.GaussianBlur(config.pre_blur)), dtype=np.float32)
    ).max(axis=2)
    scaled = np.clip(diff * 4.0, 0, 255).astype(np.uint8)
    Image.fromarray(scaled, mode="L").save(out_path)
