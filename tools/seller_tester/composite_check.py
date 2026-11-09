"""Did the composite actually use the real product? Compare the product region.

A composite is only worth anything if the product pixels in the output are the product pixels
from the upload. Colour histograms and text cannot prove that — a different pouch with the same
brand colours and the same brand text would pass both. So this compares the **region the product
occupies** against the source cutout, masked by its alpha.

Two ways to find the region:

* the generator recorded where it placed the product (`placement`) — direct, exact;
* it did not — template match the cutout against the output on a downscaled grid, then verify at
  full size. Slower, and a miss is `cannot_verify`, never a pass.

The score is mean absolute error over the opaque pixels only, normalised to 0..1. Shadow and
lighting compositing is expected to move pixels slightly, so the default bar is 0.82; a wrong
product scores far below it and the report shows the number.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

DEFAULT_MIN_SIMILARITY = 0.82
ALPHA_THRESHOLD = 0.5
SEARCH_MAX_EDGE = 640


def _check(**kw: Any) -> Dict[str, Any]:
    kw.setdefault("skipped", False)
    kw.setdefault("cannot_verify", False)
    kw["ok"] = bool(kw.get("ok", False))
    kw["check"] = "product_region"
    return kw


def _cannot_verify(reason: str, **extra: Any) -> Dict[str, Any]:
    return _check(ok=False, cannot_verify=True, detail=f"cannot verify: {reason}", **extra)


def split_rgba(cutout: Any) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """(rgb, alpha) from an RGBA/RGB array. Alpha is None when the picture has no channel."""
    array = np.asarray(cutout)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        return None, None
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    rgb = array[:, :, :3]
    alpha = array[:, :, 3].astype(np.float32) / 255.0 if array.shape[2] == 4 else None
    return rgb, alpha


def region_similarity(produced_rgb: np.ndarray, cutout_rgb: np.ndarray,
                      cutout_alpha: np.ndarray,
                      placement: Sequence[int]) -> Dict[str, Any]:
    """Compare the placed region with the cutout, over opaque pixels only."""
    x, y, width, height = (int(value) for value in placement)
    frame_h, frame_w = produced_rgb.shape[:2]
    if width <= 0 or height <= 0:
        return _cannot_verify(f"placement has no area ({placement})")
    if x < 0 or y < 0 or x + width > frame_w or y + height > frame_h:
        return _cannot_verify(
            f"placement {placement} falls outside the {frame_w}x{frame_h} frame")

    region = produced_rgb[y:y + height, x:x + width].astype(np.float32)
    cutout = cutout_rgb.astype(np.float32)
    if cutout.shape[:2] != region.shape[:2]:
        return _cannot_verify(
            f"cutout is {cutout.shape[1]}x{cutout.shape[0]} but the placement is "
            f"{width}x{height}; resize the cutout before comparing")

    mask = cutout_alpha >= ALPHA_THRESHOLD if cutout_alpha is not None else \
        np.ones(region.shape[:2], dtype=bool)
    if int(mask.sum()) < 64:
        return _cannot_verify("the cutout is almost entirely transparent")

    difference = np.abs(region - cutout).max(axis=2)[mask]
    mae = float(difference.mean()) / 255.0
    score = max(0.0, 1.0 - mae)
    return _check(
        ok=True, cannot_verify=False, similarity=round(score, 4),
        pixels=int(mask.sum()), placement=[x, y, width, height],
        detail=(f"product region {width}x{height} at ({x},{y}): "
                f"similarity {score:.3f} over {int(mask.sum())} opaque pixels"))


def locate_and_compare(produced_rgb: np.ndarray, cutout: Any,
                       *, min_similarity: float = DEFAULT_MIN_SIMILARITY
                       ) -> Dict[str, Any]:
    """Find the cutout in the output, then compare it. No placement needed."""
    cutout_rgb, cutout_alpha = split_rgba(cutout)
    if cutout_rgb is None:
        return _cannot_verify("the cutout is not an RGB or RGBA image")

    try:
        import cv2  # noqa: PLC0415 - optional at import time
    except Exception as exc:  # noqa: BLE001
        return _cannot_verify(f"OpenCV is unavailable ({type(exc).__name__})")

    frame = np.asarray(produced_rgb)
    if frame.ndim != 3:
        return _cannot_verify("the produced picture is not colour")

    scale = min(1.0, SEARCH_MAX_EDGE / float(max(frame.shape[:2])))
    if scale < 1.0:
        size = (max(1, int(frame.shape[1] * scale)), max(1, int(frame.shape[0] * scale)))
        small_frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    else:
        small_frame = frame

    if cutout_alpha is None:
        mask = None
    else:
        mask = (cutout_alpha >= ALPHA_THRESHOLD).astype(np.uint8)
        if int(mask.sum()) < 64:
            return _cannot_verify("the cutout is almost entirely transparent")

    search = small_frame.astype(np.float32)
    template = cutout_rgb.astype(np.float32)
    if template.shape[0] > search.shape[0] or template.shape[1] > search.shape[1]:
        return _cannot_verify("the cutout is larger than the produced picture")

    try:
        if mask is not None:
            result = cv2.matchTemplate(search, template, cv2.TM_CCORR_NORMED,
                                       mask=mask.astype(np.float32))
        else:
            result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    except Exception as exc:  # noqa: BLE001
        return _cannot_verify(f"template match failed ({type(exc).__name__}: {exc})")

    result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
    _, best, _, best_loc = cv2.minMaxLoc(result)
    if best <= 0.0:
        return _cannot_verify("the cutout does not appear anywhere in the produced picture",
                              best_match=round(float(best), 4))

    x = int(round(best_loc[0] / scale))
    y = int(round(best_loc[1] / scale))
    width = int(round(template.shape[1] / scale))
    height = int(round(template.shape[0] / scale))
    verdict = region_similarity(np.asarray(produced_rgb), cutout_rgb, cutout_alpha,
                               [x, y, width, height])
    verdict["found_by"] = "template_match"
    verdict["match_score"] = round(float(best), 4)
    verdict["min_similarity"] = float(min_similarity)
    if not verdict.get("cannot_verify"):
        verdict["ok"] = bool(verdict.get("similarity", 0.0) >= float(min_similarity))
    return verdict


def check_composite(produced_rgb: np.ndarray, cutout: Any, *,
                    placement: Optional[Sequence[int]] = None,
                    min_similarity: float = DEFAULT_MIN_SIMILARITY) -> Dict[str, Any]:
    """The one entry point: use the recorded placement, or find the product."""
    if placement is not None:
        cutout_rgb, cutout_alpha = split_rgba(cutout)
        if cutout_rgb is None:
            return _cannot_verify("the cutout is not an RGB or RGBA image")
        verdict = region_similarity(np.asarray(produced_rgb), cutout_rgb, cutout_alpha,
                                    placement)
        verdict["found_by"] = "placement"
        verdict["min_similarity"] = float(min_similarity)
        if not verdict.get("cannot_verify"):
            verdict["ok"] = bool(verdict.get("similarity", 0.0) >= float(min_similarity))
        return verdict
    return locate_and_compare(np.asarray(produced_rgb), cutout,
                              min_similarity=min_similarity)


__all__ = ["DEFAULT_MIN_SIMILARITY", "check_composite", "locate_and_compare",
           "region_similarity", "split_rgba"]
