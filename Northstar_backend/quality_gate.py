"""Quality gate: form, brief alignment, layout and typography before delivery.

Simple mode used to accept a deliverable on one axis - does the container form
match? - which let two defects ship: a brief that asked for label text delivered
a blank pouch, and a render that drifted off the brief delivered because the
packaging shape was right.

This gate scores five axes and blocks on four of them:

    form               observed container == requested (blocking)
    design_alignment   the render is the product the brief described (blocking)
    layout             balanced composition, not a cut-off or crowded frame (blocking)
    typography         text present when asked, absent when not, legible (blocking)
    material           finish as observed - recorded, never blocking

Typography is decided by OCR first (`text_fidelity.check_text_in_image`), because
"is there text" is answerable deterministically; the vision model only opines on
legibility once text is actually there. A lane that cannot verify is not a pass:
an unavailable vision model fails the gate, and an unavailable OCR engine fails it
only when the brief asked for text.

Material is recorded rather than scored: a matte-vs-gloss finish cannot be proven
from a PNG, so claiming to verify it would be the fabrication this gate exists to
prevent.
"""
from __future__ import annotations

import base64
import json
import re
import time
from typing import Any, Dict, Optional

import local_vision as lv
import text_fidelity as tf
from typing import Sequence

VISION_MODEL = "qwen3.5:4b"
AXES = ("form", "design_alignment", "layout", "typography", "material")
BLOCKING = ("form", "design_alignment", "layout", "typography")
FORM_WORDS = {
    "pouch": ("pouch", "sachet", "stand-up", "standup"),
    "box": ("box", "carton", "folding"),
    "bottle": ("bottle", "flask"),
    "tube": ("tube",),
    "jar": ("jar", "pot"),
}

_PROMPT = """You are a packaging art director reviewing one render.

Return ONLY this JSON object, no prose:
{
  "subject_matches": true or false,
  "form": "pouch" | "box" | "bottle" | "tube" | "jar" | "other",
  "layout": {"balanced": true or false, "note": "max 120 characters"},
  "typography": {"text_visible": true or false, "legible": true or false or null, "note": "max 120 characters"},
  "garbled_text": true or false,
  "material": {"finish": "matte" | "gloss" | "kraft" | "metallic" | "soft_touch" | "unknown", "note": "max 120 characters"},
  "design_note": "max 160 characters"
}

subject_matches is false when the image is not the product the brief describes.
layout.balanced is false when the composition is cut off, crowded, or off-centre.
typography.legible is false when letters are garbled, warped or unreadable, and
null when no text is visible at all.
garbled_text is true when ANY lettering anywhere in the image is unreadable
gibberish - background text, side panels, fine print - not only the main label."""


def _post(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    return lv._http_post(url, payload, timeout)


def _parse(raw: str) -> Dict[str, Any]:
    """Pull the JSON object out of the reply; unparsed is reported, not guessed."""
    text = (raw or "").strip()
    if not text:
        return {"parsed": False, "reason": "empty reply", "raw": ""}
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = None
    if not isinstance(data, dict):
        return {"parsed": False, "reason": "reply is not a JSON object", "raw": text[:300]}

    layout = data.get("layout") if isinstance(data.get("layout"), dict) else {}
    typo = data.get("typography") if isinstance(data.get("typography"), dict) else {}
    material = data.get("material") if isinstance(data.get("material"), dict) else {}
    form_raw = str(data.get("form") or "").strip().lower()
    form = next((name for name, words in FORM_WORDS.items()
                 if any(w in form_raw for w in words)), "other" if form_raw else "unknown")
    return {
        "parsed": True,
        "subject_matches": data.get("subject_matches"),
        "form": form,
        "form_raw": form_raw[:40],
        "layout_balanced": layout.get("balanced"),
        "layout_note": str(layout.get("note") or "")[:120],
        "text_visible": typo.get("text_visible"),
        "legible": typo.get("legible"),
        "garbled_text": data.get("garbled_text"),
        "typography_note": str(typo.get("note") or "")[:120],
        "material_finish": str(material.get("finish") or "unknown")[:24],
        "material_note": str(material.get("note") or "")[:120],
        "design_note": str(data.get("design_note") or "")[:160],
    }


def _observe(png: bytes, brief: str, *, model: str = VISION_MODEL,
             timeout: float = 180.0) -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": f"{_PROMPT}\n\nBrief: {brief.strip()[:600] or '(no brief given)'}",
        "images": [base64.b64encode(lv._downscale(png, lv.DEFAULT_MAX_SIDE)).decode("ascii")],
        "stream": False,
        "keep_alive": 0,
        # Without think=False the model spends the whole budget reasoning and the
        # reply comes back empty (measured: 34.6s, 0 chars, with format=json).
        "think": False,
        "format": "json",
        "options": {"temperature": 0.0, "num_predict": 600},
    }
    started = time.time()
    try:
        resp = _post(f"{lv.OLLAMA_HOST}/api/generate", payload, timeout)
    except Exception as exc:  # noqa: BLE001 - unreachable is not a verdict
        return {"available": False,
                "error": f"{type(exc).__name__}: {exc}"[:300],
                "model": model, "seconds": round(time.time() - started, 1)}
    parsed = _parse(str(resp.get("response") or ""))
    parsed.update({"available": parsed["parsed"], "model": model,
                   "seconds": round(time.time() - started, 1)})
    return parsed


def _axis(status: str, **fields: Any) -> Dict[str, Any]:
    return {"status": status, **fields}


def _normalise(s: str) -> str:
    # A single-letter token is almost always an apostrophe remnant ("lion's" ->
    # "lion s"), not a word worth matching on.
    tokens = [t for t in re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split()
              if len(t) > 1]
    return " ".join(tokens)


def term_coverage(expected: Optional[Sequence[str]], ocr_words: Sequence[str]) -> Dict[str, Any]:
    """How much of the requested copy the OCR actually read.

    Case and punctuation are ignored; a term counts as present when all of its
    tokens appear in the OCR text. Coverage is evidence, not proof: a stylised
    face can defeat OCR while the render is fine, which is why the gate blocks
    only below half the requested terms rather than on any miss.
    """
    terms = [t for t in (expected or []) if _normalise(t)]
    if not terms:
        return {"applicable": False}
    seen = f" {_normalise(' '.join(ocr_words))} "
    matched, missing = [], []
    for term in terms:
        tokens = [tok for tok in _normalise(term).split(" ") if tok]
        (matched if tokens and all(f" {tok} " in seen for tok in tokens) else missing).append(term)
    return {"applicable": True, "expected": len(terms), "matched": matched,
            "missing": missing, "coverage": round(len(matched) / len(terms), 2)}


def _typography_axis(ocr: Dict[str, Any], *, text_requested: bool,
                     legible: Optional[bool], note: str,
                     expected_terms: Optional[Sequence[str]] = None,
                     garbled_text: Optional[bool] = None) -> Dict[str, Any]:
    present = ocr.get("contains_text")
    if not text_requested:
        if present is True:
            return _axis("fail", reason="typography_unwanted_text",
                         detail="the brief asked for no lettering; OCR found text",
                         boxes=ocr.get("boxes"), words=ocr.get("words"),
                         engine=ocr.get("engine"))
        return _axis("not_applicable", reason="no_text_requested",
                     verified=present is False, engine=ocr.get("engine"),
                     detail=("OCR confirms no lettering" if present is False
                             else "OCR unavailable; absence not independently verified"))
    if present is None:
        return _axis("fail", reason="typography_unverified",
                     detail=f"text was requested and OCR could not run ({ocr.get('error')})",
                     engine=ocr.get("engine"))
    if present is False:
        return _axis("fail", reason="typography_missing",
                     detail="text was requested; OCR found no lettering in the render",
                     engine=ocr.get("engine"))
    if legible is False:
        return _axis("fail", reason="typography_illegible", detail=note or "letters unreadable",
                     boxes=ocr.get("boxes"), words=ocr.get("words"), engine=ocr.get("engine"))
    if garbled_text is True:
        return _axis("fail", reason="typography_garbled",
                     detail=note or "unreadable gibberish lettering elsewhere in the frame",
                     boxes=ocr.get("boxes"), words=ocr.get("words"), engine=ocr.get("engine"))
    coverage = term_coverage(expected_terms, ocr.get("words") or [])
    if coverage.get("applicable") and coverage["coverage"] < 0.5:
        return _axis("fail", reason="typography_text_mismatch",
                     detail=(f"OCR read {coverage['coverage']:.0%} of the requested copy; "
                             f"missing {coverage['missing'][:3]}"),
                     boxes=ocr.get("boxes"), words=ocr.get("words"),
                     engine=ocr.get("engine"), coverage=coverage)
    return _axis("pass", boxes=ocr.get("boxes"), words=ocr.get("words"),
                 engine=ocr.get("engine"),
                 legibility_source="vision" if legible is True else "presence_only",
                 detail=note,
                 **({"coverage": coverage} if coverage.get("applicable") else {}))


def score(png: bytes, *, brief: str, requested_form: str, text_requested: bool,
          expected_terms: Optional[Sequence[str]] = None,
          model: str = VISION_MODEL) -> Dict[str, Any]:
    """Score every axis. Returns evidence, never a bare boolean."""
    observed = _observe(png, brief, model=model)
    if not observed.get("available"):
        return {
            "available": False,
            "model": model,
            "error": observed.get("error") or observed.get("reason"),
            "seconds": observed.get("seconds"),
            "axes": {name: _axis("fail", reason="vision_unavailable",
                                detail="the vision lane did not answer") for name in BLOCKING},
            "raw": observed.get("raw"),
        }

    ocr = tf.check_text_in_image(png)
    axes: Dict[str, Any] = {}
    form_observed = observed.get("form")
    axes["form"] = (_axis("pass", observed=form_observed)
                    if requested_form and form_observed == requested_form else
                    _axis("fail", reason="form_mismatch",
                          requested=requested_form, observed=form_observed,
                          detail=observed.get("form_raw")))
    axes["design_alignment"] = (
        _axis("pass", detail=observed.get("design_note"))
        if observed.get("subject_matches") is True else
        _axis("fail", reason="brief_mismatch",
              detail=observed.get("design_note") or "the render does not match the brief")
        if observed.get("subject_matches") is False else
        _axis("fail", reason="alignment_unverified",
              detail="the vision lane did not answer subject_matches"))
    axes["layout"] = (
        _axis("pass", detail=observed.get("layout_note"))
        if observed.get("layout_balanced") is True else
        _axis("fail", reason="layout_unbalanced",
              detail=observed.get("layout_note") or "composition reported unbalanced")
        if observed.get("layout_balanced") is False else
        _axis("fail", reason="layout_unverified",
              detail="the vision lane did not answer layout.balanced"))
    axes["typography"] = _typography_axis(
        ocr, text_requested=text_requested, legible=observed.get("legible"),
        note=observed.get("typography_note") or "", expected_terms=expected_terms,
        garbled_text=observed.get("garbled_text"))
    axes["material"] = _axis("recorded", finish=observed.get("material_finish"),
                             detail=observed.get("material_note"),
                             detail_note="descriptive only; finish is not verifiable from a PNG")
    text_visible = observed.get("text_visible")
    if text_visible is not None:
        axes["typography"]["vision_text_visible"] = text_visible
    if observed.get("garbled_text") is not None:
        axes["typography"]["vision_garbled"] = observed["garbled_text"]
    return {"available": True, "model": model, "seconds": observed.get("seconds"),
            "axes": axes, "ocr": ocr}


def verdict(scored: Dict[str, Any]) -> Dict[str, Any]:
    """Block on every blocking axis that is not a pass or an explicit n/a."""
    axes = scored.get("axes") or {}
    passed, failed, not_applicable, reasons = [], [], [], []
    for name in BLOCKING:
        axis = axes.get(name) or _axis("fail", reason="axis_missing")
        status = axis.get("status")
        if status == "pass":
            passed.append(name)
        elif status == "not_applicable":
            not_applicable.append(name)
        else:
            failed.append(name)
            reasons.append({"axis": name, "reason": axis.get("reason"),
                            "detail": axis.get("detail")})
    blocking_total = len(BLOCKING) - len(not_applicable)
    return {
        "ok": not failed,
        "passed": passed,
        "failed": failed,
        "not_applicable": not_applicable,
        "reasons": reasons,
        "score": f"{len(passed)}/{blocking_total}" if blocking_total else "0/0",
        "model": scored.get("model"),
        "available": bool(scored.get("available")),
    }


def manifest_block(scored: Dict[str, Any], verdict: Dict[str, Any]) -> Dict[str, Any]:
    """The quality block for a deliverable manifest: no nulls, no placeholders.

    A field that was not measured is absent, so a reader can tell "we did not
    check" from "we checked and it failed" without reading prose.
    """
    axes: Dict[str, Dict[str, Any]] = {}
    for name, axis in (scored.get("axes") or {}).items():
        axes[name] = {k: v for k, v in axis.items() if v is not None and v != ""}
    ocr = {k: v for k, v in (scored.get("ocr") or {}).items()
           if v is not None and v != "" and k != "words"}
    if (scored.get("ocr") or {}).get("words"):
        words = [w for w in scored["ocr"]["words"] if w][:12]
        if words:
            ocr["words"] = words
    block: Dict[str, Any] = {
        "axes": axes,
        "verdict": {k: verdict[k] for k in
                    ("ok", "passed", "failed", "not_applicable", "score", "reasons")},
        "model": verdict.get("model") or scored.get("model"),
        "available": bool(scored.get("available")),
    }
    if scored.get("seconds") is not None:
        block["seconds"] = scored["seconds"]
    if scored.get("error"):
        block["error"] = scored["error"]
    if ocr:
        block["ocr"] = ocr
    return block


__all__ = ["AXES", "BLOCKING", "VISION_MODEL", "score", "verdict", "manifest_block", "_parse"]
