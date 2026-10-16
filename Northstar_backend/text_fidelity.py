"""Text Fidelity — the 'letters are checked and fixed' pipeline for renders.

Why this exists (2026-10-16): Northstar's own blueprint says it plainly —
"Render on-image text as vector, never generated. The most-repeated seller
complaint is garbled on-image text." (MASTER_BLUEPRINT #5; compliance.js). The
generation lane was NOT enforcing that rule: a full typographic brief went
straight into FLUX, so the diffusion model painted ornamental gibberish
("MUSHROOM POWEE R", broken Supplement Facts blocks, wrong weights).

This module closes the loop in two halves:

FIX (pre-render): ``sanitize_brief_for_render`` strips typographic demands
(brand names, wordmarks, weights, barcode/QR/Supplement-Facts asks, all
ALL-CAPS runs) out of the brief and appends an explicit blank-surface
suppression phrase. The model is asked for MATERIAL + ILLUSTRATION + PALETTE
only; real letters get composited later with the studio's vector text layer.

CHECK (post-render): ``check_text_in_image`` runs a real offline OCR
(rapidocr-onnxruntime, CPU, no network) over the rendered PNG and reports
whether lettering is present — with a word sample and match test against the
expected brand terms. Unavailable OCR degrades honestly to status
"unavailable" (never a fake pass).

Everything local, deterministic where possible, and testable offline.
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel  # noqa: F401  (kept for API context in docstrings)

from design_studio_api import studio_account

router = APIRouter(prefix="/api/design-studio", tags=["design-studio-text"])

SUPPRESSION_PHRASE = (
    "Blank unprinted matte packaging surface shown as pure material, finish and "
    "botanical illustration only: no lettering, no words, no typography, no logo, "
    "no barcode, no QR code, no captions, no watermark of any kind"
)

# ── FIX: prompt guard ───────────────────────────────────────────────────────

# A line is a typographic demand if it asks for any of this in words.
_DEMAND_LINE = re.compile(
    r"(?i)\b(text|lettering|letters|wordmark|wordmark|typograph\w*|serif|sans[- ]?serif|font|"
    r"tagline|headline|footer text|copy block|description block|barcode|upc\b|qr code|"
    r"supplement facts|nutrition|logo|watermark|icon row|reserved zone|"
    r"must read|read clearly|sized to read|legible)\b"
)

_QUOTED = re.compile(r"[\"“”'‘’][^\"“”'‘’]{2,80}[\"“”'‘’]")
_ALL_CAPS_RUN = re.compile(r"\b(?:[A-Z][A-Z0-9'&.\-]*\s+){1,4}[A-Z][A-Z0-9'&.\-]*\b")
_BRAND_SUFFIX_RUN = re.compile(
    r"\b[A-Z][a-z']{2,}\s+(?:Organics|Foods|Naturals|Botanicals|Brands|Labs|Company|LLC|Inc|Co)\b")
_WEIGHT_TOKEN = re.compile(r"\b\d+(?:\.\d+)?\s?(?:oz|g|lb|kg)\b", re.IGNORECASE)
_EST_YEAR = re.compile(r"\bEST\.?\s*\d{2,4}\b", re.IGNORECASE)
_DIMENSIONS = re.compile(r"\b\d+(?:\.\d+)?\s?mm\b")


def _extract_expected_terms(brief: str) -> List[str]:
    """Brand/product strings the brief expects to SEE on the pack (they get
    composited as vector text later - the check compares against them)."""
    terms: List[str] = []
    for m in _QUOTED.finditer(brief or ""):
        t = m.group(0)[1:-1].strip()
        if t and t not in terms:
            terms.append(t)
    for m in _ALL_CAPS_RUN.finditer(brief or ""):
        t = m.group(0).strip()
        if len(t) >= 3 and t not in terms:
            terms.append(t)
    for m in _BRAND_SUFFIX_RUN.finditer(brief or ""):
        t = m.group(0).strip()
        if t and t not in terms:
            terms.append(t)
    return terms[:12]


def sanitize_brief_for_render(brief: str) -> Dict[str, Any]:
    """Strip typographic demands out of a design brief for the image model.

    Returns a dict with the render prompt, what was suppressed (honest record),
    and the expected on-pack terms (for the later vector-text layer + checks).
    """
    expected = _extract_expected_terms(brief or "")
    kept: List[str] = []
    suppressed: List[str] = []
    for raw_line in (brief or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _DEMAND_LINE.search(line):
            suppressed.append(line[:160])
            continue
        # inside kept lines: strip quoted strings, ALL-CAPS runs, brand runs,
        # weights, EST years, then any previously extracted expected term
        cleaned = _QUOTED.sub(" ", line)
        cleaned = _ALL_CAPS_RUN.sub(" ", cleaned)
        cleaned = _BRAND_SUFFIX_RUN.sub(" ", cleaned)
        cleaned = _WEIGHT_TOKEN.sub(" ", cleaned)
        cleaned = _EST_YEAR.sub(" ", cleaned)
        for term in expected:
            cleaned = re.sub(re.escape(term), " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -·:;,")
        if len(cleaned) >= 12:
            kept.append(cleaned)
        elif line:
            suppressed.append(line[:160])

    body = " \n".join(kept).strip()
    for term in expected:  # belt-and-braces: expected terms never reach the model
        body = re.sub(re.escape(term), " ", body, flags=re.IGNORECASE)
    body = re.sub(r"\s{2,}", " ", body).strip()
    render_prompt = (body + "\n" if body else "") + SUPPRESSION_PHRASE
    return {
        "render_prompt": render_prompt,
        "suppressed_lines": suppressed,
        "suppressed_count": len(suppressed),
        "kept_count": len(kept),
        "expected_terms": expected,
    }


def prepare_render_brief(brief: str, text_safe: bool) -> Dict[str, Any]:
    """Shared lane helper: {'brief': str, 'text_fidelity': dict|None}."""
    if not text_safe:
        return {"brief": brief, "text_fidelity": None}
    tf = sanitize_brief_for_render(brief)
    return {
        "brief": tf["render_prompt"],
        "text_fidelity": {
            "mode": "text_safe",
            "suppressed_count": tf["suppressed_count"],
            "kept_count": tf["kept_count"],
            "expected_terms": tf["expected_terms"],
        },
    }


# ── CHECK: OCR verification ─────────────────────────────────────────────────

_OCR_ENGINE = None
_OCR_STATE: Dict[str, Any] = {"status": "unloaded"}


def _get_ocr():
    """Lazy RapidOCR (CPU, offline). Returns (engine, error)."""
    global _OCR_ENGINE, _OCR_STATE
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE, None
    if _OCR_STATE["status"] == "unavailable":
        return None, _OCR_STATE.get("error")
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415 - heavy, lazy
        _OCR_ENGINE = RapidOCR()
        _OCR_STATE = {"status": "ready"}
        return _OCR_ENGINE, None
    except Exception as exc:  # noqa: BLE001 - honest degrade, never a fake pass
        _OCR_STATE = {"status": "unavailable", "error": str(exc)[:200]}
        return None, _OCR_STATE["error"]


def check_text_in_image(image_bytes: bytes) -> Dict[str, Any]:
    """OCR a rendered image. Never raises; never fabricates a result."""
    engine, err = _get_ocr()
    if engine is None:
        return {"engine": None, "status": "unavailable", "contains_text": None,
                "boxes": 0, "words": [], "error": err}
    try:
        from PIL import Image  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        result, _elapse = engine(arr)
    except Exception as exc:  # noqa: BLE001 - a broken decode is 'unknown', not 'pass'
        return {"engine": "rapidocr", "status": "error", "contains_text": None,
                "boxes": 0, "words": [], "error": str(exc)[:200]}
    words: List[str] = []
    boxes = 0
    for item in result or []:
        try:
            _box, text, score = item[0], str(item[1]), float(item[2])
        except Exception:  # noqa: BLE001
            continue
        if score < 0.5 or len(text.strip()) < 2:
            continue
        boxes += 1
        if len(words) < 12:
            words.append(text.strip()[:40])
    return {"engine": "rapidocr", "status": "ok", "contains_text": boxes > 0,
            "boxes": boxes, "words": words, "error": None}


def verify_asset_text(image_bytes: bytes, brief: Optional[str] = None,
                      text_safe: bool = False) -> Dict[str, Any]:
    """Combined verdict used by both generation lanes."""
    check = check_text_in_image(image_bytes)
    expected = _extract_expected_terms(brief or "")
    detected = " ".join(check.get("words") or []).lower()
    matched = [t for t in expected if t.lower() in detected]
    if check["status"] != "ok":
        verdict = "unverified"
    elif check["contains_text"] is False:
        verdict = "text_free"
    elif text_safe and matched:
        verdict = "text_present_matches_expected"  # rare: model nailed the brand text
    else:
        verdict = "text_present"
    return {
        "mode": "text_safe" if text_safe else "raw",
        "verdict": verdict,
        "expected_terms": expected,
        "matched_terms": matched,
        "check": check,
    }


# ── API: check an existing asset on demand ──────────────────────────────────

@router.post("/text-check/{asset_id}")
def text_check_asset(asset_id: str, acct: str = Depends(studio_account)):
    """Run the OCR text-fidelity check on a stored studio asset."""
    from pathlib import Path
    from data_layer import get_northstar_db

    db = get_northstar_db()
    asset = db.design_studio.assets.get_by_id(asset_id, account_id=acct)
    if not asset or not asset.get("storage_key"):
        raise HTTPException(status_code=404, detail="Asset not found")
    path = Path(__file__).resolve().parent / "data" / "studio_generated" / Path(str(asset["storage_key"])).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found")
    result = verify_asset_text(path.read_bytes(), brief=None, text_safe=False)
    return {"asset_id": asset_id, "name": asset.get("name"), "text_fidelity": result}
