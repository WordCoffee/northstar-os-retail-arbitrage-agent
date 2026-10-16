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


def _hard_scrub(text: str) -> str:
    """Aggressive retry pass: leave ONLY lowercase art language + hexes.

    Strips every digit (dimensions, weights, SKUs) and every capitalized word
    ("Mogra", "Organic", "Lion's Mane", "SKU") so nothing text-shaped reaches
    the model. Palette hex codes are split out first and restored untouched -
    they read as color, not type.
    """
    parts = re.split(r"(#[0-9A-Fa-f]{3,8}\b)", text)
    for i, part in enumerate(parts):
        if re.fullmatch(r"#[0-9A-Fa-f]{3,8}", part):
            continue  # a real palette hex - preserved untouched
        part = re.sub(r"\d+", " ", part)
        part = re.sub(r"\b[A-Z][A-Za-z'\-]*\b", " ", part)
        parts[i] = part
    text = "".join(parts)
    return re.sub(r"\s{2,}", " ", text).strip(" -·:;,")


def _clean_segment(text: str, expected: List[str]) -> str:
    """Shared inline cleaner for kept clauses."""
    cleaned = _QUOTED.sub(" ", text)
    cleaned = _ALL_CAPS_RUN.sub(" ", cleaned)
    cleaned = _BRAND_SUFFIX_RUN.sub(" ", cleaned)
    cleaned = _WEIGHT_TOKEN.sub(" ", cleaned)
    cleaned = _EST_YEAR.sub(" ", cleaned)
    cleaned = _DIMENSIONS.sub(" ", cleaned)
    for term in expected:
        cleaned = re.sub(re.escape(term), " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", cleaned).strip(" -·:;,")


def sanitize_brief_for_render(brief: str, hard: bool = False) -> Dict[str, Any]:
    """Strip typographic demands out of a design brief for the image model.

    hard=True is the retry escalation: after the normal pass it removes every
    remaining capitalized word and digit, because diffusion models will paint
    ANY text-shaped token as fake packaging copy.

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
        # Demand lines are handled at CLAUSE level: a sentence that also carries
        # art direction ("...warm charcoal-black matte instead of green. Text
        # reads ...") keeps the art clause and drops only the typographic one.
        segments = re.split(r"(?<=\.)\s+", line) if _DEMAND_LINE.search(line) else [line]
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            if _DEMAND_LINE.search(seg):
                suppressed.append(seg[:160])
                continue
            cleaned = _clean_segment(seg, expected)
            if len(cleaned) >= 12:
                kept.append(cleaned)
            else:
                suppressed.append(seg[:160])

    body = " \n".join(kept).strip()
    for term in expected:  # belt-and-braces: expected terms never reach the model
        body = re.sub(re.escape(term), " ", body, flags=re.IGNORECASE)
    body = re.sub(r"\s{2,}", " ", body).strip()
    if hard:
        body = _hard_scrub(body)
    render_prompt = (body + "\n" if body else "") + SUPPRESSION_PHRASE
    return {
        "render_prompt": render_prompt,
        "suppressed_lines": suppressed,
        "suppressed_count": len(suppressed),
        "kept_count": len(kept),
        "expected_terms": expected,
        "hard": hard,
    }


def prepare_render_brief(brief: str, text_safe: bool, hard: bool = False) -> Dict[str, Any]:
    """Shared lane helper: {'brief': str, 'text_fidelity': dict|None}."""
    if not text_safe:
        return {"brief": brief, "text_fidelity": None}
    tf = sanitize_brief_for_render(brief, hard=hard)
    return {
        "brief": tf["render_prompt"],
        "text_fidelity": {
            "mode": "text_safe_hard" if hard else "text_safe",
            "suppressed_count": tf["suppressed_count"],
            "kept_count": tf["kept_count"],
            "expected_terms": tf["expected_terms"],
            "render_prompt": tf["render_prompt"],
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


def _ocr_boxes(image_bytes: bytes):
    """(PIL image, [(x0,y0,x1,y1,text)]) or (None, error)."""
    engine, err = _get_ocr()
    if engine is None:
        return None, err
    try:
        from PIL import Image  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        result, _elapse = engine(arr)
    except Exception as exc:  # noqa: BLE001 - a broken decode is 'unknown', not 'pass'
        return None, str(exc)[:200]
    boxes = []
    for item in result or []:
        try:
            quad, text, score = item[0], str(item[1]), float(item[2])
        except Exception:  # noqa: BLE001
            continue
        if score < 0.5 or len(text.strip()) < 2:
            continue
        xs = [float(p[0]) for p in quad]
        ys = [float(p[1]) for p in quad]
        boxes.append((min(xs), min(ys), max(xs), max(ys), text.strip()[:40]))
    return (img, boxes), None


def check_text_in_image(image_bytes: bytes) -> Dict[str, Any]:
    """OCR a rendered image. Never raises; never fabricates a result."""
    parsed, err = _ocr_boxes(image_bytes)
    if parsed is None:
        return {"engine": "rapidocr" if err != "unavailable" else None,
                "status": "unavailable" if err == "unavailable" else "error",
                "contains_text": None, "boxes": 0, "words": [], "error": err}
    _img, boxes = parsed
    words = [b[4] for b in boxes][:12]
    return {"engine": "rapidocr", "status": "ok", "contains_text": len(boxes) > 0,
            "boxes": len(boxes), "words": words, "error": None}


def clean_text_regions(image_bytes: bytes, *, max_coverage: float = 0.5) -> Dict[str, Any]:
    """Clear OCR-detected glyph zones into a clean plate for the vector text layer.

    Fills each detected text rectangle with the median colour sampled from a
    thin band around it (matte surfaces shade smoothly, so a local median reads
    as blank material), then softens the patch edge. Deterministic geometry —
    nothing re-generated. Verdict after cleanup is re-checked by the caller.
    """
    parsed, err = _ocr_boxes(image_bytes)
    if parsed is None:
        return {"status": "unavailable", "error": err, "cleared": 0, "image": None,
                "boxes_before": 0, "regions": []}
    img, boxes = parsed
    if not boxes:
        return {"status": "ok", "cleared": 0, "image": image_bytes,
                "boxes_before": 0, "regions": []}
    from PIL import Image, ImageDraw, ImageFilter  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    work = img.copy()
    W, H = work.size
    arr = np.array(work)
    regions: List[List[int]] = []
    cleared = 0
    pad, band = 8, 12
    for (x0, y0, x1, y1, _t) in boxes:
        bw, bh = (x1 - x0), (y1 - y0)
        if bw <= 1 or bh <= 1 or (bw * bh) > max_coverage * W * H:
            continue
        rx0, ry0 = max(0, int(x0) - pad), max(0, int(y0) - pad)
        rx1, ry1 = min(W, int(x1) + pad), min(H, int(y1) + pad)
        bx0, by0 = max(0, rx0 - band), max(0, ry0 - band)
        bx1, by1 = min(W, rx1 + band), min(H, ry1 + band)
        outer = arr[by0:by1, bx0:bx1].reshape(-1, 3)
        mask = np.ones((by1 - by0, bx1 - bx0), dtype=bool)
        mask[(ry0 - by0):(ry1 - by0), (rx0 - bx0):(rx1 - bx0)] = False
        ring = outer[mask.reshape(-1)]
        color = tuple(int(c) for c in np.median(ring, axis=0)) if len(ring) else (255, 255, 255)
        patch = Image.new("RGB", (rx1 - rx0, ry1 - ry0), color)
        patch = patch.filter(ImageFilter.GaussianBlur(2.5))
        work.paste(patch, (rx0, ry0))
        ImageDraw.Draw(work).rectangle([rx0, ry0, rx1, ry1], outline=color)
        regions.append([rx0, ry0, rx1, ry1])
        cleared += 1
    if cleared == 0:
        return {"status": "ok", "cleared": 0, "image": image_bytes,
                "boxes_before": len(boxes), "regions": []}
    out = io.BytesIO()
    work.save(out, format="PNG")
    return {"status": "ok", "cleared": cleared, "image": out.getvalue(),
            "boxes_before": len(boxes), "regions": regions[:40]}


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


# ── Render guard: sanitize → render → OCR-check → bounded auto-rerun ────────

def render_with_text_guard(*, render_fn, brief: str, text_safe: bool,
                           max_attempts: int = 2) -> Dict[str, Any]:
    """The full FIX+CHECK loop shared by both generation lanes.

    render_fn(prompt) -> studio_generation output dict ({bytes, ext, ...}).
    Attempt 1 uses the normal sanitized prompt. If the OCR check finds
    lettering and text_safe is on, ONE retry runs with the hardened prompt
    (all capitalized words + digits stripped) and a fresh composition; the
    retry's result is returned with an honest record of both attempts.
    """
    prep = prepare_render_brief(brief, text_safe)
    out = render_fn(prep["brief"])
    if not text_safe:
        return {"out": out, "text_fidelity": None, "used_brief": prep["brief"]}

    tf = verify_asset_text(out["bytes"], brief=brief, text_safe=True)
    tf.update({k: prep["text_fidelity"][k] for k in
               ("suppressed_count", "kept_count", "expected_terms", "render_prompt")})
    tf["attempts"] = [{"attempt": 1, "contains_text": tf["check"]["contains_text"],
                       "words": tf["check"]["words"][:6]}]
    if (max_attempts > 1 and tf["check"]["status"] == "ok"
            and tf["check"]["contains_text"] is True):
        hard = prepare_render_brief(brief, True, hard=True)
        out2 = render_fn(hard["brief"])
        tf2 = verify_asset_text(out2["bytes"], brief=brief, text_safe=True)
        tf2.update({k: hard["text_fidelity"][k] for k in
                    ("suppressed_count", "kept_count", "expected_terms", "render_prompt")})
        tf2["retried"] = True
        tf2["attempts"] = tf["attempts"] + [{
            "attempt": 2, "contains_text": tf2["check"]["contains_text"],
            "words": tf2["check"]["words"][:6]}]
        out, tf, used = out2, tf2, hard["brief"]
    else:
        tf["retried"] = False

    # FINAL FALLBACK: a 4B model keeps hallucinating decorative glyphs no matter
    # the prompt. Instead of shipping gibberish, clear the DETECTED glyph zones
    # deterministically - a clean plate for the real vector text layer.
    if tf["check"]["status"] == "ok" and tf["check"]["contains_text"] is True:
        cleaned = clean_text_regions(out["bytes"])
        if cleaned["status"] == "ok" and cleaned["cleared"] > 0:
            recheck = verify_asset_text(cleaned["image"], brief=brief, text_safe=True)
            tf["text_cleanup"] = {
                "cleared": cleaned["cleared"],
                "boxes_before": cleaned["boxes_before"],
                "boxes_after": recheck["check"]["boxes"],
                "regions": cleaned["regions"][:20],
                "note": ("Detected glyph zones cleared into a clean plate for the "
                         "vector text layer."),
            }
            out = {**out, "bytes": cleaned["image"]}
            tf["check"] = recheck["check"]
            if recheck["check"]["contains_text"] is False:
                tf["verdict"] = "text_cleared"
            elif (recheck["check"]["boxes"] or 99) < cleaned["boxes_before"]:
                tf["verdict"] = "text_reduced"
    return {"out": out, "text_fidelity": tf, "used_brief": used}


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
