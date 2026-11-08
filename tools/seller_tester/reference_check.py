"""Reference-subject check for the two reference input modes.

The product-picture service has exactly three inputs (ty/MANDATE.md): the
prompt alone, stored references from earlier generations, and references the
user uploads. A reference-mode brief is only satisfied if the produced picture
actually contains the subject from the reference — not merely plausible pixels.

That cannot be proved with pixels alone, so this module implements a *measurable
proxy* and never claims more than that:

* dominant-colour agreement (chroma-weighted hue histogram intersection), and
* silhouette aspect agreement (bounding box of the separable subject).

Anything this proxy cannot measure is reported as `cannot_verify`, which counts
as a failure in scoring. It is never a pass. The optional local vision judge
remains the semantic second opinion; it is off by default.

Calibration on this checkout (reference `renders/smoke_main_2000.png`, the Mogra
Organic pouch) is recorded in `reports/ty/sel01_picture_modes.md`; the defaults
below sit inside that measured gap. The proxy is coarse by construction and its
known false positives are documented there rather than hidden.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

# Only these trees may supply a stored reference asset.
REFERENCE_ROOTS = (
    "renders/",
    "generated_images/",
    "Northstar_backend/data/studio_generated/",
)

CHROMA_MIN = 30.0
HUE_BINS = 12
CORNER_PATCH = 16
BACKGROUND_DISTANCE = 28

DEFAULT_MIN_COLOUR = 0.62
DEFAULT_MAX_ASPECT_RATIO = 1.6


def _check(**kw: Any) -> Dict[str, Any]:
    kw.setdefault("skipped", False)
    kw.setdefault("cannot_verify", False)
    kw["ok"] = bool(kw.get("ok", False))
    kw["check"] = "reference_subject"
    return kw


def _cannot_verify(reason: str, **extra: Any) -> Dict[str, Any]:
    return _check(ok=False, cannot_verify=True, detail=f"cannot verify: {reason}", **extra)


def normalise_reference_path(value: Any, repo_root: str | Path = REPO_ROOT
                             ) -> Tuple[Optional[Path], str]:
    """Resolve a stored-asset reference inside the allowed trees.

    Returns (path, reason). A path outside the allowed trees, an absolute path
    or a missing file returns (None, reason) — the caller turns that into a
    `cannot_verify` failure. Nothing here guesses a replacement asset.
    """
    if not isinstance(value, str) or not value.strip():
        return None, "reference path is empty"
    raw = value.strip().replace("\\", "/")
    if raw.startswith("/") or ":" in raw:
        return None, f"reference path must be repo-relative ({value!r})"
    if ".." in Path(raw).parts:
        return None, f"reference path escapes the repository ({value!r})"
    if not any(raw.startswith(root) for root in REFERENCE_ROOTS):
        return None, (f"reference path is outside the allowed asset roots "
                      f"{REFERENCE_ROOTS} ({value!r})")
    target = Path(repo_root) / raw
    if not target.is_file():
        return None, f"reference asset is not on disk ({raw})"
    return target, ""


def subject_mask(rgb: np.ndarray) -> np.ndarray:
    """Pixels that differ from the corner-sampled background.

    When the corners do not describe a background (a full-bleed picture), the
    whole frame is the subject. When they describe almost nothing, the caller
    ends up with an empty mask and the check reports `cannot_verify`.
    """
    height, width = rgb.shape[:2]
    size = max(4, min(CORNER_PATCH, height // 8, width // 8))
    patches = (
        rgb[:size, :size],
        rgb[:size, width - size:],
        rgb[height - size:, :size],
        rgb[height - size:, width - size:],
    )
    background = np.median(
        np.array([np.median(p.reshape(-1, 3), axis=0) for p in patches]), axis=0)
    difference = np.abs(rgb.astype(np.int16) - background.astype(np.int16)).max(axis=2)
    mask = difference > BACKGROUND_DISTANCE
    coverage = float(mask.mean())
    if coverage > 0.90:
        # No separable background: the subject fills the frame.
        return np.ones((height, width), dtype=bool)
    return mask


def dominant_hue(rgb: np.ndarray, chroma_min: float = CHROMA_MIN,
                 bins: int = HUE_BINS) -> Optional[np.ndarray]:
    """Chroma-weighted hue histogram of the subject pixels, or None.

    None means "there is not enough colour to compare" — reported as
    `cannot_verify`, never as agreement.
    """
    mask = subject_mask(rgb)
    pixels = rgb[mask].reshape(-1, 3).astype(np.float32)
    if pixels.size == 0:
        return None
    high = pixels.max(axis=1)
    low = pixels.min(axis=1)
    chroma = high - low
    keep = chroma >= chroma_min
    if int(keep.sum()) < max(16, int(0.01 * pixels.shape[0])):
        return None
    pixels = pixels[keep]
    chroma = chroma[keep]
    red, green, blue = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    hue = np.zeros(pixels.shape[0], dtype=np.float32)
    max_is_red = high[keep] == red
    max_is_green = (high[keep] == green) & ~max_is_red
    rest = ~max_is_red & ~max_is_green
    hue[max_is_red] = ((green[max_is_red] - blue[max_is_red]) / chroma[max_is_red]) % 6
    hue[max_is_green] = ((blue[max_is_green] - red[max_is_green]) / chroma[max_is_green]) + 2
    hue[rest] = ((red[rest] - green[rest]) / chroma[rest]) + 4
    hue *= 60.0
    histogram = np.zeros(bins, dtype=np.float32)
    index = (hue / (360.0 / bins)).astype(np.int32) % bins
    np.add.at(histogram, index, chroma)
    total = float(histogram.sum())
    if total <= 0.0:
        return None
    return histogram / total


def silhouette_aspect(rgb: np.ndarray) -> Optional[float]:
    """Width/height of the subject bounding box, or None when there is no subject."""
    mask = subject_mask(rgb)
    rows, columns = np.where(mask)
    if rows.size == 0:
        return None
    width = int(columns.max() - columns.min() + 1)
    height = int(rows.max() - rows.min() + 1)
    if width < 2 or height < 2:
        return None
    return width / float(height)


def colour_agreement(produced: np.ndarray, reference: np.ndarray) -> Optional[float]:
    """Hue-histogram intersection in 0..1, or None when colour is unmeasurable."""
    produced_hue = dominant_hue(produced)
    reference_hue = dominant_hue(reference)
    if produced_hue is None or reference_hue is None:
        return None
    return float(np.minimum(produced_hue, reference_hue).sum())


def check_reference_subject(produced: np.ndarray, reference: np.ndarray, *,
                            min_colour: float = DEFAULT_MIN_COLOUR,
                            max_aspect_ratio: float = DEFAULT_MAX_ASPECT_RATIO
                            ) -> Dict[str, Any]:
    """Compare a produced picture with its reference image."""
    agreement = colour_agreement(produced, reference)
    if agreement is None:
        return _cannot_verify(
            "one of the pictures has too little colour to compare "
            "(<1% of subject pixels above chroma 30)")
    produced_aspect = silhouette_aspect(produced)
    reference_aspect = silhouette_aspect(reference)
    if produced_aspect is None or reference_aspect is None:
        return _cannot_verify("no separable subject silhouette in one of the pictures")
    ratio = max(produced_aspect, reference_aspect) / min(produced_aspect, reference_aspect)
    colour_ok = agreement >= float(min_colour)
    aspect_ok = ratio <= float(max_aspect_ratio)
    return _check(
        ok=bool(colour_ok and aspect_ok),
        detail=(f"dominant-colour agreement {agreement:.3f} "
                f"(min {float(min_colour):.2f}); silhouette aspect "
                f"{produced_aspect:.2f} vs {reference_aspect:.2f} "
                f"(ratio {ratio:.2f}, max {float(max_aspect_ratio):.2f})"),
        colour_agreement=round(agreement, 4),
        min_colour=float(min_colour),
        produced_aspect=round(produced_aspect, 3),
        reference_aspect=round(reference_aspect, 3),
        aspect_ratio=round(ratio, 3),
        max_aspect_ratio=float(max_aspect_ratio),
    )


def load_reference_rgb(reference: Dict[str, Any], *,
                       repo_root: str | Path = REPO_ROOT
                       ) -> Tuple[Optional[np.ndarray], str, Optional[str]]:
    """Load the reference image for a brief's `reference` object.

    Returns (rgb, reason, resolved_path). `rgb` is None when the reference
    cannot be read; `reason` then explains why in plain words.
    """
    if not isinstance(reference, dict):
        return None, "brief declares no reference object", None
    kind = reference.get("kind")
    if kind == "stored_asset":
        path, reason = normalise_reference_path(reference.get("path"), repo_root)
    elif kind == "uploaded_file":
        descriptor = reference.get("descriptor") or {}
        filename = str(descriptor.get("filename") or "").strip()
        path, reason = normalise_reference_path(reference.get("path"), repo_root)
        if path is None and reason.startswith("reference path is empty"):
            reason = (f"no local copy of the uploaded file "
                      f"({filename or 'unnamed upload'}); the upload was not "
                      "present in this checkout")
    else:
        return None, f"unknown reference kind {kind!r}", None

    if path is None:
        return None, reason, None
    try:
        from .scorers import load_image

        loaded = load_image(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        return None, f"reference asset is unreadable ({type(exc).__name__})", str(path)
    return loaded.rgb, "", str(path)


def reference_check_for_brief(produced_rgb: np.ndarray, brief: Dict[str, Any], *,
                              repo_root: str | Path = REPO_ROOT) -> Dict[str, Any]:
    """Full reference check for one brief: resolve, load, compare, or refuse."""
    mode = brief.get("source_mode") or "unclassified"
    if mode == "prompt_only":
        return {"ok": True, "skipped": True, "cannot_verify": False,
                "detail": "prompt-only brief: there is no reference to verify",
                "check": "reference_subject"}
    if mode not in ("stored_reference", "uploaded_reference"):
        return _cannot_verify(f"brief has no usable input mode ({mode!r})")

    reference = brief.get("reference")
    rgb, reason, resolved = load_reference_rgb(reference, repo_root=repo_root)
    if rgb is None:
        return _cannot_verify(reason, reference_path=resolved)
    spec = (reference or {}).get("check") or {}
    verdict = check_reference_subject(
        produced_rgb, rgb,
        min_colour=float(spec.get("min_colour_agreement", DEFAULT_MIN_COLOUR)),
        max_aspect_ratio=float(spec.get("max_aspect_ratio", DEFAULT_MAX_ASPECT_RATIO)),
    )
    verdict["reference_path"] = resolved
    verdict["reference_kind"] = (reference or {}).get("kind")
    return verdict


__all__ = [
    "CHROMA_MIN",
    "DEFAULT_MAX_ASPECT_RATIO",
    "DEFAULT_MIN_COLOUR",
    "HUE_BINS",
    "REFERENCE_ROOTS",
    "check_reference_subject",
    "colour_agreement",
    "dominant_hue",
    "load_reference_rgb",
    "normalise_reference_path",
    "reference_check_for_brief",
    "silhouette_aspect",
    "subject_mask",
]
