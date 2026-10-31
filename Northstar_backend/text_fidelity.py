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


def _ocr_boxes(image_bytes: bytes, min_score: float = 0.5, min_len: int = 2):
    """(PIL image, [(x0,y0,x1,y1,text)]) or (None, error). Thresholds are
    caller-tunable: the CHECK pass stays strict (0.5/2), the CLEAN pass is more
    aggressive (0.35/1) so tiny residual lettering cannot slip through."""
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
        if score < min_score or len(text.strip()) < min_len:
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


def clean_text_regions(image_bytes: bytes, *, max_coverage: float = 0.6,
                       min_score: float = 0.35, min_len: int = 1) -> Dict[str, Any]:
    """Clear OCR-detected glyph zones by RECONSTRUCTING the panel, not painting it.

    v2 (2026-10-16 evening): the old median-colour fill left visible flat
    rectangles on dieline sheets. Now each detected zone is replaced with a
    heavily downscaled-then-upscaled sample of its own surroundings - a smooth
    continuation of the panel's gradient/flat colour that erases the strokes
    without leaving patch seams. Aggressive thresholds (0.35/1) so tiny
    residual lettering cannot survive; detection filters are recorded for audit.
    """
    parsed, err = _ocr_boxes(image_bytes, min_score=min_score, min_len=min_len)
    if parsed is None:
        return {"status": "unavailable", "error": err, "cleared": 0, "image": None,
                "boxes_before": 0, "regions": []}
    img, boxes = parsed
    if not boxes:
        return {"status": "ok", "cleared": 0, "image": image_bytes,
                "boxes_before": 0, "regions": []}
    from PIL import Image, ImageDraw, ImageFilter  # noqa: PLC0415

    work = img.copy()
    W, H = work.size
    regions: List[List[int]] = []
    cleared = 0
    pad = 10
    for (x0, y0, x1, y1, _t) in boxes:
        bw, bh = (x1 - x0), (y1 - y0)
        if bw <= 1 or bh <= 1 or (bw * bh) > max_coverage * W * H:
            continue
        rx0, ry0 = max(0, int(x0) - pad), max(0, int(y0) - pad)
        rx1, ry1 = min(W, int(x1) + pad), min(H, int(y1) + pad)
        rw, rh = rx1 - rx0, ry1 - ry0
        if rw < 4 or rh < 4:
            continue
        # Reconstruction: keep 30px of real context around the zone, wipe the
        # letterforms with a median pass, then smooth (box-downscaled, ~1/14)
        # so the fill carries the panel's gradient/flat colour with no seams.
        ctx = 30
        cx0, cy0 = max(0, rx0 - ctx), max(0, ry0 - ctx)
        cx1, cy1 = min(W, rx1 + ctx), min(H, ry1 + ctx)
        crop = work.crop((cx0, cy0, cx1, cy1))
        med_size = 31 if min(crop.size) > 35 else 9
        crop = crop.filter(ImageFilter.MedianFilter(size=med_size))
        small = crop.resize((max(2, crop.width // 14), max(2, crop.height // 14)), Image.BOX)
        smooth = small.resize(crop.size, Image.BILINEAR)
        patch = smooth.crop((rx0 - cx0, ry0 - cy0, rx1 - cx0, ry1 - cy0))
        mask = Image.new("L", (rw, rh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, rw - 1, rh - 1], radius=max(4, min(rw, rh) // 3), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(4))
        work.paste(patch, (rx0, ry0), mask)
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


# ── Edit-drift gate: did an edit change the copy it was told not to touch? ──

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'&.\-]*")


def _tokens(words: List[str]) -> List[str]:
    out: List[str] = []
    for w in words:
        for t in _TOKEN.findall(str(w)):
            t = t.strip(".'&-").upper()
            # keep multi-char tokens and ANY token carrying a digit: a net
            # weight of "6 oz" must not lose its "6"
            if len(t) >= 2 or any(ch.isdigit() for ch in t):
                out.append(t)
    return out


def _numerics(tokens: List[str]) -> List[str]:
    return sorted({t for t in tokens if any(ch.isdigit() for ch in t)})


def compare_text_between_images(before_bytes: bytes, after_bytes: bytes,
                                *, min_score: float = 0.5) -> Dict[str, Any]:
    """OCR-diff two images: the packaging-accuracy gate for the edit lane.

    A text-faithful edit (scene / lighting / material only) must return the
    SAME copy. Diffusion editors are known to re-render glyphs, so this gate
    names the drift instead of trusting the prompt. Numeric drift (weights,
    volumes, net contents) is called out separately — it is the failure that
    reaches a customer.

    Never raises; ``status`` is "ok" | "unavailable" | "error", and an
    unavailable engine yields verdict "unverified" (never a fake pass).
    """
    pb, err_b = _ocr_boxes(before_bytes, min_score=min_score, min_len=2)
    pa, err_a = _ocr_boxes(after_bytes, min_score=min_score, min_len=2)
    if pb is None or pa is None:
        status = "unavailable" if (err_b == "unavailable" or err_a == "unavailable") else "error"
        return {"status": status, "verdict": "unverified",
                "error": err_b if pb is None else err_a,
                "before_words": [], "after_words": [], "added": [], "removed": [],
                "numeric_before": [], "numeric_after": [], "numeric_drift": None}
    tb = _tokens([b[4] for b in pb[1]])
    ta = _tokens([b[4] for b in pa[1]])
    sb, sa = set(tb), set(ta)
    added = sorted(sa - sb)
    removed = sorted(sb - sa)
    nb, na = _numerics(tb), _numerics(ta)
    numeric_drift = None if nb == na else {"before": nb, "after": na}
    if not sb and not sa:
        verdict = "no_text"
    elif not added and not removed:
        verdict = "identical"
    elif numeric_drift is not None:
        verdict = "drift_numeric"
    else:
        verdict = "drift"
    return {
        "status": "ok", "verdict": verdict,
        "before_words": [b[4] for b in pb[1]][:20],
        "after_words": [b[4] for b in pa[1]][:20],
        "added": added[:20], "removed": removed[:20],
        "numeric_before": nb, "numeric_after": na, "numeric_drift": numeric_drift,
        "error": None,
    }


def verify_edit_preserves_copy(before_bytes: bytes, after_bytes: bytes) -> Dict[str, Any]:
    """Lane helper: True when the edit left the copy untouched (or unverified)."""
    diff = compare_text_between_images(before_bytes, after_bytes)
    diff["preserves_copy"] = (None if diff["verdict"] == "unverified"
                              else diff["verdict"] in ("identical", "no_text"))
    diff["note"] = (
        "Edit preserved the printed copy." if diff["preserves_copy"] is True else
        "Edit CHANGED the printed copy - re-compose the deterministic text layer "
        "before this render ships." if diff["preserves_copy"] is False else
        "OCR unavailable: copy preservation is UNVERIFIED (never assumed).")
    return diff


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
    used = prep["brief"]  # overwritten by the hardened brief if the retry branch runs
    if not text_safe:
        return {"out": out, "text_fidelity": None, "used_brief": used}

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

    # FINAL FALLBACK: a small model keeps hallucinating decorative glyphs no
    # matter the prompt. Instead of shipping gibberish, RECONSTRUCT the detected
    # glyph zones (gradient-aware inpaint, two bounded passes) - and keep the
    # raw render so the pass is never destructive.
    raw_bytes = None
    if tf["check"]["status"] == "ok" and tf["check"]["contains_text"] is True:
        raw_bytes = out["bytes"]
        passes = []
        cur = out["bytes"]
        for attempt in range(2):
            cleaned = clean_text_regions(cur)
            if cleaned["status"] != "ok" or cleaned["cleared"] == 0:
                break
            recheck = verify_asset_text(cleaned["image"], brief=brief, text_safe=True)
            passes.append({"pass": attempt + 1, "cleared": cleaned["cleared"],
                           "boxes_before": cleaned["boxes_before"],
                           "boxes_after": recheck["check"]["boxes"],
                           "regions": cleaned["regions"][:20]})
            cur = cleaned["image"]
            tf["check"] = recheck["check"]
            if recheck["check"]["contains_text"] is False:
                break
        if passes:
            tf["text_cleanup"] = {
                "cleared": sum(p["cleared"] for p in passes),
                "boxes_before": passes[0]["boxes_before"],
                "boxes_after": tf["check"]["boxes"],
                "passes": passes,
                "note": ("Detected glyph zones reconstructed (gradient-aware inpaint) "
                         "into a clean plate for the vector text layer."),
            }
            out = {**out, "bytes": cur}
            if tf["check"]["contains_text"] is False:
                tf["verdict"] = "text_cleared"
            elif (tf["check"]["boxes"] or 99) < passes[0]["boxes_before"]:
                tf["verdict"] = "text_reduced"
    return {"out": out, "text_fidelity": tf, "used_brief": used, "raw_bytes": raw_bytes}


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

# ── Plate refusal gate (blank-plate architecture) ────────────────────────────
class PlateNotClean(RuntimeError):
    """Raised when a generated base plate still carries OCR-detectable text."""

    def __init__(self, boxes: int, words: List[str], floor: float):
        self.boxes = boxes
        self.words = words
        self.floor = floor
        super().__init__(
            f"plate_not_clean: {boxes} OCR box(es) survived cleaning at min_score {floor} "
            f"({', '.join(words[:5]) or 'no words'}). A blank plate must carry no text "
            "before deterministic composition - compositing onto a dirty plate ghosts "
            "the burned-in lettering through the label."
        )


def assert_plate_clean(image_bytes: bytes, *, min_score: float = 0.5,
                       min_len: int = 2) -> Dict[str, Any]:
    """HALT if any text survives on a base plate. Raises PlateNotClean.

    Deliberately a refusal, not a warning: the 2026-10-30 runs proved that
    scrubbing leaves residue the realism pass can re-introduce, so a plate that
    is not clean must never reach the compositor.
    """
    parsed, err = _ocr_boxes(image_bytes, min_score=min_score, min_len=min_len)
    if parsed is None:
        return {"status": "unavailable", "checked": False, "error": err}
    _img, boxes = parsed
    words = [b[4] for b in boxes][:8]
    if boxes:
        raise PlateNotClean(len(boxes), words, min_score)
    return {"status": "clean", "checked": True, "boxes": 0, "min_score": min_score}
