"""Package readiness — one call that answers "is this package retail-ready?".

It does not add a new measurement; it runs the mechanical checks the pipeline
already owns and returns ONE verdict with grouped blockers and the full evidence:

  * prepress   - ICC gamut shift (CIE76 dE) + total area coverage (ink limit)
  * copy       - is the printed copy present and does it match the expected terms
  * main image - Amazon MAIN: pure white background, >=85 % fill, >=2000 px
  * dieline    - bleed / trim / fold / safe layers present, sane bleed, and the
                 published-ladder proportion check for a doypack

"retail_ready" means every supplied check passed. Missing inputs are reported as
not-assessed, never as a pass - an assessment with no artwork is not a green
light.

Pure local: littleCMS + PIL + the repo's own OCR. No network, no provider.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import image_prep
import prepress
import text_fidelity

REQUIRED_LAYERS = ("trim", "fold", "safe")
MIN_BLEED_MM = 2.0          # 3 mm is the common commercial default
RECOMMENDED_BLEED_MM = 3.0


# ── individual checks ───────────────────────────────────────────────────────

def assess_dieline(build: Optional[dict]) -> Dict[str, Any]:
    """Structural sanity of a built dieline (never a substitute for a die)."""
    if not build:
        return {"assessed": False, "reason": "no dieline supplied"}
    meta = build.get("meta") or {}
    layers = build.get("layers") or []
    kinds = {str(item.get("layer")) for item in layers}
    blockers: List[str] = []
    warnings: List[str] = []

    for needed in REQUIRED_LAYERS:
        if needed not in kinds:
            blockers.append(f"dieline is missing its '{needed}' layer")
    bleed = float(meta.get("bleed_mm") or 0.0)
    if bleed < MIN_BLEED_MM:
        blockers.append(f"bleed is {bleed:g}mm (needs >= {MIN_BLEED_MM:g}mm)")
    elif bleed < RECOMMENDED_BLEED_MM:
        warnings.append(f"bleed is {bleed:g}mm; {RECOMMENDED_BLEED_MM:g}mm is the "
                        "common commercial default")
    if not meta.get("template"):
        warnings.append("dieline does not name its template")
    if float(build.get("width_mm") or 0) <= 0 or float(build.get("height_mm") or 0) <= 0:
        blockers.append("dieline has no usable sheet dimensions")

    proportion = meta.get("proportion_check")
    if proportion and proportion.get("status") == "warnings":
        for w in (proportion.get("warnings") or []):
            warnings.append(f"proportion: {w}")
    confidence = meta.get("confidence")
    if confidence:
        warnings.append(f"dieline confidence: {confidence}")

    return {
        "assessed": True, "template": meta.get("template"),
        "size_mm": [build.get("width_mm"), build.get("height_mm")],
        "bleed_mm": bleed, "layers_present": sorted(k for k in kinds if k),
        "proportion_status": (proportion or {}).get("status"),
        "blockers": blockers, "warnings": warnings,
    }


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s).upper() if ch.isalnum())


def _best_similarity(term: str, haystack_lines: Sequence[str]) -> float:
    """Best similarity between a term and any OCR line (difflib ratio)."""
    import difflib
    t = _norm(term)
    if not t:
        return 0.0
    best = 0.0
    for line in haystack_lines:
        h = _norm(line)
        if not h:
            continue
        if t in h:
            return 1.0
        best = max(best, difflib.SequenceMatcher(None, t, h).ratio())
    return best


#: A stylised serif wordmark is routinely OCR'd one or two characters off
#: ("MOGRA ORGANCS", "ORGANISLION'SMANE"). Below this ratio we call it missing.
FUZZY_MATCH_RATIO = 0.80


def assess_copy(image: Optional[bytes], expected_terms: Optional[Sequence[str]] = None
                ) -> Dict[str, Any]:
    """OCR the artwork and compare against the terms that must appear.

    Exact hits are 'matched'. Near hits (see FUZZY_MATCH_RATIO) are reported as
    'matched_fuzzy' WITH the ratio - a stylised wordmark read one character off
    is a warning to eyeball, not a silent pass, and not a false blocker.
    """
    if not image:
        return {"assessed": False, "reason": "no artwork supplied"}
    check = text_fidelity.check_text_in_image(image)
    if check.get("status") != "ok":
        return {"assessed": False, "status": check.get("status"),
                "reason": "OCR unavailable - copy is UNVERIFIED, not passed",
                "error": check.get("error")}
    words = list(check.get("words") or [])
    lines = words + [" ".join(words)]
    expected = [t for t in (expected_terms or []) if t]

    matched: List[str] = []
    fuzzy: List[Dict[str, Any]] = []
    missing: List[str] = []
    for term in expected:
        ratio = _best_similarity(term, lines)
        if ratio >= 1.0:
            matched.append(term)
        elif ratio >= FUZZY_MATCH_RATIO:
            fuzzy.append({"term": term, "ratio": round(ratio, 3)})
        else:
            missing.append(term)

    blockers = [f"expected copy not found in the artwork: {t!r}" for t in missing]
    warnings = [f"copy '{f['term']}' matched only fuzzily (OCR ratio {f['ratio']}) - "
                "eyeball the render before shipping" for f in fuzzy]
    return {
        "assessed": True, "contains_text": check.get("contains_text"),
        "boxes": check.get("boxes"), "words": words[:12],
        "expected_terms": expected, "matched": matched,
        "matched_fuzzy": fuzzy, "missing": missing,
        "blockers": blockers, "warnings": warnings,
        "note": ("Fuzzy matching exists because a stylised serif wordmark is often "
                 "OCR'd one character off; fuzzy hits are reported, never silently "
                 "accepted."),
    }


def assess_main(image: Optional[bytes], *, min_fill: float = 0.85,
                min_side: int = 2000) -> Dict[str, Any]:
    if not image:
        return {"assessed": False, "reason": "no MAIN image supplied"}
    rep = image_prep.check_main_compliance(image, min_fill=min_fill, min_side=min_side)
    return {"assessed": True, **rep}


def assess_prepress(image: Optional[bytes], *, profile: Optional[str] = None,
                    tac_limit: float = 300.0) -> Dict[str, Any]:
    if not image:
        return {"assessed": False, "reason": "no artwork supplied"}
    try:
        rep = prepress.prepress_report(image, profile=profile, limit_pct=tac_limit)
    except RuntimeError as exc:
        return {"assessed": False, "reason": str(exc)}
    # Turn the blocker into an instruction: for the worst offenders, give the
    # colour that DOES print faithfully through the same profile.
    worst = [c.get("srgb") for c in (rep.get("gamut", {}).get("worst_colors") or [])
             if c.get("srgb")]
    if worst:
        try:
            mapped = prepress.map_colors(worst, profile=rep.get("profile"),
                                         de_tolerance=rep.get("gamut", {}).get(
                                             "tolerance_dE76", 8.0))
            out_of_gamut = [c for c in mapped.get("colors", []) if not c["in_gamut"]]
            if out_of_gamut:
                rep["suggested_colors"] = out_of_gamut[:6]
        except Exception:  # noqa: BLE001 - a suggestion is a bonus, never a failure
            pass
    return {"assessed": True, **rep}


# ── the one call ────────────────────────────────────────────────────────────

def assess_package(*, artwork: Optional[bytes] = None,
                   main_image: Optional[bytes] = None,
                   dieline: Optional[dict] = None,
                   expected_terms: Optional[Sequence[str]] = None,
                   profile: Optional[str] = None,
                   tac_limit: float = 300.0,
                   min_fill: float = 0.85,
                   min_side: int = 2000) -> Dict[str, Any]:
    """Run every supplied check and return ONE retail-readiness verdict."""
    prepress_r = assess_prepress(artwork, profile=profile, tac_limit=tac_limit)
    copy_r = assess_copy(artwork, expected_terms)
    main_r = assess_main(main_image, min_fill=min_fill, min_side=min_side)
    dieline_r = assess_dieline(dieline)

    blockers: List[str] = []
    warnings: List[str] = []
    assessed_any = False

    for name, result in (("prepress", prepress_r), ("copy", copy_r),
                         ("main", main_r), ("dieline", dieline_r)):
        if not result.get("assessed"):
            continue
        assessed_any = True
        for b in result.get("blockers") or []:
            blockers.append(f"{name}: {b}")
        for w in result.get("warnings") or []:
            warnings.append(f"{name}: {w}")

    not_assessed = [name for name, r in (("prepress", prepress_r), ("copy", copy_r),
                                         ("main", main_r), ("dieline", dieline_r))
                    if not r.get("assessed")]

    if not assessed_any:
        verdict = "not_assessed"
    elif blockers:
        verdict = "needs_work"
    else:
        verdict = "retail_ready"

    return {
        "verdict": verdict,
        "blockers": blockers,
        "warnings": warnings,
        "not_assessed": not_assessed,
        "evidence": {
            "prepress": prepress_r, "copy": copy_r,
            "main": main_r, "dieline": dieline_r,
        },
        "note": ("Mechanical checks only: ICC conversion, OCR copy match, MAIN "
                 "framing, dieline structure. A 'retail_ready' here still needs "
                 "the co-packer's die drawing and their own preflight - this "
                 "report narrows what to ask them about, it does not replace them."),
    }
