"""Programmatic image scorers — pure functions, no model, PIL + numpy only.

Every check returns::

    {"ok": bool, "skipped": bool, "detail": str, ...measurements}

`score_image` loads the bytes once, runs the checks a brief asks for, and
returns a 0-100 subscore. The checks are deliberately mechanical: dimensions,
aspect, corner-sampled background, subject fill, matte/alpha, file size, a
margin-ink heuristic for the text rule, and — for the two reference input
modes — a reference-subject proxy supplied by `reference_check`. The heuristic
is not OCR; a vision judge can be layered on top, but it is never required for
a score.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import numpy as np

DEFAULT_WEIGHTS = {
    "dimensions": 0.20,
    "aspect": 0.10,
    "background": 0.20,
    "subject_fill": 0.20,
    "alpha_matte": 0.10,
    "file_size": 0.05,
    "text_free": 0.15,
    "reference_subject": 0.25,
}

DEFAULT_CRITICAL = ("dimensions", "aspect", "background")

# Margin ink above this fraction of the margin band reads as text/graphic.
NO_TEXT_MAX_INK = 0.02
# Margin ink at or above this fraction satisfies a text_expected brief.
TEXT_EXPECTED_MIN_INK = 0.002
MARGIN_RATIO = 0.10

#: Weight of the product-region check on a composite. It is graded only for composites, and
#: the denominator is the graded set, so adding it changes nothing for a full generation.
PRODUCT_REGION_WEIGHT = 0.25


@dataclass
class LoadedImage:
    width: int
    height: int
    mode: str
    fmt: str
    rgb: np.ndarray
    alpha: Optional[np.ndarray]
    nbytes: int


def load_image(image_bytes: bytes) -> LoadedImage:
    """Decode bytes into an RGB uint8 array plus an optional alpha plane."""
    from PIL import Image, UnidentifiedImageError

    if not image_bytes:
        raise ValueError("empty image bytes")
    try:
        with Image.open(BytesIO(image_bytes)) as opened:
            fmt = (opened.format or "").upper()
            width, height = opened.size
            alpha = None
            if opened.mode in ("RGBA", "LA"):
                alpha = np.asarray(opened.convert("RGBA"))[:, :, 3].copy()
            rgb = np.asarray(opened.convert("RGB"), dtype=np.uint8)
            mode = opened.mode
    except (UnidentifiedImageError, OSError) as exc:  # noqa: BLE001 - reported as a check failure
        raise ValueError(f"unreadable image: {type(exc).__name__}") from exc
    if width < 8 or height < 8:
        raise ValueError(f"image too small to score: {width}x{height}")
    return LoadedImage(width=width, height=height, mode=mode, fmt=fmt,
                       rgb=rgb, alpha=alpha, nbytes=len(image_bytes))


def _ok(**kw: Any) -> Dict[str, Any]:
    kw.setdefault("skipped", False)
    kw["ok"] = bool(kw.get("ok", False))
    return kw


def _skip(reason: str) -> Dict[str, Any]:
    return {"ok": True, "skipped": True, "detail": reason}


def _as_rgb(value: Any) -> Tuple[int, int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(int(max(0, min(255, int(v)))) for v in value)  # type: ignore[return-value]
    grey = int(max(0, min(255, int(value))))
    return (grey, grey, grey)


def sample_corners(rgb: np.ndarray, patch: int = 24) -> list[Tuple[int, int, int]]:
    """Median RGB of a square patch in each corner, in TL/TR/BL/BR order."""
    height, width = rgb.shape[:2]
    size = max(4, min(int(patch), height // 8, width // 8))
    patches = (
        rgb[:size, :size],
        rgb[:size, width - size:],
        rgb[height - size:, :size],
        rgb[height - size:, width - size:],
    )
    corners = []
    for patch_px in patches:
        med = np.median(patch_px.reshape(-1, 3), axis=0)
        corners.append(tuple(int(round(float(v))) for v in med))
    return corners


def check_dimensions(width: int, height: int, spec: Dict[str, Any]) -> Dict[str, Any]:
    if not spec:
        return _skip("no dimension spec")
    min_w = int(spec.get("min_width", 1))
    min_h = int(spec.get("min_height", 1))
    max_w = int(spec.get("max_width", 10000))
    max_h = int(spec.get("max_height", 10000))
    exact = spec.get("exact")
    tolerance = int(spec.get("tolerance_px", 0))

    if exact:
        target_w, target_h = int(exact[0]), int(exact[1])
        ok = abs(width - target_w) <= tolerance and abs(height - target_h) <= tolerance
        detail = f"{width}x{height} vs exact {target_w}x{target_h} +-{tolerance}px"
    else:
        ok = min_w <= width <= max_w and min_h <= height <= max_h
        detail = f"{width}x{height} vs min {min_w}x{min_h}, max {max_w}x{max_h}"
    return _ok(ok=ok, detail=detail, width=width, height=height, check="dimensions")


def check_aspect(width: int, height: int, spec: Dict[str, Any]) -> Dict[str, Any]:
    if not spec:
        return _skip("no aspect spec")
    ratio = spec.get("ratio", 1.0)
    if isinstance(ratio, str) and ":" in ratio:
        left, right = ratio.split(":", 1)
        ratio = float(left) / float(right)
    ratio = float(ratio)
    tolerance = float(spec.get("tolerance", 0.02))
    if ratio <= 0 or height <= 0:
        return _ok(ok=False, detail="invalid aspect inputs", check="aspect")
    actual = width / height
    ok = abs(actual - ratio) <= tolerance * ratio
    return _ok(ok=ok, detail=f"aspect {actual:.4f} vs {ratio:.4f} +-{tolerance:.3f}",
               actual=round(actual, 4), target=ratio, check="aspect")


def check_background(rgb: np.ndarray, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Corner-sampled background value, uniform or free."""
    if not spec or spec.get("mode", "uniform") == "free":
        return _skip("background is free for this brief")
    target = _as_rgb(spec.get("value", 255))
    tolerance = int(spec.get("tolerance", 6))
    spread_tolerance = int(spec.get("spread_tolerance", max(tolerance, 6)))
    corners = sample_corners(rgb, int(spec.get("corner_px", 24)))
    deviations = [max(abs(c[i] - target[i]) for i in range(3)) for c in corners]
    spread = [max(c[i] for c in corners) - min(c[i] for c in corners) for i in range(3)]
    ok = all(d <= tolerance for d in deviations) and max(spread) <= spread_tolerance
    return _ok(ok=ok,
               detail=(f"corners {corners} vs target {target} +-{tolerance}; "
                       f"max deviation {max(deviations)}, corner spread {max(spread)}"),
               corners=corners, target=list(target),
               max_deviation=max(deviations), spread=max(spread), check="background")


def _background_colour(rgb: np.ndarray) -> np.ndarray:
    corners = np.array(sample_corners(rgb), dtype=np.float32)
    return np.median(corners, axis=0)


def _product_mask_from_cutout(cutout: Any, product_box: Optional[Any],
                              shape: Tuple[int, int]) -> Optional[np.ndarray]:
    """The product's own pixels on the frame's grid, from the saved cutout.

    D-018 (measured 2026-11-11): a white product on a white canvas defeats the
    corner-colour instrument — ST-024 read 20.7 % against a 24 % floor and ST-031
    19.8 % against 20 %, not because the product was small but because it is the
    same colour as the canvas. The cutout the generator saved beside the artefact
    is the product's own silhouette, so its area is the honest measure whatever the
    colours are.
    """
    if cutout is None or product_box is None:
        return None
    try:
        box = [int(v) for v in product_box]
    except (TypeError, ValueError):
        return None
    if len(box) != 4:
        return None
    left, top, right, bottom = box
    frame_h, frame_w = shape
    left, right = max(0, left), min(frame_w, right)
    top, bottom = max(0, top), min(frame_h, bottom)
    if right - left < 2 or bottom - top < 2:
        return None
    array = np.asarray(cutout)
    if array.ndim != 3 or array.shape[2] < 4:
        return None
    from PIL import Image

    alpha = Image.fromarray(array[..., 3].astype(np.uint8), "L")
    # the saved cutout is the generator's canvas, not the product: trim to the alpha
    # box first or the product is measured at a fraction of its real size (measured
    # 2026-11-11: a 768 px cutout canvas resized into a 1 375 px product box read
    # 13.6 % where the product covers ~35 % of the frame).
    bounds = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    if bounds:
        alpha = alpha.crop(bounds)
    alpha = alpha.resize((right - left, bottom - top), Image.NEAREST)
    mask = np.zeros((frame_h, frame_w), dtype=bool)
    mask[top:bottom, left:right] = np.asarray(alpha) > 128
    return mask


def check_subject_fill(rgb: np.ndarray, spec: Dict[str, Any],
                       background_spec: Optional[Dict[str, Any]] = None,
                       product_box: Optional[Any] = None,
                       subject_mask: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """How much of the frame the product occupies.

    Two instruments, chosen by the background the brief asked for:

    * a **flat** background (uniform value / white matte) gives a real corner colour, so the
      share of pixels that differ from it *is* the subject's area;
    * a **free** background is a generated scene, and then the corner colour is not the
      background at all — every pixel differs from it. Measured 2026-11-11: PO-002 and PO-010
      reported "subject fill 94.3 % against 8-50 %" on a correct lifestyle picture, because the
      instrument was measuring the scene, not the product. On that route the product's box is
      the only honest measure of its share, and without a box the check is *skipped with a
      reason*, never passed by default.
    """
    if not spec:
        return _skip("no fill spec")
    low = float(spec.get("min", 0))
    high = float(spec.get("max", 100))
    distance = float(spec.get("distance", 20))
    mode = str((background_spec or {}).get("mode") or "").lower()
    if mode in ("free", "scene"):
        box = [int(v) for v in product_box] if (
            isinstance(product_box, (list, tuple)) and len(product_box) == 4) else None
        if not box or box[2] <= box[0] or box[3] <= box[1]:
            return _skip(
                "a free (scene) background gives no corner colour to measure against, and no "
                "product box was recorded: subject fill cannot be measured on this artefact")
        pct = (box[2] - box[0]) * (box[3] - box[1]) / float(rgb.shape[0] * rgb.shape[1]) * 100.0
        ok = low <= pct <= high
        return _ok(ok=ok,
                   detail=f"product box {pct:.1f}% of the frame vs {low:.1f}-{high:.1f}% "
                          f"(free background: the box is the measure, not the corner colour)",
                   fill_pct=round(pct, 2), min=low, max=high, instrument="product_box",
                   check="subject_fill")
    bg = _background_colour(rgb)
    diff = np.abs(rgb.astype(np.int16) - bg.astype(np.int16)).max(axis=2)
    mask = diff > distance
    pct = float(mask.mean() * 100.0)
    if subject_mask is not None and pct < 5.0:
        # D-018: a white product on a white canvas has no colour difference to find
        # from, so the corner instrument reads ~0 %. Only in that blind case — and
        # only when the product's own cutout is available — the cutout's area is used.
        # Every other picture keeps the instrument it was scored with before.
        share = float(np.asarray(subject_mask, dtype=bool).mean() * 100.0)
        if share >= 5.0:
            ok = low <= share <= high
            return _ok(ok=ok,
                       detail=f"subject fill {share:.1f}% vs {low:.1f}-{high:.1f}% "
                              f"(the product's own cutout: the corner colour found "
                              f"{pct:.1f}% and cannot see this product)",
                       fill_pct=round(share, 2), min=low, max=high,
                       instrument="cutout_mask", check="subject_fill",
                       corner_fill_pct=round(pct, 2))
    ok = low <= pct <= high
    return _ok(ok=ok,
               detail=f"subject fill {pct:.1f}% vs {low:.1f}-{high:.1f}% "
                      f"(distance > {distance:.0f})",
               fill_pct=round(pct, 2), min=low, max=high, instrument="corner_colour",
               background=tuple(int(v) for v in bg), check="subject_fill")


def check_alpha_matte(loaded: LoadedImage, spec: Dict[str, Any]) -> Dict[str, Any]:
    """White-matte cleanliness, or a real alpha cutout when the brief asks for one."""
    mode = (spec or {}).get("mode", "any")
    if mode == "any":
        return _skip("matte free for this brief")

    height, width = loaded.height, loaded.width
    if mode == "alpha":
        if loaded.alpha is None:
            return _ok(ok=False, detail="alpha cutout required but image has no alpha channel",
                       mode=mode, check="alpha_matte")
        transparent = float((loaded.alpha < 16).mean())
        ok = 0.03 <= transparent <= 0.98
        return _ok(ok=ok,
                   detail=f"transparent pixels {transparent * 100:.1f}% (need 3-98%)",
                   mode=mode, transparent_pct=round(transparent * 100, 2),
                   check="alpha_matte")

    # white_matte: the outer ring must be a clean, flat, near-white band.
    thickness = max(4, int(min(height, width) * float((spec or {}).get("ring_ratio", 0.01))))
    ring = np.concatenate([
        loaded.rgb[:thickness, :, :].reshape(-1, 3),
        loaded.rgb[-thickness:, :, :].reshape(-1, 3),
        loaded.rgb[:, :thickness, :].reshape(-1, 3),
        loaded.rgb[:, -thickness:, :].reshape(-1, 3),
    ])
    luminance = ring.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    mean = float(luminance.mean())
    std = float(luminance.std())
    target = float((spec or {}).get("value", 255))
    tolerance = float((spec or {}).get("tolerance", 6))
    max_std = float((spec or {}).get("max_border_std", 6))
    ok = mean >= target - tolerance and std <= max_std
    return _ok(ok=ok,
               detail=f"border mean {mean:.1f} (>= {target - tolerance:.0f}), "
                      f"std {std:.2f} (<= {max_std:.1f})",
               mode=mode, border_mean=round(mean, 2), border_std=round(std, 2),
               check="alpha_matte")


def check_file_size(nbytes: int, width: int, height: int,
                    spec: Dict[str, Any]) -> Dict[str, Any]:
    if not spec:
        return _skip("no file size spec")
    min_bytes = int(spec.get("min_bytes", 0))
    max_bytes = int(spec.get("max_bytes", 20_000_000))
    min_bpp = float(spec.get("min_bytes_per_pixel", 0.01))
    bpp = nbytes / float(max(1, width * height))
    ok = min_bytes <= nbytes <= max_bytes and bpp >= min_bpp
    return _ok(ok=ok,
               detail=(f"{nbytes} bytes ({bpp:.3f} bytes/px) vs "
                       f"{min_bytes}-{max_bytes} bytes, min {min_bpp:.3f} bytes/px"),
               nbytes=nbytes, bytes_per_pixel=round(bpp, 4), check="file_size")


def _ink_mask(rgb: np.ndarray) -> np.ndarray:
    """Dark or saturated pixels, before any decision about what they are."""
    flat = rgb.astype(np.int32)
    luminance = (flat[:, :, 0] * 299 + flat[:, :, 1] * 587 + flat[:, :, 2] * 114) // 1000
    chroma = flat.max(axis=2) - flat.min(axis=2)
    return (luminance < 140) | (chroma > 70)


def _margin_ink_fraction(rgb: np.ndarray, margin_ratio: float = MARGIN_RATIO) -> float:
    """Ink confined to the margin band, as a share of the band.

    A product that fills the frame legitimately crosses the outer band — Amazon's own
    main-image rule asks for ~85 % linear fill — so counting every dark pixel there
    would flag the product itself as overlay text. Only ink that is *confined* to the
    band counts: a connected ink region that also reaches the central area is the
    subject or the scene, not a text overlay. A banner, badge or watermark that lives
    entirely inside the band is still counted.
    """
    height, width = rgb.shape[:2]
    band = max(8, int(min(height, width) * margin_ratio))
    mask = _ink_mask(rgb)
    total = width * height - max(0, width - 2 * band) * max(0, height - 2 * band)
    if total <= 0:
        return 0.0
    central = (band, band, max(band, width - band), max(band, height - band))
    try:
        import cv2  # noqa: PLC0415 - optional; the caller already depends on numpy/PIL

        count, _, stats, _ = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), connectivity=8)
        margin_ink = 0
        for label in range(1, count):
            left, top, wide, high, area = (int(v) for v in stats[label])
            right, bottom = left + wide, top + high
            # Does the region reach the area a subject occupies? A product that fills
            # ~85 % of the frame does; an overlay banner or corner badge does not.
            reaches_centre = (right > central[0] and left < central[2]
                              and bottom > central[1] and top < central[3])
            if not reaches_centre:
                margin_ink += area
        return min(1.0, margin_ink / float(total))
    except Exception:  # noqa: BLE001 - no OpenCV is a fallback, never a false pass
        strips = (mask[:band, :], mask[-band:, :], mask[:, :band], mask[:, -band:])
        return float(sum(int(strip.sum()) for strip in strips)) / float(max(1, total))


def check_text_free(rgb: np.ndarray, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Margin-ink heuristic for the brief's text rule.

    This is not OCR and does not claim to be: it measures dark or saturated ink
    in the outer margin band, which is where Amazon overlay text/graphics live.
    A product that bleeds into the margin can be flagged; the vision judge (off
    by default) is the semantic second opinion.
    """
    rule = (spec or {}).get("rule", "allowed")
    if rule == "allowed":
        return _skip("text allowed for this brief")
    margin_ratio = float((spec or {}).get("margin_ratio", MARGIN_RATIO))
    ink = _margin_ink_fraction(rgb, margin_ratio)
    if rule == "no_text":
        threshold = float((spec or {}).get("max_ink", NO_TEXT_MAX_INK))
        ok = ink <= threshold
        detail = f"margin ink {ink * 100:.2f}% vs max {threshold * 100:.2f}% (text-free)"
    elif rule == "text_expected":
        threshold = float((spec or {}).get("min_ink", TEXT_EXPECTED_MIN_INK))
        ok = ink >= threshold
        detail = f"margin ink {ink * 100:.2f}% vs min {threshold * 100:.2f}% (text expected)"
    else:
        return _skip(f"unknown text rule {rule!r}")
    return _ok(ok=ok, detail=detail, rule=rule, margin_ink=round(ink, 5),
               threshold=threshold, check="text_free")


def _run_checks(loaded: LoadedImage, brief: Dict[str, Any], *,
                composite_route: bool = True,
                product_box: Optional[Any] = None,
                cutout: Any = None) -> Dict[str, Dict[str, Any]]:
    """Every mechanical check for this brief.

    `composite_route` decides whether `alpha_matte` is *applicable*. A composite route cuts the
    seller's product out of its pixels, so a matte — a clean white ring or a real alpha channel —
    is a property of the deliverable and is graded. A full generation produces one opaque plate:
    the canvas has no cutout and cannot have one, so grading a matte there caps the route at a
    rubric constant instead of measuring the picture (measured 2026-11-11: six prompt-only briefs
    at exactly 90.0, every one failing only this check). The check is recorded as skipped *with a
    reason*, never dropped, so an absent check can never be mistaken for a silent pass.
    """
    constraints = brief.get("constraints") or {}
    background_spec = constraints.get("background") or {}
    checks: Dict[str, Dict[str, Any]] = {}
    checks["dimensions"] = check_dimensions(
        loaded.width, loaded.height, constraints.get("dimensions") or {})
    checks["aspect"] = check_aspect(
        loaded.width, loaded.height, constraints.get("aspect") or {})
    checks["background"] = check_background(loaded.rgb, background_spec)
    checks["subject_fill"] = check_subject_fill(
        loaded.rgb, constraints.get("fill_pct") or {}, background_spec,
        product_box=product_box,
        subject_mask=_product_mask_from_cutout(cutout, product_box,
                                               loaded.rgb.shape[:2]))
    matte_spec = constraints.get("matte") or {}
    if composite_route:
        checks["alpha_matte"] = check_alpha_matte(loaded, matte_spec)
    elif str(matte_spec.get("mode") or "any") == "alpha":
        # A white matte is a pixel property and a full generation can satisfy it; an ALPHA
        # cutout cannot exist on an opaque plate, so grading it caps the route at a rubric
        # constant instead of measuring the picture (measured 2026-11-11: six prompt-only
        # briefs at exactly 90.0, every one failing only this check). Skipped with a reason,
        # never dropped, so an absent check can never be mistaken for a silent pass.
        checks["alpha_matte"] = _skip(
            "not applicable to a full-generation deliverable: the plate is opaque and has no "
            "cutout to matte. A brief that needs an alpha cutout routes through the composite "
            "path, where this check is graded.")
        checks["alpha_matte"]["not_applicable"] = True
    else:
        checks["alpha_matte"] = check_alpha_matte(loaded, matte_spec)
    checks["file_size"] = check_file_size(
        loaded.nbytes, loaded.width, loaded.height, constraints.get("file_size") or {})
    text_spec: Dict[str, Any] = {"rule": constraints.get("text_rule", "allowed")}
    if "text_max_ink" in constraints:
        text_spec["max_ink"] = constraints["text_max_ink"]
    if "text_min_ink" in constraints:
        text_spec["min_ink"] = constraints["text_min_ink"]
    checks["text_free"] = check_text_free(loaded.rgb, text_spec)
    return checks


def _normalise_judgement(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {"ok": False, "skipped": True, "detail": "judge returned a non-dict"}
    if "pass" not in raw:
        return {"ok": False, "skipped": True, "detail": "judge returned no pass field"}
    if raw.get("available") is False or raw.get("pass") is None:
        return {"ok": False, "skipped": True,
                "detail": "judge unavailable: " + str(raw.get("reason") or "unknown")}
    reasons = raw.get("reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    passed = bool(raw.get("pass"))
    try:
        score = float(raw.get("score", 100.0 if passed else 0.0))
    except (TypeError, ValueError):
        score = 100.0 if passed else 0.0
    return {"ok": passed, "skipped": False, "score": max(0.0, min(100.0, score)),
            "detail": "; ".join(str(r)[:200] for r in reasons)[:500] or "judge verdict",
            "reasons": [str(r)[:200] for r in reasons][:8]}


def _reference_verdict(rgb: np.ndarray, brief: Dict[str, Any], reference_check: Any) -> Dict[str, Any]:
    """Resolve the reference-subject verdict for this brief and image.

    prompt_only  -> skipped (there is nothing to compare)
    reference    -> the injected check's verdict, or a cannot_verify failure
    unclassified -> cannot_verify failure (an undeclared input is not a pass)
    """
    mode = brief.get("source_mode") or "unclassified"
    if mode == "prompt_only":
        return {"ok": True, "skipped": True, "cannot_verify": False,
                "detail": "prompt-only brief: no reference to verify"}
    if mode not in ("stored_reference", "uploaded_reference"):
        return {"ok": False, "skipped": False, "cannot_verify": True,
                "detail": f"cannot verify: brief has no usable input mode ({mode!r})"}
    if reference_check is None:
        return {"ok": False, "skipped": False, "cannot_verify": True,
                "detail": "cannot verify: no reference was supplied to the scorer"}
    try:
        raw = reference_check(rgb)
    except Exception as exc:  # noqa: BLE001 - an unreadable reference is a failure, not a crash
        return {"ok": False, "skipped": False, "cannot_verify": True,
                "detail": f"cannot verify: reference check raised {type(exc).__name__}"}
    if not isinstance(raw, dict):
        return {"ok": False, "skipped": False, "cannot_verify": True,
                "detail": "cannot verify: reference check returned a non-dict"}
    return {
        "ok": bool(raw.get("ok")),
        "skipped": bool(raw.get("skipped")),
        "cannot_verify": bool(raw.get("cannot_verify")),
        "detail": str(raw.get("detail", ""))[:400],
        **{k: v for k, v in raw.items()
           if k not in ("ok", "skipped", "cannot_verify", "detail", "check")},
    }


def _product_region_verdict(produced_rgb: np.ndarray, *, cutout: Any,
                            placement: Any, placement_quad: Any = None) -> Dict[str, Any]:
    """The composite's own proof: the product pixels in the output are the upload's.

    There is no pass here for "we did not look". A composite route always runs this check; when
    the generator saved no cutout it is `product region cannot be verified: ...`, which is a
    failure under the owner's rule (2026-11-08).
    """
    if cutout is None:
        from .composite_check import missing_cutout_verdict

        return missing_cutout_verdict(
            "the generator saved no cutout it used, so the product region cannot be compared "
            "(expected <artefact>.cutout.png beside the composite)")
    try:
        from .composite_check import check_composite

        verdict = check_composite(produced_rgb, cutout, placement=placement,
                                  placement_quad=placement_quad)
    except Exception as exc:  # noqa: BLE001 - an unreadable cutout is a named failure
        from .composite_check import missing_cutout_verdict

        return missing_cutout_verdict(
            f"the product-region comparison raised {type(exc).__name__}: {exc}")
    verdict.setdefault("skipped", False)
    verdict.setdefault("cannot_verify", False)
    verdict["ok"] = bool(verdict.get("ok"))
    verdict["check"] = "product_region"
    return verdict


def combine_checks(checks: Dict[str, Dict[str, Any]], brief: Dict[str, Any], *,
                   composite_route: bool = False) -> Dict[str, Any]:
    """Turn measured checks into a score, a verdict and the reasons.

    Split out of `score_image` so a later audit can re-score a recorded run with one new check
    (the product region) without inventing numbers: the same weights, the same critical set,
    the same `cannot_verify`-cannot-pass rule.
    """
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(brief.get("weights") or {})
    if composite_route:
        # Graded only for composites; the denominator is the graded set, so a full
        # generation is unchanged.
        weights["product_region"] = float(
            brief.get("product_region_weight", PRODUCT_REGION_WEIGHT))
    vision = checks.get("vision")
    if isinstance(vision, dict) and not vision.get("skipped"):
        weights["vision"] = float(brief.get("vision_weight", 0.25))

    graded = [name for name, check in checks.items()
              if not check.get("skipped") and weights.get(name, 0) > 0]
    denominator = sum(weights[name] for name in graded)
    weighted = sum(weights[name] * (1.0 if checks[name]["ok"] else 0.0) for name in graded)
    score = 100.0 * weighted / denominator if denominator else 0.0

    failed = [name for name, check in checks.items()
              if not check.get("skipped") and not check["ok"]]
    critical = list(brief.get("critical") or DEFAULT_CRITICAL)
    reference = checks.get("reference_subject") or {}
    if not reference.get("skipped") and "reference_subject" not in critical:
        # A picture that does not contain the reference subject cannot pass on
        # the strength of its dimensions.
        critical.append("reference_subject")
    if composite_route and "product_region" not in critical:
        # An unverified product region is a failure even when every other check passes.
        critical.append("product_region")
    critical_failed = [name for name in critical
                       if name in checks and not checks[name].get("skipped")
                       and not checks[name]["ok"]]
    pass_score = float(brief.get("pass_score", 70))
    return {
        "score": round(score, 1),
        "passed": bool(score >= pass_score and not critical_failed),
        "failed_checks": failed,
        "critical_failed": critical_failed,
        "pass_score": pass_score,
        "graded": graded,
    }


def score_image(image_bytes: bytes, brief: Dict[str, Any], *,
                judge: Any = None,
                reference_check: Any = None,
                scene_source: Optional[str] = None,
                route: Optional[str] = None,
                composite_route: Optional[bool] = None,
                cutout: Any = None,
                placement: Any = None,
                placement_quad: Any = None,
                product_box: Optional[Any] = None) -> Dict[str, Any]:
    """Score one image against one brief. Never raises on bad image data.

    `reference_check` is an optional callable taking the decoded RGB array and
    returning a check dict; the harness supplies it for reference-mode briefs.
    A reference-mode brief scored without one is a `cannot_verify` failure — the
    check is never silently skipped into a pass.

    `scene_source` is the generator's own label for how the picture was made. A
    composite whose scene is `synthetic` did not go through the render lane, so it
    is `cannot_verify` and cannot pass: the cutout and the placement are proved,
    the generated scene is not.

    `composite_route` says the picture came out of the composite path. The product
    region is then a mandatory check: no saved cutout means `cannot_verify` and a
    fail, never a skip. When it is `None`, a brief that declares `route: composite`
    selects the same behaviour, so a caller cannot forget the check by omission.
    """
    brief_id = brief.get("id", "unknown")
    mode = brief.get("source_mode") or "unclassified"
    if composite_route is None:
        composite_route = str(route or brief.get("route") or "") == "composite"
    base = {
        "brief_id": brief_id,
        "category": brief.get("category"),
        "situation": brief.get("situation"),
        "difficulty": brief.get("difficulty"),
        "source_mode": mode,
        "route": route,
        "checks": {},
        "failed_checks": [],
        "score": 0.0,
        "passed": False,
        "judged": False,
    }
    if mode == "unclassified":
        base["source_mode"] = "unclassified"
    try:
        loaded = load_image(image_bytes)
    except ValueError as exc:
        base["error"] = str(exc)
        base["checks"] = {
            name: {"ok": False, "skipped": False, "detail": str(exc)}
            for name in DEFAULT_WEIGHTS
        }
        base["failed_checks"] = list(DEFAULT_WEIGHTS)
        return base

    checks = _run_checks(loaded, brief, composite_route=composite_route,
                         product_box=product_box, cutout=cutout)
    base.update({
        "width": loaded.width,
        "height": loaded.height,
        "format": loaded.fmt,
        "bytes": loaded.nbytes,
    })
    checks["reference_subject"] = _reference_verdict(loaded.rgb, brief, reference_check)
    if composite_route:
        checks["product_region"] = _product_region_verdict(
            loaded.rgb, cutout=cutout, placement=placement,
            placement_quad=placement_quad)

    else:
        # No reference, no cutout, nothing to preserve: the check does not apply. It is recorded as
        # skipped with that reason rather than left out, so an absent check is never mistaken for a
        # silent pass.
        checks["product_region"] = _skip(
            "the product-region check applies to the composite route; this brief has no reference "
            "to preserve")


    if judge is not None:
        # The rubric must describe the brief's own product. It used to say "a {situation}
        # picture for a {category}", and `category` is a taxonomy slot: PO-004 asks for three
        # pale-pink Word Coffee gift boxes and is filed under `food_jar`, so the judge
        # correctly answered "not a food jar" about a correct picture (2026-11-11). The
        # brief's own words are the only honest description of what it wants.
        described = str(brief.get("judge_constraint") or "").strip()
        if not described:
            product = str(brief.get("prompt") or brief.get("product") or
                          brief.get("product_description") or "").strip()
            if product:
                described = product
            else:
                described = (f"{brief.get('situation')} picture for a {brief.get('category')} "
                             "that satisfies the brief's stated constraints")
        rubric = {
            "brief_id": brief_id,
            "category": brief.get("category"),
            "situation": brief.get("situation"),
            "constraint": described,
        }
        verdict = _normalise_judgement(judge(image_bytes, rubric))
        checks["vision"] = verdict
        if not verdict.get("skipped"):
            base["judged"] = True
        else:
            checks["vision"]["ok"] = True

    combined = combine_checks(checks, brief, composite_route=composite_route)

    base["checks"] = checks
    base["failed_checks"] = combined["failed_checks"]
    base["critical_failed"] = combined["critical_failed"]
    base["score"] = combined["score"]
    base["passed"] = combined["passed"]
    base["pass_score"] = combined["pass_score"]
    if scene_source == "synthetic":
        base["passed"] = False
        base["cannot_verify"] = True
        base["cannot_verify_reason"] = (
            "the scene was a synthetic backdrop, not a render: the cutout and the "
            "placement are proved, the generated scene is not")
    product_region = checks.get("product_region")
    if composite_route and isinstance(product_region, dict) \
            and product_region.get("cannot_verify"):
        base["passed"] = False
        base["cannot_verify"] = True
        base["cannot_verify_reason"] = str(product_region.get("detail") or "")
    return base


__all__ = [
    "DEFAULT_WEIGHTS",
    "DEFAULT_CRITICAL",
    "LoadedImage",
    "PRODUCT_REGION_WEIGHT",
    "combine_checks",
    "load_image",
    "sample_corners",
    "check_dimensions",
    "check_aspect",
    "check_background",
    "check_subject_fill",
    "check_alpha_matte",
    "check_file_size",
    "check_text_free",
    "score_image",
]
