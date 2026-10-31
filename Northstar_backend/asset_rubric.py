"""Offline conversion rubric (Benchmark Evaluator, deterministic half).

The CrewAI evaluator agent narrates; THIS module scores. Numbers must be
reproducible and testable, so the rubric is computed from pixels and from the
OCR gate - never from a model's opinion of its own output.

Metrics (0-1 each, then a 0-100 composite):

    contrast       Michelson contrast of the subject region
    fill           subject area vs frame, against the 85% listing target
    balance        distance of the subject centroid from the frame centre
    hook_density   edge energy - "does something stop the thumb at 200px?"
    legibility     1.0 when the intended copy is OCR-readable, else 0
    purity         share of pure-white background (main-image rule)

No network, no model call.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

TARGET_FILL = 0.85
WHITE = 250


def _lum(a: np.ndarray) -> np.ndarray:
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def metrics(png: bytes) -> Dict[str, float]:
    img = Image.open(BytesIO(png)).convert("RGB")
    a = np.asarray(img, dtype=np.float32)

    white = np.all(a >= WHITE, axis=-1)
    purity = float(white.mean())

    subject = ~white
    if subject.sum() < 50:
        return {"contrast": 0.0, "fill": 0.0, "balance": 0.0,
                "hook_density": 0.0, "purity": round(purity, 4), "subject_px": 0}

    ys, xs = np.where(subject)
    h, w = a.shape[:2]
    box_w = (xs.max() - xs.min() + 1) / w
    box_h = (ys.max() - ys.min() + 1) / h
    fill = float(max(box_w, box_h))          # longest side, the conservative reading

    lum = _lum(a)
    subj = lum[subject]
    hi, lo = float(np.percentile(subj, 95)), float(np.percentile(subj, 5))
    contrast = 0.0 if hi + lo <= 1 else (hi - lo) / (hi + lo)

    cx = float(xs.mean()) / w
    cy = float(ys.mean()) / h
    balance = max(0.0, 1.0 - 2.0 * (((cx - 0.5) ** 2 + (cy - 0.5) ** 2) ** 0.5))

    gx = np.abs(np.diff(lum, axis=1)).mean()
    gy = np.abs(np.diff(lum, axis=0)).mean()
    hook_density = float(min(1.0, (gx + gy) / 24.0))

    return {"contrast": round(contrast, 4), "fill": round(fill, 4),
            "balance": round(balance, 4), "hook_density": round(hook_density, 4),
            "purity": round(purity, 4), "subject_px": int(subject.sum())}


def legibility(png: bytes, expected: Optional[list] = None) -> Dict[str, Any]:
    """1.0 only when the intended copy is actually readable. Never guessed."""
    try:
        import text_fidelity
        res = text_fidelity.check_text_in_image(png)
    except Exception as exc:  # noqa: BLE001 - OCR absence is reported, not faked
        return {"legibility": 0.0, "ocr": f"unavailable: {type(exc).__name__}"}
    if res.get("status") != "ok":
        return {"legibility": 0.0, "ocr": res.get("status")}
    words = " ".join(res.get("words") or []).lower()
    if expected:
        hits = sum(1 for w in expected if w.lower() in words)
        return {"legibility": round(min(1.0, hits / max(1, len(expected))), 4),
                "hits": hits, "boxes": res.get("boxes")}
    return {"legibility": 1.0 if res.get("contains_text") else 0.0,
            "boxes": res.get("boxes")}


def score_hero(png: bytes, *, expected_copy: Optional[list] = None) -> Dict[str, Any]:
    m = metrics(png)
    leg = legibility(png, expected_copy)

    fill_penalty = abs(m["fill"] - TARGET_FILL)
    composite = (
        m["contrast"] * 20
        + max(0.0, 1.0 - fill_penalty * 3) * 25
        + m["balance"] * 10
        + m["hook_density"] * 15
        + leg["legibility"] * 20
        + m["purity"] * 10
    )
    defects = []
    if m["purity"] < 0.35:
        defects.append("background_not_white_enough")
    if m["fill"] < 0.6:
        defects.append("subject_too_small")
    if m["fill"] > 0.95:
        defects.append("subject_touching_frame")
    if m["balance"] < 0.6:
        defects.append("subject_off_centre")
    if leg["legibility"] < 0.5:
        defects.append("copy_not_readable")
    if m["hook_density"] < 0.25:
        defects.append("low_thumb_stop_energy")

    return {
        "score": round(min(100.0, composite), 1),
        "metrics": m,
        "legibility": leg,
        "defects": defects,
        "verdict": "pass" if composite >= 70 and not defects else "revise",
        "rubric": "offline: contrast/fill/balance/hook_density/legibility/purity",
    }


__all__ = ["metrics", "legibility", "score_listing", "score_hook", "score", "score_hero", "CLASSES", "TARGET_FILL"]

# â”€â”€ artifact-class scoring (split) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# A listing main image and an ad creative are judged by OPPOSITE criteria: the
# listing wants a calm, pure-white, product-only frame; the ad wants energy and
# a hook. One score for both forced a false verdict ("revise" on a compliant
# hero because its thumb-stop energy was low). Two functions, one router.

LISTING_PURITY = 0.90
LISTING_FILL = (0.80, 0.92)
HOOK_MIN = 0.25


def score_listing(png: bytes, *, expected_copy: Optional[list] = None) -> Dict[str, Any]:
    """Strict compliance: pure white, product fills 80-92%, nothing else."""
    m = metrics(png)
    leg = legibility(png, expected_copy)
    defects = []
    if m["purity"] < LISTING_PURITY:
        defects.append("background_not_white_enough")
    if m["fill"] < LISTING_FILL[0]:
        defects.append("subject_too_small")
    if m["fill"] > LISTING_FILL[1]:
        defects.append("subject_touching_frame")
    if m["balance"] < 0.6:
        defects.append("subject_off_centre")
    if leg["legibility"] < 0.5:
        defects.append("copy_not_readable")
    if m["purity"] < 0.5 and "contact_shadow_or_floor" not in defects:
        defects.append("contact_shadow_or_floor")

    composite = (
        min(1.0, m["purity"] / LISTING_PURITY) * 40
        + max(0.0, 1.0 - abs(m["fill"] - 0.86) * 8) * 30
        + m["balance"] * 10
        + leg["legibility"] * 20
    )
    return {
        "class": "listing",
        "score": round(min(100.0, composite), 1),
        "metrics": m,
        "legibility": leg,
        "defects": defects,
        "verdict": "pass" if not defects else "revise",
        "rubric": "listing: purity>=%.2f, fill 80-92%%, balance, OCR legibility" % LISTING_PURITY,
    }


def score_hook(png: bytes) -> Dict[str, Any]:
    """Ad / A+ band: energy, contrast and a stop-the-thumb read. Purity ignored."""
    m = metrics(png)
    defects = []
    if m["hook_density"] < HOOK_MIN:
        defects.append("low_thumb_stop_energy")
    if m["contrast"] < 0.25:
        defects.append("flat_contrast")
    if m["subject_px"] == 0:
        defects.append("no_subject")

    composite = (m["hook_density"] * 45 + m["contrast"] * 35
                 + m["balance"] * 10 + min(1.0, m["fill"]) * 10)
    return {
        "class": "hook",
        "score": round(min(100.0, composite), 1),
        "metrics": m,
        "defects": defects,
        "verdict": "pass" if not defects else "revise",
        "rubric": "hook: edge energy>=%.2f, contrast>=0.25, subject present" % HOOK_MIN,
    }


CLASSES = {"listing": score_listing, "hero": score_listing,
           "ad": score_hook, "aplus": score_hook, "social": score_hook}


def score(png: bytes, artifact_class: str = "listing", *,
          expected_copy: Optional[list] = None) -> Dict[str, Any]:
    """Route by artefact class. Unknown classes are refused, never defaulted."""
    key = str(artifact_class or "").strip().lower()
    if key not in CLASSES:
        raise KeyError(f"unknown artifact class {artifact_class!r}; known: {sorted(CLASSES)}")
    if key in ("listing", "hero"):
        return score_listing(png, expected_copy=expected_copy)
    return score_hook(png)


def score_hero(png: bytes, *, expected_copy: Optional[list] = None) -> Dict[str, Any]:
    """Back-compat alias: a hero IS a listing image."""
    return score_listing(png, expected_copy=expected_copy)

