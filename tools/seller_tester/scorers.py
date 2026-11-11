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
    # Split, not grown: `matte_residue` measures the same property `background` claims
    # (a flat background), and the denominator is unchanged, so a clean picture keeps
    # exactly the score it had before D-020. Measured 2026-11-11.
    "background": 0.10,
    "matte_residue": 0.10,
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
    if isinstance(cutout, (bytes, bytearray)):
        # The cutout saved beside an artefact is a PNG on disk; a caller that hands the
        # checker those bytes gets the same answer as one that decoded them first.
        # (Measured 2026-11-11: passing `path.read_bytes()` made np.asarray produce a
        # 1-D array, so this returned None and the residue check was *skipped* — a
        # silent skip is how a masked shadow passes as a clean picture.)
        from io import BytesIO

        from PIL import Image as _Image

        try:
            cutout = _Image.open(BytesIO(cutout)).convert("RGBA")
        except Exception:  # noqa: BLE001 - unreadable bytes are "no silhouette"
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


#: Share of the frame that may differ from a flat background outside the product before
#: the picture is not a main image any more. 0.5 % of a 2000² frame is 20 000 px.
MATTE_RESIDUE_MAX = 0.005


#: Cutout methods that separate an object from its pixels by colour. A shadow that is
#: attached and opaque survives every one of them, so the silhouette they produce is the
#: product *plus* its shadow — which makes "outside the silhouette" empty (D-026).
COLOUR_CUT_METHODS = ("grabcut", "background_distance", "otsu_lab")


def check_matte_residue(rgb: np.ndarray, spec: Dict[str, Any], *,
                        subject_mask: Optional[np.ndarray] = None,
                        silhouette_source: Optional[str] = None) -> Dict[str, Any]:
    """Is a flat background flat **everywhere**, not only in the corners?

    D-020 (found 2026-11-11 while closing D-017): `check_background` samples the four
    corner patches and `check_alpha_matte`'s white-matte branch samples an outer ring.
    A contact shadow under the product sits between them, so both instruments pass a
    picture a seller cannot list — and every white-main score before this check was
    produced that way.

    The measure is the product's own silhouette (the cutout `D-018` records beside a
    main image): every pixel that differs from the asked value by more than the
    tolerance and is *not* inside the silhouette is residue. Two things are tolerated
    because they are not shadows: a thin blend at the cut edge (the silhouette is
    dilated before the comparison) and isolated sparkle (blobs under 0.02 % of the
    frame are dropped). A shadow is neither.

    Without a silhouette the check is **skipped with a reason** — never passed. It is
    the harness's job to count how many artefacts could not be checked; the number is
    published, not hidden.
    """
    if not spec or str(spec.get("mode", "uniform")).lower() in ("free", "scene"):
        return _skip("background is free for this brief")
    if subject_mask is None:
        return _skip("no product silhouette was recorded beside this artefact, so the "
                     "background can only be sampled at the corners and the ring; the "
                     "residue check is skipped WITH a reason, never passed")
    mask = np.asarray(subject_mask, dtype=bool)
    if mask.shape != rgb.shape[:2]:
        return _skip("the recorded silhouette does not match the picture's frame")
    if not mask.any():
        return _skip("the recorded silhouette is empty, so nothing is inside it")
    if str(silhouette_source or "").lower() in COLOUR_CUT_METHODS:
        # D-026 (measured 2026-11-11): a colour cut keeps a shadow that is attached to
        # the product, so the silhouette it produced already contains the thing this
        # check looks for. Reporting 0.00 % there is not a clean picture, it is a mask
        # hiding the smear; say it cannot be verified instead of saying it is clean.
        return _skip(f"the silhouette came from a colour cut ({silhouette_source}), "
                     "which keeps a shadow attached to the product; an instrument "
                     "cannot police the mask it is calibrated against, so this picture "
                     "is UNVERIFIED for residue — not clean")
    target = _as_rgb(spec.get("value", 255))
    tolerance = int(spec.get("tolerance", 6))
    import cv2

    height, width = mask.shape[:2]
    ring = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    deviation = np.abs(rgb.astype(np.int16) - np.array(target, dtype=np.int16)).max(axis=2)
    raw = (deviation > tolerance) & ~ring
    px = int(raw.sum())
    if px:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            raw.astype(np.uint8), connectivity=8)
        floor = max(64, int(0.0002 * float(raw.size)))
        keep = np.zeros_like(raw)
        for index in range(1, count):
            if int(stats[index, cv2.CC_STAT_AREA]) >= floor:
                keep |= (labels == index)
        raw = keep
        px = int(raw.sum())
    share = 100.0 * px / float(raw.size)
    neutral = np.abs(rgb[..., 0].astype(np.int16) - rgb[..., 2].astype(np.int16)) <= 14
    shadow = int((raw & neutral).sum())
    ok = share <= 100.0 * MATTE_RESIDUE_MAX
    return _ok(ok=ok,
               detail=(f"background residue {share:.2f}% of the frame ({px} px) outside "
                       f"the product's silhouette, {shadow} px of it neutral "
                       f"(shadow-shaped); limit {100.0 * MATTE_RESIDUE_MAX:.1f}% at "
                       f"value {target[0]} ±{tolerance}"),
               residue_pct=round(share, 3), residue_px=px, shadow_px=shadow,
               tolerance=tolerance, target=list(target), check="matte_residue")


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


def _runs(row: np.ndarray) -> list[tuple[int, int]]:
    """(start, end_exclusive) runs of True in one boolean row."""
    padded = np.concatenate(([0], row.astype(np.int8), [0]))
    edges = np.diff(padded)
    starts = np.flatnonzero(edges == 1).tolist()
    ends = np.flatnonzero(edges == -1).tolist()
    return list(zip(starts, ends))


def _components(mask: np.ndarray, *, with_map: bool = False
                ) -> Any:
    """4-connected components of a boolean mask, numpy only (no scipy).

    Run-length rows are merged with a union-find, so the cost follows the ink
    rather than the frame: a 2000 x 2000 page with a few strokes labels in
    milliseconds. With `with_map=True` the per-pixel label map is returned too,
    which is what lets a caller ask "does this mark touch the product?".
    """
    parent: list[int] = []

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    height = mask.shape[0]
    previous: list[tuple[int, int, int]] = []
    runs: list[tuple[int, int, int, int]] = []
    index = 0
    for y in range(height):
        current: list[tuple[int, int, int]] = []
        for start, end in _runs(mask[y]):
            parent.append(index)
            for p_start, p_end, p_index in previous:
                if p_start < end and start < p_end:
                    union(index, p_index)
            current.append((start, end, index))
            runs.append((y, start, end, index))
            index += 1
        previous = current

    stats: Dict[int, Dict[str, Any]] = {}
    label_map = np.zeros(mask.shape, dtype=np.int32) if with_map else None
    for y, start, end, label in runs:
        root = find(label)
        entry = stats.setdefault(root, {"area": 0, "x0": start, "x1": end,
                                        "y0": y, "y1": y})
        entry["area"] += end - start
        entry["x0"] = min(entry["x0"], start)
        entry["x1"] = max(entry["x1"], end)
        entry["y1"] = max(entry["y1"], y)
        if label_map is not None:
            label_map[y, start:end] = root + 1
    components = [dict(value, id=key) for key, value in stats.items()]
    if with_map:
        return components, label_map
    return components


def _dilate(mask: np.ndarray, steps: int = 3) -> np.ndarray:
    out = mask.copy()
    for _ in range(max(0, int(steps))):
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        out = grown
    return out


def check_stray_marks(rgb: np.ndarray, spec: Dict[str, Any], *,
                      subject_mask: Optional[np.ndarray] = None,
                      frame: Optional[Any] = None) -> Dict[str, Any]:
    """Stray objects on or beside the product, measured — the D-019 instrument.

    A stray is a *small, thin, detached* mark: a stick or wire, a dashed rule, a
    floating ring, a ghosted duplicate. Three things are deliberately not strays:

    * the product itself, which is why a silhouette is required — without one the
      check is skipped rather than guessed;
    * a large region, which is a scene or a shadow, not an object: a contact
      shadow is measured by `check_matte_residue`, not here;
    * the page furniture a layout stage drew on purpose. That is why `frame`
      exists: a composed page is measured **inside its photo panel**, because the
      rules, headings and callout dots live in the margin by construction
      (`deterministic.infographic`). Asking "is this page free of marks" of a page
      the harness itself typeset was the D-019 acceptance bug. The panel is inset
      by `frame_inset` (10 px) so the panel's own border line and the callout dots
      that sit on it are not read as marks.

    Returns a verdict shaped like every other check. `skipped` is a real answer:
    with no silhouette nothing can be attributed to the product.
    """
    if subject_mask is None:
        return _skip("no product silhouette was recorded, so a mark cannot be "
                     "attributed to the scene rather than the product")
    spec = spec or {}
    distance = float(spec.get("distance", 20))
    min_area = int(spec.get("min_area", 80))
    max_area = int(spec.get("max_area", 20000))
    max_side_frac = float(spec.get("max_side_fraction", 0.25))
    height, width = rgb.shape[:2]
    if frame:
        x0, y0, x1, y1 = (int(v) for v in frame)
        inset = int(spec.get("frame_inset", 10))
        x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(width, x1), min(height, y1)
    else:
        x0, y0, x1, y1 = 0, 0, width, height
    if x1 - x0 < 8 or y1 - y0 < 8:
        return _skip(f"frame {frame!r} is too small to measure")
    region = np.asarray(rgb[y0:y1, x0:x1], dtype=np.int16)
    corners = [region[0:24, 0:24], region[0:24, -24:], region[-24:, 0:24], region[-24:, -24:]]
    levels = [np.median(patch.reshape(-1, 3), axis=0) for patch in corners]
    background = np.median(np.array(levels), axis=0)
    spread = max(float(np.abs(level - background).max()) for level in levels)
    max_spread = float(spec.get("max_corner_spread", 12))
    if spread > max_spread:
        # A scene with a horizon or a vignette has no single background to differ from, so
        # a "mark" here could just as easily be the scene. Reported, never guessed.
        return _skip(f"the background is not a field: corner levels span {spread:.0f} "
                     f"levels of {max_spread:.0f}, so a mark cannot be attributed to the "
                     f"picture rather than the scene")
    ink = np.abs(region - background).max(axis=2) > distance
    subject = np.asarray(subject_mask, dtype=bool)[y0:y1, x0:x1]
    outside = ink & ~subject
    side_limit = max_side_frac * min(x1 - x0, y1 - y0)
    min_thickness = float(spec.get("min_thickness", 4.0))
    rim_radius = int(spec.get("rim_radius", 3))
    components, labels = _components(outside, with_map=True)
    hugging = _dilate(subject, rim_radius)
    # Three shape filters, each with a reason:
    #  * a halo or a silhouette rim hugs the product edge, so most of its own pixels sit
    #    inside the product's rim band — the silhouette and residue checks own that
    #    property, and it is not an object a seller would point at;
    #  * a mark 1-3 px thick is a hairline, not an object;
    #  * a region larger than `max_area` or wider than the side cap is a scene area or a
    #    shadow, not a mark.
    marks = []
    for component in components:
        side = max(component["x1"] - component["x0"], component["y1"] - component["y0"])
        thickness = component["area"] / float(max(1, side))
        if not (min_area <= component["area"] <= max_area and side <= side_limit
                and thickness >= min_thickness):
            continue
        own = labels == int(component["id"]) + 1
        if float((own & hugging).sum()) >= 0.5 * component["area"]:
            continue
        marks.append({key: int(component[key])
                      for key in ("area", "x0", "y0", "x1", "y1")})
    marks.sort(key=lambda mark: mark["area"], reverse=True)
    detail = (f"no stray object outside the product in "
              f"{'the photo panel' if frame else 'the frame'}"
              if not marks else
              f"{len(marks)} stray mark(s), {sum(m['area'] for m in marks)} px, "
              f"largest {marks[0]['area']} px at "
              f"({marks[0]['x0']},{marks[0]['y0']})-({marks[0]['x1']},{marks[0]['y1']})")
    return _ok(ok=not marks, check="stray_marks", marks=marks[:8], mark_px=sum(
        mark["area"] for mark in marks), frame=[x0, y0, x1, y1],
        background=[int(v) for v in background], detail=detail)


#: The page furniture `deterministic.infographic` draws itself. A composed page is
#: not a photograph: these marks are the layout, and asking a judge to call them
#: strays was the D-019 acceptance bug (measured 2026-11-11).
COMPOSED_PAGE_FURNITURE = ("the accent rule at the top of the page", "the subtitle rule",
                           "the footer rule and footer text", "the callout chips",
                           "their leader lines", "their anchor dots")


def judge_constraint(brief: Dict[str, Any], layout: Optional[Dict[str, Any]] = None
                     ) -> Dict[str, Any]:
    """The question the vision judge is asked, and the scope of "stray".

    Two populations, two questions:

    * a **photograph** (no layout stage) must be free of marks on or beside the
      product, including the background the model drew;
    * a **composed page** (the harness typed the title, rules, callouts and footer)
      is judged on the photograph inside its panel. Its own furniture is named as
      exempt so a correct page is not failed for the layout that makes it correct.

    `layout` is the generator's own record (`{"kind": "deterministic", "panel": …}`).
    Anything else — absent, refused, errored — is judged as a photograph, which is
    the stricter question and never the weaker one.
    """
    described = str(brief.get("judge_constraint") or "").strip()
    if not described:
        described = str(brief.get("prompt") or brief.get("product") or
                        brief.get("product_description") or "").strip()
    if not described:
        described = (f"{brief.get('situation')} picture for a {brief.get('category')} "
                     "that satisfies the brief's stated constraints")
    record = layout or {}
    composed = (str(record.get("kind") or "") == "deterministic"
                and str(brief.get("situation") or "") in ("infographic", "packaging_mockup"))
    if not composed:
        return {
            "constraint": (f"{described} The picture must be free of stray marks: a thin "
                           "stick or wire, a dashed rule, a floating ring, or a duplicate "
                           "of the product, on or beside the product."),
            "scope": "photograph",
            "furniture_exempt": [],
            "brief_id": brief.get("id"),
        }
    return {
        "constraint": (
            f"{described} Judge the photograph inside the page's photo panel. A stray there "
            "is a thin stick or wire, a dashed rule, a floating ring or a small detached "
            "object on or beside the product. The page's own layout furniture is drawn by "
            "the app and is NOT a stray: " + "; ".join(COMPOSED_PAGE_FURNITURE) + "."),
        "scope": "composed_page",
        "furniture_exempt": list(COMPOSED_PAGE_FURNITURE),
        "panel": record.get("panel"),
        "brief_id": brief.get("id"),
    }


def _run_checks(loaded: LoadedImage, brief: Dict[str, Any], *,
                composite_route: bool = True,
                product_box: Optional[Any] = None,
                cutout: Any = None,
                silhouette_source: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
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
    subject_mask = _product_mask_from_cutout(cutout, product_box, loaded.rgb.shape[:2])
    checks["subject_fill"] = check_subject_fill(
        loaded.rgb, constraints.get("fill_pct") or {}, background_spec,
        product_box=product_box, subject_mask=subject_mask)
    # D-020: the same silhouette, used for the property `background` only samples at the
    # corners. Graded only where a silhouette exists; otherwise skipped with the reason.
    checks["matte_residue"] = check_matte_residue(
        loaded.rgb, background_spec, subject_mask=subject_mask,
        silhouette_source=silhouette_source)
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
    if (checks.get("matte_residue") or {}).get("skipped"):
        # The split is only affordable where the residue can actually be measured. A
        # picture with no recorded silhouette keeps the single background weight, so
        # its score is exactly what it was before D-020 (measured 2026-11-11).
        weights["background"] = float(brief.get("background_weight", 0.20))
        weights.pop("matte_residue", None)
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
    residue = checks.get("matte_residue") or {}
    if not residue.get("skipped") and "matte_residue" not in critical:
        # A main image with a shadow under the product is not listable, for the same
        # reason `background` is critical: this is the property it claims.
        critical.append("matte_residue")
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
                product_box: Optional[Any] = None,
                silhouette_source: Optional[str] = None,
                layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
                         product_box=product_box, cutout=cutout,
                         silhouette_source=silhouette_source)
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
        rubric = judge_constraint(brief, layout)
        rubric.update({"category": brief.get("category"),
                       "situation": brief.get("situation")})
        verdict = _normalise_judgement(judge(image_bytes, rubric))
        checks["vision"] = verdict
        if not verdict.get("skipped"):
            base["judged"] = True
        else:
            checks["vision"]["ok"] = True
        base["judge_scope"] = rubric.get("scope")

    # D-019: measured, never graded. "Stray marks" is a question about the mark on or
    # beside the product, so it needs the product's silhouette and — on a page the
    # harness composed — the photo panel, not the page. Recorded as a diagnostic so no
    # published score moves for a check that was not part of the weights.
    mask = _product_mask_from_cutout(cutout, product_box, loaded.rgb.shape[:2])
    panel = (layout or {}).get("panel")
    panel_frame = None
    if isinstance(panel, (list, tuple)) and len(panel) == 4:
        panel_frame = [int(panel[0]), int(panel[1]),
                       int(panel[0]) + int(panel[2]), int(panel[1]) + int(panel[3])]
    stray_spec = dict(((brief.get("constraints") or {}).get("stray_marks") or {}))
    base["stray_marks"] = check_stray_marks(
        loaded.rgb, stray_spec, subject_mask=mask,
        frame=panel_frame if str((layout or {}).get("kind")) == "deterministic" else None)

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
    "check_matte_residue",
    "check_subject_fill",
    "check_alpha_matte",
    "check_file_size",
    "check_text_free",
    "score_image",
]
