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


def check_subject_fill(rgb: np.ndarray, spec: Dict[str, Any],
                       background_spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Estimate subject fill as the share of pixels that differ from the corners."""
    if not spec:
        return _skip("no fill spec")
    low = float(spec.get("min", 0))
    high = float(spec.get("max", 100))
    distance = float(spec.get("distance", 20))
    bg = _background_colour(rgb)
    diff = np.abs(rgb.astype(np.int16) - bg.astype(np.int16)).max(axis=2)
    mask = diff > distance
    pct = float(mask.mean() * 100.0)
    ok = low <= pct <= high
    return _ok(ok=ok,
               detail=f"subject fill {pct:.1f}% vs {low:.1f}-{high:.1f}% "
                      f"(distance > {distance:.0f})",
               fill_pct=round(pct, 2), min=low, max=high,
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


def _margin_ink_fraction(rgb: np.ndarray, margin_ratio: float = MARGIN_RATIO) -> float:
    height, width = rgb.shape[:2]
    band = max(8, int(min(height, width) * margin_ratio))
    strips = (
        rgb[:band, :, :],
        rgb[-band:, :, :],
        rgb[:, :band, :],
        rgb[:, -band:, :],
    )
    ink = 0
    total = 0
    for strip in strips:
        flat = strip.reshape(-1, 3).astype(np.int32)
        luminance = (flat[:, 0] * 299 + flat[:, 1] * 587 + flat[:, 2] * 114) // 1000
        chroma = flat.max(axis=1) - flat.min(axis=1)
        ink += int(((luminance < 140) | (chroma > 70)).sum())
        total += flat.shape[0]
    return ink / float(max(1, total))


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


def _run_checks(loaded: LoadedImage, brief: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    constraints = brief.get("constraints") or {}
    background_spec = constraints.get("background") or {}
    checks: Dict[str, Dict[str, Any]] = {}
    checks["dimensions"] = check_dimensions(
        loaded.width, loaded.height, constraints.get("dimensions") or {})
    checks["aspect"] = check_aspect(
        loaded.width, loaded.height, constraints.get("aspect") or {})
    checks["background"] = check_background(loaded.rgb, background_spec)
    checks["subject_fill"] = check_subject_fill(
        loaded.rgb, constraints.get("fill_pct") or {}, background_spec)
    checks["alpha_matte"] = check_alpha_matte(loaded, constraints.get("matte") or {})
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


def score_image(image_bytes: bytes, brief: Dict[str, Any], *,
                judge: Any = None,
                reference_check: Any = None) -> Dict[str, Any]:
    """Score one image against one brief. Never raises on bad image data.

    `reference_check` is an optional callable taking the decoded RGB array and
    returning a check dict; the harness supplies it for reference-mode briefs.
    A reference-mode brief scored without one is a `cannot_verify` failure —
    the check is never silently skipped into a pass.
    """
    brief_id = brief.get("id", "unknown")
    mode = brief.get("source_mode") or "unclassified"
    base = {
        "brief_id": brief_id,
        "category": brief.get("category"),
        "situation": brief.get("situation"),
        "difficulty": brief.get("difficulty"),
        "source_mode": mode,
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

    checks = _run_checks(loaded, brief)
    base.update({
        "width": loaded.width,
        "height": loaded.height,
        "format": loaded.fmt,
        "bytes": loaded.nbytes,
    })
    checks["reference_subject"] = _reference_verdict(loaded.rgb, brief, reference_check)

    weights = dict(DEFAULT_WEIGHTS)
    weights.update(brief.get("weights") or {})

    if judge is not None:
        rubric = {
            "brief_id": brief_id,
            "category": brief.get("category"),
            "situation": brief.get("situation"),
            "constraint": brief.get("judge_constraint") or (
                f"{brief.get('situation')} picture for a {brief.get('category')} "
                "that satisfies the brief's stated constraints"),
        }
        verdict = _normalise_judgement(judge(image_bytes, rubric))
        checks["vision"] = verdict
        if not verdict.get("skipped"):
            weights["vision"] = float(brief.get("vision_weight", 0.25))
            base["judged"] = True
        else:
            checks["vision"]["ok"] = True

    graded = [name for name, check in checks.items()
              if not check.get("skipped") and weights.get(name, 0) > 0]
    denominator = sum(weights[name] for name in graded)
    weighted = sum(weights[name] * (1.0 if checks[name]["ok"] else 0.0) for name in graded)
    score = 100.0 * weighted / denominator if denominator else 0.0

    failed = [name for name, check in checks.items()
              if not check.get("skipped") and not check["ok"]]
    critical = list(brief.get("critical") or DEFAULT_CRITICAL)
    reference = checks["reference_subject"]
    if not reference.get("skipped") and "reference_subject" not in critical:
        # A picture that does not contain the reference subject cannot pass on
        # the strength of its dimensions.
        critical.append("reference_subject")
    critical_failed = [name for name in critical
                       if name in checks and not checks[name].get("skipped")
                       and not checks[name]["ok"]]
    pass_score = float(brief.get("pass_score", 70))

    base["checks"] = checks
    base["failed_checks"] = failed
    base["critical_failed"] = critical_failed
    base["score"] = round(score, 1)
    base["passed"] = bool(score >= pass_score and not critical_failed)
    base["pass_score"] = pass_score
    return base


__all__ = [
    "DEFAULT_WEIGHTS",
    "DEFAULT_CRITICAL",
    "LoadedImage",
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
