"""Guarantee a main image carries no text.

The creative lanes already know that diffusion must never be asked to spell, and
`text_fidelity` can detect glyphs and clean them. What was missing is the last
step: nothing applied that guarantee to the *bench* and listing path, so a
main-image render shipped with invented lettering. Measured 2026-11-05 on the
frozen bench: `from-01-main_white` scored **0/100 on text accuracy** because the
model drew text onto a main image that must be text-free.

This module is the small, explicit bridge:

    ensure_text_free(png) -> {bytes, boxes_before, boxes_after, cleaned, passes}

It OCRs, cleans, re-OCRs, and reports what happened. A render that cannot be
cleaned is returned as-is with `cleaned=False` and the reason - never silently
"fixed" and never silently passed.

CPU only: no GPU, no model weights, so it runs even when the render lane is
paused.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def ensure_text_free(png: bytes, *, max_passes: int = 2,
                     detect: Optional[Callable[[bytes], Dict[str, Any]]] = None,
                     clean: Optional[Callable[..., Dict[str, Any]]] = None
                     ) -> Dict[str, Any]:
    """Remove OCR-detected text from an image that must not contain any.

    ``detect`` and ``clean`` are injectable so the logic is testable without the
    OCR engine; in production they default to ``text_fidelity``.
    """
    if not png:
        raise ValueError("an image is required")

    if detect is None or clean is None:
        import text_fidelity as tf  # local import: keeps this module dependency-free

        detect = detect or tf.check_text_in_image
        clean = clean or tf.clean_text_regions

    first = detect(png) or {}
    if first.get("status") not in (None, "ok"):
        return {"bytes": png, "cleaned": False, "passes": 0,
                "boxes_before": None, "boxes_after": None,
                "reason": f"ocr_{first.get('status')}: {first.get('error')}"}
    boxes_before = int(first.get("boxes") or 0)
    if boxes_before == 0:
        return {"bytes": png, "cleaned": False, "passes": 0,
                "boxes_before": 0, "boxes_after": 0, "reason": "already clean"}

    current = png
    passes = 0
    last_boxes = boxes_before
    while passes < max(0, int(max_passes)):
        passes += 1
        result = clean(current) or {}
        candidate = result.get("bytes") or result.get("image") or current
        if not candidate:
            break
        current = candidate
        after = detect(current) or {}
        last_boxes = int(after.get("boxes") or 0)
        if last_boxes == 0:
            break

    return {
        "bytes": current,
        "cleaned": last_boxes == 0,
        "passes": passes,
        "boxes_before": boxes_before,
        "boxes_after": last_boxes,
        "reason": "text removed" if last_boxes == 0 else "text still detected",
    }
