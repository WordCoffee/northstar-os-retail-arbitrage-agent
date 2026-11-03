"""Legibility gate for product pictures.

A product picture that cannot be read is not a product picture. The measurable
half of "looks good" on a package shot is that the brand wordmark and the net
weight survive the composite at the size the picture will be used, and that the
type is not soft. This module runs the local OCR (RapidOCR, CPU, offline) over a
composite and decides:

* the wordmark is present — an explicit one when the caller names it, otherwise
  any alphabetic token of three or more letters;
* the net weight is present — an explicit string when named, otherwise a
  number plus a weight/volume unit;
* every detected text region is SHARP — measured as the variance of the
  Laplacian inside that region, which collapses (three orders of magnitude on
  the reference probe) when the picture is blurred;
* the text is not too small to read at the delivered size.

Nothing is generated or guessed: an OCR failure is a refusal (`ok=False`) with
a named reason, never a pass. No provider call, no network, no cost.
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image

import text_fidelity as tf

#: Variance of the Laplacian inside an OCR box. Sharp 120 px type on the
#: reference probe measures ~3600; the same picture blurred measures ~2.
MIN_BOX_SHARPNESS = 40.0
#: A text region shorter than this cannot be read at product-picture scale.
MIN_TEXT_HEIGHT_PX = 10
#: At least this share of detected boxes must clear the sharpness floor.
MIN_SHARP_BOX_SHARE = 0.75

_WEIGHT_RE = re.compile(
    r"(?<![A-Za-z0-9])(\d+(?:[.,]\d+)?)\s*"
    r"(oz|fl\s*oz|g|gr|gram|grams|kg|mg|ml|l|litre|liter|lb|lbs)(?![A-Za-z])",
    re.IGNORECASE,
)
_ALPHA_TOKEN = re.compile(r"[A-Za-z][A-Za-z'&.-]{2,}")


def _as_png_bytes(image: Union[Image.Image, bytes, bytearray]) -> bytes:
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)
    if isinstance(image, Image.Image):
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()
    raise TypeError("image must be a PIL Image or PNG/JPEG bytes")


def _normalise(text: str) -> str:
    """Uppercase alphanumerics only, with OCR's O/0 confusion folded.

    OCR reads the 'O' in 'OZ' as a zero ('6 0Z') often enough that a strict
    comparison would refuse a legible picture. Folding O to 0 keeps the check
    about whether the weight was READ, not about which glyph the engine chose.
    """
    s = re.sub(r"[^A-Z0-9]+", "", text.upper())
    return s.replace("O", "0")


def _laplacian_variance(gray: np.ndarray) -> float:
    """Variance of the 4-neighbour Laplacian (higher = sharper edges)."""
    a = gray.astype(np.float32)
    if a.shape[0] < 3 or a.shape[1] < 3:
        return 0.0
    p = np.pad(a, 1, mode="edge")
    lap = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
           - 4.0 * p[1:-1, 1:-1])
    return float(lap.var())


def _box_sharpness(img: Image.Image, box: Sequence[float], pad: int = 6) -> float:
    x0, y0, x1, y1 = (int(round(v)) for v in box[:4])
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(img.width, x1 + pad), min(img.height, y1 + pad)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0
    crop = np.asarray(img.crop((x0, y0, x1, y1)).convert("L"))
    return _laplacian_variance(crop)


def _refusal(reason: str, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "reason": reason, "words": [], "boxes": 0}
    out.update(extra)
    return out


def assert_legible(image: Union[Image.Image, bytes, bytearray], *,
                   wordmark: Optional[str] = None,
                   net_weight: Optional[str] = None,
                   min_sharpness: float = MIN_BOX_SHARPNESS,
                   min_text_height_px: int = MIN_TEXT_HEIGHT_PX,
                   min_sharp_box_share: float = MIN_SHARP_BOX_SHARE
                   ) -> Dict[str, Any]:
    """Decide whether a product picture is legible, and say why not.

    Returns ``{ok, reason, words, boxes, sharpness, text_height_px, engine,
    wordmark_found, net_weight_found, regions}``. ``ok`` is True only when OCR
    actually read a wordmark AND a net weight AND the type is sharp.
    """
    try:
        png = _as_png_bytes(image)
    except TypeError as exc:
        return _refusal(f"bad_image: {exc}")

    parsed, err = tf._ocr_boxes(png)  # same module's OCR, with box geometry
    if parsed is None:
        return _refusal("ocr_unavailable" if err == "unavailable" else f"ocr_error: {err}",
                        engine=None if err == "unavailable" else "rapidocr")

    img, boxes = parsed
    words = [str(b[4]) for b in boxes]
    joined = " ".join(words)
    joined_norm = _normalise(joined)

    if not boxes:
        return _refusal("no_text_found", engine="rapidocr", boxes=0, words=[])

    regions: List[Dict[str, Any]] = []
    for b in boxes:
        x0, y0, x1, y1, text = b
        regions.append({
            "text": str(text),
            "box": [round(float(x0), 1), round(float(y0), 1),
                    round(float(x1), 1), round(float(y1), 1)],
            "height_px": int(round(float(y1) - float(y0))),
            "sharpness": round(_box_sharpness(img, b), 2),
        })

    sharpness = float(np.median([r["sharpness"] for r in regions]))
    text_height = int(max(r["height_px"] for r in regions))
    sharp_share = float(sum(1 for r in regions if r["sharpness"] >= min_sharpness)
                        / max(1, len(regions)))

    # 1. wordmark -----------------------------------------------------------
    if wordmark:
        found_wordmark = _normalise(wordmark) in joined_norm
    else:
        found_wordmark = any(_ALPHA_TOKEN.search(w) for w in words)
    if not found_wordmark:
        return _refusal("wordmark_not_read" + (f": {wordmark}" if wordmark else ""),
                        words=words, boxes=len(boxes), engine="rapidocr",
                        sharpness=round(sharpness, 2), text_height_px=text_height,
                        regions=regions)

    # 2. net weight ---------------------------------------------------------
    if net_weight:
        found_weight = _normalise(net_weight) in joined_norm
    else:
        found_weight = bool(_WEIGHT_RE.search(joined))
    if not found_weight:
        return _refusal("net_weight_not_read" + (f": {net_weight}" if net_weight else ""),
                        words=words, boxes=len(boxes), engine="rapidocr",
                        sharpness=round(sharpness, 2), text_height_px=text_height,
                        regions=regions)

    # 3. type that survives the picture, not a claim that it does -----------
    if text_height < int(min_text_height_px):
        return _refusal(f"text_too_small: {text_height}px < {int(min_text_height_px)}px",
                        words=words, boxes=len(boxes), engine="rapidocr",
                        sharpness=round(sharpness, 2), text_height_px=text_height,
                        regions=regions)
    if sharp_share < float(min_sharp_box_share):
        return _refusal(
            f"blurred_or_too_soft: {sharp_share:.0%} of text regions at or above "
            f"{min_sharpness:g} (median {sharpness:.1f})",
            words=words, boxes=len(boxes), engine="rapidocr",
            sharpness=round(sharpness, 2), text_height_px=text_height,
            regions=regions)

    return {
        "ok": True,
        "reason": "",
        "words": words,
        "boxes": len(boxes),
        "engine": "rapidocr",
        "sharpness": round(sharpness, 2),
        "text_height_px": text_height,
        "sharp_box_share": round(sharp_share, 3),
        "wordmark_found": True,
        "net_weight_found": True,
        "regions": regions,
    }


__all__ = ["assert_legible", "MIN_BOX_SHARPNESS", "MIN_TEXT_HEIGHT_PX"]
