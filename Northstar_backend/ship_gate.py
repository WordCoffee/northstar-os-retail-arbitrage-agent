"""Review gate in front of any image the product presents.

The legibility gate (`mockup_quality.assert_legible`) answers one question: can a
human read the wordmark and the net weight? It cannot answer "is this the right
product?" or "is this image good enough to deliver?", and it is only called by
the product-picture path. This module is the missing second question:

    identity    the render must match the reference product photo (pHash + SSIM)
    legibility  the same OCR/sharpness contract, when text is expected
    preference  a human-preference score (HPSv2) when a scorer is configured
    adherence   prompt adherence (PickScore) when a scorer is configured

It returns evidence, never a bare boolean, and it is deliberately honest about
what it could not measure: a render with no evaluable blocking axis is
``unscored`` (a candidate, not a deliverable), and a required scorer that is not
configured is ``needs_review`` - never ``passed``.

Scorers are injected, not guessed. ``preference_scorer`` and
``adherence_scorer`` are callables ``(png_bytes, brief) -> float``; the weights
are on disk under ``ComfyUI/models/_incoming`` but the ML runtime (torch) is not
installed in the service environment, so the gate reports the axis as
unavailable instead of pretending. Thresholds are parameters with documented
defaults; the plan (reports/ty/creative_pipeline_plan_20261103.md §6.3) says the
first thresholds come from a scored baseline of the owner's own reference
images, so these are provisional floors, not a final bar.

No provider call, no network, no cost.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image

import mockup_quality as mq

ImageLike = Union[Image.Image, bytes, bytearray, str, Path, None]
Scorer = Optional[Callable[[bytes, str], float]]

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "image_review.json"

#: Provisional identity floors, calibrated 2026-11-04 on a same-seed pair
#: (reference-conditioned vs text-only, 512px): the reference render measured
#: pHash 22 / SSIM 0.484, the invented one pHash 24 / SSIM 0.231. Both must clear
#: the floor (phash distance AND ssim), or SSIM alone must be very high - a hash
#: that drifts by a few bits on a legitimate re-light is not a different product.
DEFAULT_MAX_PHASH_DISTANCE = 24
DEFAULT_MIN_SSIM = 0.40
#: SSIM at or above this passes even when the hash drifted (same picture, new
#: light). Calibrate from the owner's reference set before tightening.
SSIM_RESCUE = 0.55
#: Surface used when the caller names none.
DEFAULT_SURFACE = "default"

_SSIM_SIZE = 256


def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def surface_policy(surface: Optional[str] = None,
                   config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Floors and requirements for one surface.

    Calibration 2026-11-04 (state/evidence/image_review_calibration_20261104.json):
    the product pictures scored HPSv2 0.236-0.241 / PickScore 19.4-21.4, while the
    flat label artwork scored 0.151 / 19.0. Designed typography frames (a TikTok
    frame) score low by nature, so they are recorded, not blocked.
    """
    cfg = config if config is not None else load_config()
    surfaces = cfg.get("surfaces") or {}
    policy = surfaces.get(str(surface or DEFAULT_SURFACE)) or surfaces.get(DEFAULT_SURFACE) or {}
    return {
        "preference_floor": policy.get("preference_floor"),
        "adherence_floor": policy.get("adherence_floor"),
        "require_scorers": bool(policy.get("require_scorers", False)),
    }


def _default_scorer(axis: str):
    """The installed scorer for an axis, or None when it cannot run."""
    try:
        import image_review_scorers as scorers  # noqa: WPS433

        if not scorers.available().get("ok"):
            return None
        return scorers.default_scorer(axis)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# perceptual measurement
# ---------------------------------------------------------------------------

def _load(image: ImageLike) -> Image.Image:
    if image is None:
        raise ValueError("no image supplied")
    if isinstance(image, (bytes, bytearray)):
        return Image.open(io.BytesIO(bytes(image))).convert("RGB")
    if isinstance(image, (str, Path)):
        return Image.open(str(image)).convert("RGB")
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    raise TypeError("image must be a path, bytes or a PIL Image")


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _dct_matrix(n: int) -> np.ndarray:
    """Orthonormal DCT-II matrix (rows are frequencies)."""
    k = np.arange(n)
    m = np.cos(np.pi * (2 * k[None, :] + 1) * k[:, None] / (2.0 * n))
    m[0, :] /= np.sqrt(2.0)
    return m * np.sqrt(2.0 / n)


def phash(img: Image.Image, hash_size: int = 8, highfreq: int = 4) -> int:
    """64-bit perceptual hash (DCT of a 32x32 greyscale thumbnail)."""
    size = hash_size * highfreq
    small = np.asarray(img.convert("L").resize((size, size), Image.LANCZOS),
                       dtype=np.float64)
    dct = _dct_matrix(size) @ small @ _dct_matrix(size).T
    low = dct[:hash_size, :hash_size].flatten()
    median = float(np.median(low[1:]))
    bits = 0
    for value in low:
        bits = (bits << 1) | (1 if value > median else 0)
    return bits


def phash_distance(a: Image.Image, b: Image.Image) -> int:
    return int((phash(a) ^ phash(b)).bit_count())


def ssim(a: Image.Image, b: Image.Image, size: int = _SSIM_SIZE) -> float:
    """Global SSIM on a fixed-size greyscale view of both images."""
    x = np.asarray(a.convert("L").resize((size, size), Image.LANCZOS), dtype=np.float64)
    y = np.asarray(b.convert("L").resize((size, size), Image.LANCZOS), dtype=np.float64)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    mx, my = x.mean(), y.mean()
    vx, vy = x.var(), y.var()
    cov = ((x - mx) * (y - my)).mean()
    return float(((2 * mx * my + c1) * (2 * cov + c2))
                 / ((mx * mx + my * my + c1) * (vx + vy + c2)))


def _axis(status: str, *, blocking: bool, **fields: Any) -> Dict[str, Any]:
    return {"status": status, "blocking": bool(blocking), **fields}


def _scorer_axis(scorer: Scorer, png: bytes, brief: str, *,
                 name: str, floor: Optional[float],
                 required: bool) -> Dict[str, Any]:
    if scorer is None:
        return _axis("unavailable", blocking=bool(required), name=name,
                     reason=f"no_{name}_scorer_configured", required=bool(required))
    try:
        value = float(scorer(png, brief or ""))
    except Exception as exc:  # noqa: BLE001 - an error is not a verdict
        return _axis("error", blocking=True, name=name, reason=str(exc)[:200],
                     required=bool(required))
    ok = (floor is None) or (value >= float(floor))
    return _axis("pass" if ok else "fail", blocking=bool(floor is not None and required),
                 name=name, score=round(value, 4), floor=floor,
                 required=bool(required))


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

def review_image(image: ImageLike, *, brief: str = "",
                 reference: ImageLike = None,
                 wordmark: Optional[str] = None,
                 net_weight: Optional[str] = None,
                 require_text: bool = False,
                 surface: Optional[str] = None,
                 max_phash_distance: Optional[int] = None,
                 min_ssim: Optional[float] = None,
                 require_preference: Optional[bool] = None,
                 preference_floor: Optional[float] = None,
                 preference_scorer: Scorer = None,
                 require_adherence: Optional[bool] = None,
                 adherence_floor: Optional[float] = None,
                 adherence_scorer: Scorer = None,
                 use_default_scorers: bool = True) -> Dict[str, Any]:
    """Review one rendered image and say whether it may be delivered.

    Thresholds and requirements come from ``config/image_review.json`` for the
    named ``surface``; explicit arguments win. The scorers (PickScore, HPSv2)
    are loaded per call in a child process when they are installed, unless
    ``use_default_scorers`` is false (offline tests and the probe).

    ``status`` is one of:

    * ``passed``      - every required axis was measured and passed;
    * ``refused``     - a measured axis failed, with the reason;
    * ``needs_review``- a required scorer is not configured (never a pass);
    * ``unscored``    - nothing blocking could be measured (a candidate only).
    """
    policy = surface_policy(surface)
    thresholds = load_config().get("thresholds") or {}
    if max_phash_distance is None:
        max_phash_distance = int(thresholds.get("max_phash_distance",
                                                DEFAULT_MAX_PHASH_DISTANCE))
    if min_ssim is None:
        min_ssim = float(thresholds.get("min_ssim", DEFAULT_MIN_SSIM))
    if require_preference is None:
        require_preference = policy["require_scorers"]
    if require_adherence is None:
        require_adherence = policy["require_scorers"]
    if preference_floor is None:
        preference_floor = policy["preference_floor"]
    if adherence_floor is None:
        adherence_floor = policy["adherence_floor"]
    if preference_scorer is None and use_default_scorers and require_preference:
        preference_scorer = _default_scorer("preference")
    if adherence_scorer is None and use_default_scorers and require_adherence:
        adherence_scorer = _default_scorer("adherence")

    img = _load(image)
    png = _png_bytes(img)
    axes: Dict[str, Dict[str, Any]] = {}
    reasons: list[str] = []

    # 1. legibility ---------------------------------------------------------
    need_text = bool(require_text or wordmark or net_weight)
    if need_text:
        try:
            leg = mq.assert_legible(png, wordmark=wordmark, net_weight=net_weight)
        except Exception as exc:  # noqa: BLE001 - fail closed
            leg = {"ok": False, "reason": f"legibility_error: {exc}"}
        axes["legibility"] = _axis(
            "pass" if leg.get("ok") else "fail", blocking=True,
            reason=leg.get("reason") or "", words=(leg.get("words") or [])[:12],
            sharpness=leg.get("sharpness"), text_height_px=leg.get("text_height_px"))
        if not leg.get("ok"):
            reasons.append("legibility: " + str(leg.get("reason") or "unreadable"))
    else:
        axes["legibility"] = _axis("not_applicable", blocking=False,
                                   reason="no text expected on this surface")

    # 2. identity -----------------------------------------------------------
    if reference is not None:
        ref = _load(reference)
        distance = phash_distance(img, ref)
        similarity = ssim(img, ref)
        ok = ((distance <= int(max_phash_distance) and similarity >= float(min_ssim))
              or similarity >= SSIM_RESCUE)
        axes["identity"] = _axis(
            "pass" if ok else "fail", blocking=True,
            phash_distance=distance, max_phash_distance=int(max_phash_distance),
            ssim=round(similarity, 4), min_ssim=float(min_ssim),
            rescue=SSIM_RESCUE)
        if not ok:
            reasons.append(
                f"identity: phash distance {distance} (max {max_phash_distance}) and "
                f"ssim {similarity:.2f} (min {min_ssim:.2f}, rescue {SSIM_RESCUE:.2f}) "
                f"against the reference")
    else:
        axes["identity"] = _axis("not_applicable", blocking=False,
                                 reason="no reference image supplied")

    # 3. recorded preference / adherence -----------------------------------
    axes["preference"] = _scorer_axis(
        preference_scorer, png, brief, name="preference", floor=preference_floor,
        required=require_preference)
    axes["adherence"] = _scorer_axis(
        adherence_scorer, png, brief, name="adherence", floor=adherence_floor,
        required=require_adherence)

    blocking = [a for a in axes.values() if a.get("blocking")]
    failed = [name for name, a in axes.items()
              if a.get("blocking") and a.get("status") in ("fail", "error")]
    unavailable_required = [name for name, a in axes.items()
                            if a.get("status") == "unavailable" and a.get("required")]
    evaluated_blocking = [name for name, a in axes.items()
                          if a.get("blocking") and a.get("status") in ("pass", "fail")]
    evaluated = [name for name, a in axes.items() if a.get("status") in ("pass", "fail")]

    if failed:
        status = "refused"
    elif unavailable_required:
        status = "needs_review"
    elif not evaluated_blocking:
        status = "unscored"
    else:
        status = "passed"

    return {
        "status": status,
        "ok": status == "passed",
        "deliverable": status == "passed",
        "candidate": status in ("unscored", "needs_review"),
        "reasons": reasons,
        "failed_axes": failed,
        "required_unavailable": unavailable_required,
        "evaluated_axes": evaluated,
        "evaluated_blocking_axes": evaluated_blocking,
        "blocking_axes": [name for name, a in axes.items() if a.get("blocking")],
        "surface": str(surface or DEFAULT_SURFACE),
        "axes": axes,
        "thresholds": {"max_phash_distance": int(max_phash_distance),
                       "min_ssim": float(min_ssim), "ssim_rescue": SSIM_RESCUE,
                       "preference_floor": preference_floor,
                       "adherence_floor": adherence_floor,
                       "provisional": True},
        "measurement": {"width": img.width, "height": img.height},
    }


def manifest_block(report: Dict[str, Any]) -> Dict[str, Any]:
    """Compact block for a manifest / task evidence record."""
    if not isinstance(report, dict):
        return {"status": "error"}
    return {
        "status": report.get("status"),
        "ok": report.get("ok"),
        "reasons": list(report.get("reasons") or []),
        "failed_axes": list(report.get("failed_axes") or []),
        "required_unavailable": list(report.get("required_unavailable") or []),
        "surface": report.get("surface"),
        "axes": {name: {k: v for k, v in axis.items()
                        if k in ("status", "blocking", "score", "floor",
                                 "phash_distance", "ssim", "reason")}
                 for name, axis in (report.get("axes") or {}).items()},
        "thresholds": report.get("thresholds"),
    }


def reference_from(params: Optional[Dict[str, Any]]) -> Optional[str]:
    """Read the reference image path out of a step's params, if one is named."""
    params = params or {}
    for key in ("reference", "reference_image", "reference_path"):
        value = params.get(key)
        if value:
            return str(value)
    assets = params.get("reference_assets") or []
    if isinstance(assets, (list, tuple)) and assets:
        return str(assets[0])
    return None


__all__ = ["review_image", "manifest_block", "phash", "phash_distance", "ssim",
           "reference_from", "load_config", "surface_policy",
           "DEFAULT_MAX_PHASH_DISTANCE", "DEFAULT_MIN_SSIM"]
