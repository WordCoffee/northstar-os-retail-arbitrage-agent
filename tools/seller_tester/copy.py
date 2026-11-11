"""Seller-Tester for the three copy rooms: OfferChisel, The Town Crier, SocialPulse.

Why this module exists: those three services were scored 0.0 on the `seller`
dimension for one reason only — nothing measured their copy. A picture has a
scorer; a listing has a composer and a rubric; a caption had nothing. This is the
instrument, in the same shape as the other service paths
(`tools/seller_tester/services.py`): named checks, the share of graded checks
that passed, a skip is never a pass, and a refusal is recorded with its reason.

What is measured, and where the copy comes from
-----------------------------------------------
The score is **not** a model verdict. Every check is one of the app's own
deterministic rules applied to the copy the room would show:

* **offerchisel** (`offer_copy`) — the room asks the local engine for
  ``TITLE:/BULLETS:/KEYWORDS:`` sections. The answer is a recorded fixture (a
  live generation is a gated model call). The copy is judged by
  ``specialists.listing_optimizer`` — the app's own listing rubric:
  `audit_title`, `audit_bullet`, `keyword_coverage`, `backend_bytes` — plus the
  claims lint (`tools/seller_tester/claims_lint.py`) and a byte cap.
* **towncrier** (`caption`) — one caption plus 3-4 hashtags, as the room's own
  prompt asks. The answer is a recorded fixture. The checks are the room's own
  limits (220 chars, brand voice rule "Word Coffee is NOT a beverage"), the
  claims lint, and the hashtag shape.
* **socialpulse** (`social_caption`) — this one is **real code, not a fixture**:
  ``social_pulse.generate_caption`` is called with the local model refused, so the
  documented template fallback runs. The caption, its hashtags, its CTA and its
  platform spec are the app's own output, and the app's own
  ``_score_caption`` is reported alongside.

Honesty rules that are enforced here, not promised:

* a check the brief cannot answer (no facts to trace a number to) is **skipped**
  and is not counted as a pass;
* a recorded answer that the room could not even parse is a **refusal**, recorded
  with the reason, not a zero that looks like a score;
* the published number is the share of graded checks that passed, exactly like
  every other service path.

Two real defects this instrument found on the day it was built (2026-11-11),
kept in the sample rather than papered over:

1. ``social_pulse._generate_hashtags`` honours the voice's ``hashtags_per_post``
   (default 10) but never the platform's ``max_hashtags`` (twitter: 3), so the
   template path returns 10 hashtags for a platform that caps at 3;
2. the recorded OfferChisel drafts carry a promotional claim ("BEST SELLER")
   and a disease claim ("immune support") that the room itself does not screen.
   The checks fail on them; that is the instrument working.

    python -m tools.seller_tester services --only offer_copy,caption,social_caption
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]

#: Path name -> the service whose declared product it is. Kept here as the single
#: statement of ownership; `service_briefs.json`'s `service_attribution` repeats it
#: for the scorer, and the two are asserted equal by the tests.
OWNERS = {
    "offer_copy": "offerchisel",
    "caption": "towncrier",
    "social_caption": "socialpulse",
}

PATHS = tuple(OWNERS)


class CopyRefused(RuntimeError):
    """The recorded answer could not be parsed into the product's shape."""


def _backend() -> Path:
    backend = ROOT / "Northstar_backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    if str(ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools"))
    return backend


def _ok(check: str, **kw: Any) -> Dict[str, Any]:
    return {"ok": True, "check": check, **kw}


def _bad(check: str, detail: str, **kw: Any) -> Dict[str, Any]:
    return {"ok": False, "check": check, "detail": detail, **kw}


def _skip(check: str, detail: str, **kw: Any) -> Dict[str, Any]:
    return {"ok": False, "check": check, "skipped": True, "detail": detail, **kw}


def _score(checks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Share of graded checks that passed. A skip is not a pass and not a failure."""
    graded = [name for name, check in checks.items() if not check.get("skipped")]
    failed = [name for name in graded if not checks[name].get("ok")]
    skipped = [name for name, check in checks.items() if check.get("skipped")]
    score = round(100.0 * (len(graded) - len(failed)) / len(graded), 1) if graded else 0.0
    return {"score": score, "passed": not failed and bool(graded),
            "graded": len(graded), "failed_checks": failed, "skipped_checks": skipped}


#: A number with a unit is a factual claim about the product (claims_lint.NUMBER).
_UNIT_NUMBER = re.compile(
    r"\b\d+(?:\.\d+)?\s*(mg|g|oz|ml|l|servings?|capsules?|count|pack|%|x)\b", re.IGNORECASE)


def _numbers(text: str) -> List[str]:
    return sorted({match.group(0).strip().lower() for match in _UNIT_NUMBER.finditer(str(text))})


def _unsourced_numbers(text: str, facts: Sequence[str]) -> List[str]:
    lowered = [str(fact).lower() for fact in facts]
    return [token for token in _numbers(text)
            if not any(token in fact or fact in token for fact in lowered)]


def _claim_hits(text: str) -> List[str]:
    from .claims_lint import DISEASE_TERMS  # noqa: PLC0415

    low = str(text or "").lower()
    return [term for term in DISEASE_TERMS if term in low]


def _cross_brand_hits(text: str, brand: str) -> List[str]:
    from .claims_lint import BRANDS  # noqa: PLC0415

    own = _brand_key(brand)
    low = str(text or "").lower()
    hits: List[str] = []
    for other, names in BRANDS.items():
        if other == own:
            continue
        for name in names:
            if name.lower() in low:
                hits.append(name)
    return hits


def _brand_key(brand: str) -> str:
    low = str(brand or "").lower()
    if "coffee" in low:
        return "word-coffee"
    if "mogra" in low or "lion" in low:
        return "mogra"
    return low


# ── OfferChisel: the listing copy ────────────────────────────────────────────

#: The room's own prompt asks for exactly these three sections (OfferChisel.jsx:21-30),
#: and parses them with these three expressions (:28-30). Both are copied, not invented.
_TITLE = re.compile(r"TITLE:\s*([^\n]+)", re.IGNORECASE)
_BULLETS = re.compile(r"BULLETS:([\s\S]*?)(?=KEYWORDS:)", re.IGNORECASE)
_KEYWORDS = re.compile(r"KEYWORDS:\s*([^\n]+)", re.IGNORECASE)


def _parse_listing(answer: str) -> Dict[str, Any]:
    title = _TITLE.search(answer or "")
    bullets = _BULLETS.search(answer or "")
    keywords = _KEYWORDS.search(answer or "")
    if not title or not bullets or not keywords:
        raise CopyRefused("the answer has no TITLE:/BULLETS:/KEYWORDS: sections")
    lines = [line.strip() for line in bullets.group(1).splitlines()]
    points = [line.lstrip("-").strip() for line in lines if line.startswith("-")]
    terms = [term.strip() for term in keywords.group(1).split(",") if term.strip()]
    return {"title": title.group(1).strip(), "bullets": points,
            "keywords_line": keywords.group(1).strip(), "keywords": terms}


def run_offer_copy(brief: Dict[str, Any], *, work_dir: Path) -> Dict[str, Any]:
    """Judge one recorded OfferChisel answer with the app's own listing rubric."""
    _backend()
    from specialists import listing_optimizer as lo  # noqa: PLC0415

    answer = str(brief.get("recorded_answer") or "")
    if not answer.strip():
        raise CopyRefused(f"{brief.get('id')}: the fixture records no engine answer")
    parsed = _parse_listing(answer)
    title = parsed["title"]
    bullets = parsed["bullets"]
    keywords = [str(k) for k in (brief.get("keywords") or [])]
    everything = " ".join([title, *bullets, parsed["keywords_line"]])
    facts = [str(f) for f in (brief.get("facts") or [])]
    checks: Dict[str, Dict[str, Any]] = {}

    checks["sections_parsed"] = _ok("sections_parsed", bullets=len(bullets),
                                    keywords=len(parsed["keywords"]))
    checks["title_within_200"] = (
        _ok("title_within_200", chars=len(title)) if len(title) <= lo.TITLE_SOFT_MAX else
        _bad("title_within_200", f"title is {len(title)} chars, limit {lo.TITLE_SOFT_MAX}"))
    title_issues = lo.audit_title(title)
    checks["title_audit_clean"] = (
        _ok("title_audit_clean") if not title_issues else
        _bad("title_audit_clean", "; ".join(title_issues)))
    checks["exactly_four_bullets"] = (
        _ok("exactly_four_bullets", bullets=len(bullets)) if len(bullets) == 4 else
        _bad("exactly_four_bullets", f"{len(bullets)} bullet(s), the room asks for 4"))
    bullet_issues = [issue for index, bullet in enumerate(bullets, 1)
                     for issue in lo.audit_bullet(bullet, index)]
    checks["bullets_audit_clean"] = (
        _ok("bullets_audit_clean") if not bullet_issues else
        _bad("bullets_audit_clean", "; ".join(bullet_issues)[:300]))
    checks["keywords_8_to_12"] = (
        _ok("keywords_8_to_12", count=len(parsed["keywords"]))
        if 8 <= len(parsed["keywords"]) <= 12 else
        _bad("keywords_8_to_12", f"{len(parsed['keywords'])} term(s), the room asks for 8-12"))
    coverage = lo.keyword_coverage(title, bullets, parsed["keywords_line"], keywords)
    checks["keyword_coverage_complete"] = (
        _ok("keyword_coverage_complete", covered=coverage["covered"], total=coverage["total"])
        if coverage["total"] and coverage["covered"] == coverage["total"] else
        _bad("keyword_coverage_complete",
             f"{coverage['covered']}/{coverage['total']} target keywords appear: "
             f"{[row['keyword'] for row in coverage['keywords'] if not row['covered']]}"))
    written = lo.backend_bytes(parsed["keywords_line"])
    checks["backend_within_250_bytes"] = (
        _ok("backend_within_250_bytes", bytes=written) if written <= lo.BACKEND_BYTE_LIMIT else
        _bad("backend_within_250_bytes",
             f"back-end terms are {written} bytes, limit {lo.BACKEND_BYTE_LIMIT}"))
    claims = _claim_hits(everything)
    checks["no_disease_or_treatment_claim"] = (
        _ok("no_disease_or_treatment_claim") if not claims else
        _bad("no_disease_or_treatment_claim", f"claims the app screens for: {claims}"))
    if not facts:
        checks["no_unsourced_number"] = _skip(
            "no_unsourced_number", "this brief declares no facts, so a number cannot be traced")
    else:
        invented = _unsourced_numbers(everything, facts)
        checks["no_unsourced_number"] = (
            _ok("no_unsourced_number", numbers=_numbers(everything)) if not invented else
            _bad("no_unsourced_number", f"numbers with no source in the brief: {invented}"))
    cross = _cross_brand_hits(everything, str(brief.get("brand") or ""))
    checks["no_cross_brand_copy"] = (
        _ok("no_cross_brand_copy") if not cross else
        _bad("no_cross_brand_copy", f"another brand's line appears: {cross}"))

    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / f"{brief.get('id')}.json"
    target.write_text(json.dumps({"brief": brief.get("id"), "parsed": parsed,
                                  "checks": checks}, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    scored = _score(checks)
    return {"path": "offer_copy", "brief_id": brief.get("id"), "artefact": str(target),
            "title": title, "bullets": len(bullets), "checks": checks, **scored}


# ── The Town Crier: one caption plus hashtags ───────────────────────────────


def _parse_caption(answer: str) -> Dict[str, Any]:
    lines = [line.strip() for line in (answer or "").splitlines() if line.strip()]
    tag_index = next((i for i, line in enumerate(lines) if line.startswith("#")), -1)
    if tag_index < 0:
        return {"caption": " ".join(lines), "hashtags": [], "hashtag_line": False}
    caption = " ".join(lines[:tag_index]).strip()
    tags = [token for line in lines[tag_index:] for token in line.split()
            if token.startswith("#")]
    if not caption:
        raise CopyRefused("the answer carries hashtags but no caption")
    return {"caption": caption, "hashtags": tags, "hashtag_line": True}


def run_caption(brief: Dict[str, Any], *, work_dir: Path) -> Dict[str, Any]:
    """Judge one recorded Town Crier caption against the room's own rules."""
    answer = str(brief.get("recorded_answer") or "")
    if not answer.strip():
        raise CopyRefused(f"{brief.get('id')}: the fixture records no engine answer")
    parsed = _parse_caption(answer)
    caption = parsed["caption"]
    tags = parsed["hashtags"]
    facts = [str(f) for f in (brief.get("facts") or [])]
    forbidden = [str(term) for term in (brief.get("forbidden_terms") or [])]
    checks: Dict[str, Dict[str, Any]] = {}

    limit = int(brief.get("platform_limit") or 220)
    checks["caption_parsed"] = _ok("caption_parsed", chars=len(caption))
    checks["caption_within_platform_limit"] = (
        _ok("caption_within_platform_limit", chars=len(caption), limit=limit)
        if 0 < len(caption) <= limit else
        _bad("caption_within_platform_limit",
             f"caption is {len(caption)} chars, limit {limit}"))
    checks["one_caption_not_a_dump"] = (
        _ok("one_caption_not_a_dump", chars=len(caption)) if caption.count(". ") <= 4 else
        _bad("one_caption_not_a_dump", "the answer is several paragraphs, not one caption"))
    checks["hashtags_3_to_4"] = (
        _ok("hashtags_3_to_4", hashtags=len(tags)) if 3 <= len(tags) <= 4 else
        _bad("hashtags_3_to_4", f"{len(tags)} hashtag(s), the room asks for 3-4",
             hashtags=len(tags)))
    malformed = [tag for tag in tags if len(tag) < 2 or " " in tag]
    checks["hashtags_well_formed"] = (
        _ok("hashtags_well_formed") if tags and not malformed and
        len(set(tags)) == len(tags) else
        _bad("hashtags_well_formed", f"malformed or repeated: {malformed or tags}"))
    used = [term for term in forbidden if term.lower() in caption.lower()]
    checks["brand_rule_respected"] = (
        _ok("brand_rule_respected", forbidden=forbidden) if not used else
        _bad("brand_rule_respected",
             f"the brand voice forbids {forbidden}; the caption says {used}"))
    claims = _claim_hits(caption)
    checks["no_disease_or_treatment_claim"] = (
        _ok("no_disease_or_treatment_claim") if not claims else
        _bad("no_disease_or_treatment_claim", f"claims the app screens for: {claims}"))
    if not facts:
        checks["no_unsourced_number"] = _skip(
            "no_unsourced_number", "this brief declares no facts, so a number cannot be traced")
    else:
        invented = _unsourced_numbers(caption, facts)
        checks["no_unsourced_number"] = (
            _ok("no_unsourced_number", numbers=_numbers(caption)) if not invented else
            _bad("no_unsourced_number", f"numbers with no source in the brief: {invented}"))

    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / f"{brief.get('id')}.json"
    target.write_text(json.dumps({"brief": brief.get("id"), "parsed": parsed,
                                  "checks": checks}, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    scored = _score(checks)
    return {"path": "caption", "brief_id": brief.get("id"), "artefact": str(target),
            "caption_chars": len(caption), "checks": checks, **scored}


# ── SocialPulse: the app's own caption pipeline ─────────────────────────────


def _refuse_model(prompt: str) -> str:  # noqa: ARG001 - the seam's signature
    """The local engine is refused on purpose: the template fallback is the path under test.

    `social_pulse.generate_caption` documents the fallback as the designed path
    when the engine is down; the seller-tester must not depend on a GPU, a model
    download or a socket, so it asks for that path explicitly.
    """
    raise RuntimeError("no local model in the seller-tester lane")


def run_social_caption(brief: Dict[str, Any], *, work_dir: Path) -> Dict[str, Any]:
    """Run the real SocialPulse caption pipeline and judge what it produced."""
    _backend()
    import social_pulse  # noqa: PLC0415

    platform = str(brief.get("platform") or "instagram")
    product = dict(brief.get("product") or {})
    brand = str(brief.get("brand") or "Harbor")
    voice = brief.get("voice")
    result = social_pulse.generate_caption(
        product=product, platform=platform, brand=brand,
        angle=str(brief.get("angle") or "quality"),
        voice=dict(voice) if isinstance(voice, Mapping) else None,
        generator=_refuse_model)
    caption = str(result.get("caption") or "")
    hashtags = [str(tag) for tag in (result.get("hashtags") or [])]
    spec = dict(result.get("platform_spec") or {})
    cta = str(result.get("cta") or "")
    facts = [str(f) for f in (brief.get("facts") or [])]
    checks: Dict[str, Dict[str, Any]] = {}

    checks["caption_returned"] = (
        _ok("caption_returned", chars=len(caption)) if len(caption) >= 20 else
        _bad("caption_returned", f"caption is {len(caption)} chars; the product is empty"))
    limit = int(spec.get("max_caption_length") or 0)
    checks["caption_within_platform_limit"] = (
        _ok("caption_within_platform_limit", chars=len(caption), limit=limit)
        if limit and len(caption) <= limit else
        _bad("caption_within_platform_limit", f"caption {len(caption)} > spec {limit}"))
    checks["platform_spec_reported"] = (
        _ok("platform_spec_reported", spec=spec) if spec.get("max_caption_length") else
        _bad("platform_spec_reported", "the pipeline returned no platform spec"))
    cap = int(spec.get("max_hashtags") or 0)
    checks["hashtags_within_platform_cap"] = (
        _ok("hashtags_within_platform_cap", hashtags=len(hashtags), cap=cap)
        if cap and len(hashtags) <= cap else
        # The cap is recorded on the failing row too: "measured, not waived" means the evidence
        # carries the number the check was measured against, not only the verdict.
        _bad("hashtags_within_platform_cap",
             f"{len(hashtags)} hashtags for a platform capped at {cap}",
             hashtags=len(hashtags), cap=cap))
    wanted = int((voice or {}).get("hashtags_per_post") or 10)
    checks["hashtag_count_matches_voice"] = (
        _ok("hashtag_count_matches_voice", hashtags=len(hashtags), wanted=wanted)
        if 0 < len(hashtags) <= wanted else
        _bad("hashtag_count_matches_voice",
             f"{len(hashtags)} hashtags, voice asks up to {wanted}"))
    checks["cta_returned"] = (
        _ok("cta_returned", cta=cta) if cta else
        _bad("cta_returned", "the pipeline returned no call to action"))
    checks["brand_named"] = (
        _ok("brand_named", brand=brand) if brand.lower() in caption.lower() else
        _bad("brand_named", f"the caption never names {brand!r}"))
    claims = _claim_hits(caption)
    checks["no_disease_or_treatment_claim"] = (
        _ok("no_disease_or_treatment_claim") if not claims else
        _bad("no_disease_or_treatment_claim", f"claims the app screens for: {claims}"))
    if not facts:
        checks["no_unsourced_number"] = _skip(
            "no_unsourced_number", "this brief declares no facts, so a number cannot be traced")
    else:
        invented = _unsourced_numbers(caption, facts)
        checks["no_unsourced_number"] = (
            _ok("no_unsourced_number", numbers=_numbers(caption)) if not invented else
            _bad("no_unsourced_number", f"numbers with no source in the brief: {invented}"))
    app_score = result.get("score")
    checks["app_score_recorded"] = (
        _ok("app_score_recorded", score=app_score)
        if isinstance(app_score, (int, float)) and 0 <= float(app_score) <= 100 else
        _bad("app_score_recorded", f"the pipeline returned score {app_score!r}"))

    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / f"{brief.get('id')}.json"
    target.write_text(json.dumps({"brief": brief.get("id"), "result": result,
                                  "checks": checks}, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    scored = _score(checks)
    return {"path": "social_caption", "brief_id": brief.get("id"),
            "artefact": str(target), "caption_chars": len(caption),
            "hashtags": len(hashtags), "checks": checks, **scored}


RUNNERS = {"offer_copy": run_offer_copy, "caption": run_caption,
           "social_caption": run_social_caption}


__all__ = ["CopyRefused", "OWNERS", "PATHS", "RUNNERS", "run_caption",
           "run_offer_copy", "run_social_caption"]
