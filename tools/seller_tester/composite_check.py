"""Did the composite actually use the real product? Compare the product region.

A composite is only worth anything if the product pixels in the output are the product pixels
from the upload. Colour histograms and text cannot prove that — a different pouch with the same
brand colours and the same brand text would pass both. So this compares the **region the product
occupies** against the source cutout, masked by its alpha.

Two ways to find the region:

* the generator recorded where it placed the product (`placement`) — direct, exact;
* it did not — template match the cutout against the output on a downscaled grid, then verify at
  full size. Slower, and a miss is `cannot_verify`, never a pass.

The score is normalised cross-correlation over opaque pixels (MAE is a diagnostic), because a
composite applies a scene grade and a shadow: structure survives that, absolute colour does not.
The default bar is 0.82; a wrong product scores far below it and the report shows the number.

**A product region that cannot be verified is a failure, never a skip.** The owner's rule
(2026-11-08): `cannot_verify` is a fail. Every refusal here therefore says
`product region cannot be verified: <why>` and carries `ok: False`, so a caller that only
looks at `ok` still fails it.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

DEFAULT_MIN_SIMILARITY = 0.82
ALPHA_THRESHOLD = 0.5
SEARCH_MAX_EDGE = 1280


def _check(**kw: Any) -> Dict[str, Any]:
    kw.setdefault("skipped", False)
    kw.setdefault("cannot_verify", False)
    kw["ok"] = bool(kw.get("ok", False))
    kw["check"] = "product_region"
    return kw


def _cannot_verify(reason: str, **extra: Any) -> Dict[str, Any]:
    return _check(ok=False, cannot_verify=True,
                  detail=f"product region cannot be verified: {reason}", **extra)


def missing_cutout_verdict(reason: str) -> Dict[str, Any]:
    """The verdict when there is nothing to compare against — a named failure, not a skip."""
    return _cannot_verify(reason, check="product_region")


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
    # No trimming here: a recorded placement refers to the cutout's own canvas (that is what the
    # generator pasted), so trimming the cutout to its subject would compare an 80x80 subject
    # against a 120x120 box and report a mismatch that is only geometry.
    cutout = cutout_rgb.astype(np.float32)
    distortion = 1.0
    if cutout.shape[:2] != region.shape[:2]:
        # The generator resizes the cutout to the placement, so compare at the geometry it
        # actually used. A wild aspect change means the box is not this product, and that is
        # reported rather than silently stretched away.
        cut_aspect = cutout.shape[1] / float(cutout.shape[0])
        box_aspect = width / float(height)
        distortion = max(cut_aspect, box_aspect) / min(cut_aspect, box_aspect)
        if distortion > 1.25:
            return _cannot_verify(
                f"cutout aspect {cut_aspect:.2f} and placement aspect {box_aspect:.2f} "
                f"differ by {distortion:.2f}x; this is not the same subject")
        try:
            import cv2  # noqa: PLC0415

            cutout = cv2.resize(cutout, (region.shape[1], region.shape[0]),
                                interpolation=cv2.INTER_AREA)
            if cutout_alpha is not None:
                cutout_alpha = cv2.resize(cutout_alpha, (region.shape[1], region.shape[0]),
                                          interpolation=cv2.INTER_AREA)
        except Exception as exc:  # noqa: BLE001
            return _cannot_verify(f"could not align the cutout ({type(exc).__name__})")

    mask = cutout_alpha >= ALPHA_THRESHOLD if cutout_alpha is not None else \
        np.ones(region.shape[:2], dtype=bool)
    if mask.shape[:2] != region.shape[:2]:
        # Coerce: a mismatch here is a rounding path, never a reason to crash the audit.
        try:
            import cv2  # noqa: PLC0415

            cutout = cv2.resize(cutout, (region.shape[1], region.shape[0]),
                                interpolation=cv2.INTER_AREA)
            if cutout_alpha is not None:
                cutout_alpha = cv2.resize(cutout_alpha, (region.shape[1], region.shape[0]),
                                          interpolation=cv2.INTER_AREA)
                mask = cutout_alpha >= ALPHA_THRESHOLD
            else:
                mask = np.ones(region.shape[:2], dtype=bool)
        except Exception as exc:  # noqa: BLE001
            return _cannot_verify(f"could not align the cutout ({type(exc).__name__})")
    if int(mask.sum()) < 64:
        return _cannot_verify("the cutout is almost entirely transparent")

    difference = np.abs(region - cutout).max(axis=2)[mask]
    mae = float(difference.mean()) / 255.0

    # Structure, not exposure. A composite applies a scene grade and a shadow, which shifts
    # every channel; normalised cross-correlation (zero-mean Pearson) is invariant to that and
    # is what "the same product" actually means. MAE stays as a diagnostic.
    left = region[mask].reshape(-1)
    right = cutout[mask].reshape(-1)
    left = left - left.mean()
    right = right - right.mean()
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-9:
        # A flat-coloured subject has no structure to correlate; colour agreement is then
        # the only evidence there is, and it is reported as such.
        score = max(0.0, 1.0 - mae)
        basis = "colour_only"
    else:
        score = max(0.0, min(1.0, float(np.dot(left, right) / denominator)))
        basis = "structure"
    return _check(
        ok=True, cannot_verify=False, similarity=round(score, 4),
        basis=basis, aspect_distortion=round(distortion, 3),
        mae_similarity=round(max(0.0, 1.0 - mae), 4),
        pixels=int(mask.sum()), placement=[x, y, width, height],
        detail=(f"product region {width}x{height} at ({x},{y}): "
                f"{basis} {score:.3f} over {int(mask.sum())} opaque pixels "
                f"(mean-abs {1 - mae:.3f})"))


def locate_and_compare(produced_rgb: np.ndarray, cutout: Any,
                       *, min_similarity: float = DEFAULT_MIN_SIMILARITY
                       ) -> Dict[str, Any]:
    """Find the cutout in the output, then compare it. No placement needed."""
    cutout_rgb, cutout_alpha = split_rgba(cutout)
    if cutout_rgb is None:
        return _cannot_verify("the cutout is not an RGB or RGBA image")

    # Crop to the subject. A cutout is usually a full canvas with an alpha matte, so its
    # bounding box is the whole image; matching that template can never fit inside a frame
    # that shows the product smaller than the reference canvas.
    if cutout_alpha is not None:
        rows, columns = np.where(cutout_alpha >= ALPHA_THRESHOLD)
        if rows.size >= 64:
            top, bottom = int(rows.min()), int(rows.max()) + 1
            left, right = int(columns.min()), int(columns.max()) + 1
            cutout_rgb = cutout_rgb[top:bottom, left:right]
            cutout_alpha = cutout_alpha[top:bottom, left:right]

    try:
        import cv2  # noqa: PLC0415 - optional at import time
    except Exception as exc:  # noqa: BLE001
        return _cannot_verify(f"OpenCV is unavailable ({type(exc).__name__})")

    frame = np.asarray(produced_rgb)
    if frame.ndim != 3:
        return _cannot_verify("the produced picture is not colour")

    # Multi-scale search on grayscale structure. A single scale cannot find a product that
    # the composite scaled down, and a masked correlation over a near-frame-sized template
    # returns nonsense; normalised cross-correlation over a few candidate scales does not.
    scale_down = min(1.0, SEARCH_MAX_EDGE / float(max(frame.shape[:2])))
    search_frame = frame
    if scale_down < 1.0:
        search_frame = cv2.resize(
            frame, (max(1, int(frame.shape[1] * scale_down)),
                    max(1, int(frame.shape[0] * scale_down))),
            interpolation=cv2.INTER_AREA)
    search_gray = cv2.cvtColor(search_frame.astype(np.uint8),
                               cv2.COLOR_RGB2GRAY).astype(np.float32)

    best = (-1.0, 0, 0, 1.0)
    for candidate in (1.0, 0.85, 0.72, 0.6, 0.5, 0.42, 0.35, 0.3):
        height = int(cutout_rgb.shape[0] * scale_down * candidate)
        width = int(cutout_rgb.shape[1] * scale_down * candidate)
        if height < 24 or width < 24:
            continue
        if height > search_gray.shape[0] or width > search_gray.shape[1]:
            continue
        template = cv2.cvtColor(
            cv2.resize(cutout_rgb, (width, height), interpolation=cv2.INTER_AREA),
            cv2.COLOR_RGB2GRAY).astype(np.float32)
        try:
            result = cv2.matchTemplate(search_gray, template, cv2.TM_CCOEFF_NORMED)
        except Exception:  # noqa: BLE001
            continue
        result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
        _, score, _, location = cv2.minMaxLoc(result)
        if score > best[0]:
            best = (float(score), int(location[0]), int(location[1]), candidate)

    if best[0] <= 0.0:
        return _cannot_verify("the cutout does not appear anywhere in the produced picture",
                              best_match=round(best[0], 4))

    score, left_edge, top_edge, candidate = best
    width = max(1, int(round(cutout_rgb.shape[1] * candidate)))
    height = max(1, int(round(cutout_rgb.shape[0] * candidate)))
    x = int(round(left_edge / scale_down))
    y = int(round(top_edge / scale_down))
    # Compare at the scale the product was actually found at; comparing a full-size cutout
    # against a downscaled region would be a size error, not a fidelity test.
    scaled_rgb = cv2.resize(cutout_rgb, (width, height), interpolation=cv2.INTER_AREA)
    scaled_alpha = (cv2.resize(cutout_alpha, (width, height), interpolation=cv2.INTER_AREA)
                    if cutout_alpha is not None else None)
    verdict = region_similarity(frame, scaled_rgb, scaled_alpha, [x, y, width, height])
    verdict["found_by"] = "template_match"
    verdict["match_score"] = round(score, 4)
    verdict["template_scale"] = candidate
    verdict["min_similarity"] = float(min_similarity)
    if not verdict.get("cannot_verify"):
        verdict["ok"] = bool(verdict.get("similarity", 0.0) >= float(min_similarity))
    return verdict


def check_composite(produced_rgb: np.ndarray, cutout: Any, *,
                    placement: Optional[Sequence[int]] = None,
                    min_similarity: float = DEFAULT_MIN_SIMILARITY) -> Dict[str, Any]:
    """The one entry point: compare at the recorded placement, or find the product.

    When a placement is supplied it is authoritative: a box that falls outside the frame, or one
    whose region does not match the cutout, is a **failure**, not a reason to go looking elsewhere.
    Falling back on a failed placement would turn "the generator put the product somewhere else"
    into a pass by finding the product wherever it happens to be.
    """
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
           "missing_cutout_verdict", "region_similarity", "split_rgba"]
