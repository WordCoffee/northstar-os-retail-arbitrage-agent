"""AdPilot's own ad copy, scored by the app's own rules.

PPC was the last core service whose *seller* dimension came from somewhere else: the ads path
scored under design-studio (the bulksheet upload we actually drive), while AdPilot's own copy — the
headline, body and call to action a seller puts in a sponsored-products ad — had no instrument at
all. This is that instrument, in the same shape as the other copy rooms: named checks, the share of
graded checks that passed, a skip is never a pass, and the copy is a **recorded fixture of the
room's own output** because a paid/cloud call is a gated action.

Where the checks come from (all deterministic, all the app's own rules):

* the sponsored-products caps on a headline and a body line;
* one call to action per variant, not a paragraph;
* the brand named in the copy;
* the claims lint (no disease/treatment claims) and no unsourced number;
* no other brand's name in the copy;
* at least three variants, because one option is not a test.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .copy import (  # noqa: F401 - the helpers are shared with the other copy rooms
    CopyRefused,
    _bad,
    _brand_key,
    _claim_hits,
    _cross_brand_hits,
    _ok,
    _score,
    _unsourced_numbers,
)

#: OWNER-CONFIRMED AD TYPE (2026-11-15): Sponsored Products.
#: The caps in this module (headline 60, body 150) are Sponsored Products limits. Sponsored
#: Brands and Sponsored Display use different caps and placements, so if the owner ever changes
#: the target ad type, the caps and the fixtures change together and the score is re-run.
#: `ASSUMED_AD_TYPE` is kept as an alias for callers/tests written before the confirmation.
AD_TYPE = "Sponsored Products"
ASSUMED_AD_TYPE = AD_TYPE

BRIEFS = Path(__file__).resolve().parent / "ad_copy_briefs.json"
DEFAULT_HEADLINE_CAP = 60
DEFAULT_BODY_CAP = 150
MIN_VARIANTS = 3


def _unsourced_digits(text: str, facts: Sequence[str]) -> List[str]:
    """Numbers in the copy whose digits do not appear in any declared fact."""
    pool = " ".join(str(f) for f in facts)
    fact_digits = set(re.findall(r"\d+(?:\.\d+)?", pool))
    return [n for n in re.findall(r"\d+(?:\.\d+)?", text) if n not in fact_digits]


def _parse_variants(answer: str) -> List[Dict[str, str]]:
    """HEADLINE:/BODY:/CTA: blocks, one variant per block. A block without a CTA is still a block."""
    variants: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    field = ""
    for raw in (answer or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("HEADLINE:"):
            if current:
                variants.append(current)
                current = {}
            field = "headline"
            current[field] = line.split(":", 1)[1].strip()
        elif upper.startswith("BODY:"):
            field = "body"
            current[field] = line.split(":", 1)[1].strip()
        elif upper.startswith("CTA:"):
            field = "cta"
            current[field] = line.split(":", 1)[1].strip()
        elif field:
            current[field] = (current.get(field, "") + " " + line).strip()
    if current:
        variants.append(current)
    return variants


def run_ad_copy(brief: Dict[str, Any], *, work_dir: Path | None = None) -> Dict[str, Any]:
    """Score one recorded AdPilot answer against the sponsored-products rules."""
    answer = str(brief.get("recorded_answer") or "")
    if not answer.strip():
        raise CopyRefused(f"{brief.get('id')}: the fixture records no ad-copy answer")

    variants = _parse_variants(answer)
    checks: Dict[str, Dict[str, Any]] = {}
    checks["answer_parsed"] = (
        _ok("answer_parsed", variants=len(variants)) if variants else
        _bad("answer_parsed", "no HEADLINE:/BODY:/CTA: block in the recorded answer"))
    checks["variants_at_least_three"] = (
        _ok("variants_at_least_three", variants=len(variants)) if len(variants) >= MIN_VARIANTS else
        _bad("variants_at_least_three", f"{len(variants)} variant(s); the room asks for at least "
                                        f"{MIN_VARIANTS}", variants=len(variants)))

    brand = str(brief.get("brand") or "")
    facts: Sequence[str] = [str(f) for f in (brief.get("facts") or [])]
    headline_cap = int(brief.get("headline_cap") or DEFAULT_HEADLINE_CAP)
    body_cap = int(brief.get("body_cap") or DEFAULT_BODY_CAP)

    long_headlines = [(v.get("headline") or "") for v in variants
                      if len(v.get("headline") or "") > headline_cap]
    checks["headline_within_cap"] = (
        _ok("headline_within_cap", cap=headline_cap) if not long_headlines else
        _bad("headline_within_cap",
             f"{len(long_headlines)} headline(s) over {headline_cap} chars",
             cap=headline_cap, longest=max(len(h) for h in long_headlines)))
    long_bodies = [v for v in variants if len(v.get("body") or "") > body_cap]
    checks["body_within_cap"] = (
        _ok("body_within_cap", cap=body_cap) if not long_bodies else
        _bad("body_within_cap", f"{len(long_bodies)} body line(s) over {body_cap} chars",
             cap=body_cap))
    missing_cta = [i for i, v in enumerate(variants) if not (v.get("cta") or "").strip()]
    checks["cta_present"] = (
        _ok("cta_present", variants=len(variants)) if variants and not missing_cta else
        _bad("cta_present", f"variant(s) without a call to action: {missing_cta}"))
    named = bool(brand) and any(brand.lower() in (v.get("headline", "") + " "
                                                  + v.get("body", "")).lower() for v in variants)
    checks["brand_named"] = (
        _ok("brand_named", brand=brand) if named else
        _bad("brand_named", f"the copy never names {brand!r}"))

    joined = " ".join(" ".join(v.values()) for v in variants)
    claims = _claim_hits(joined)
    checks["no_disease_or_treatment_claim"] = (
        _ok("no_disease_or_treatment_claim") if not claims else
        _bad("no_disease_or_treatment_claim", f"claims the app screens for: {claims}"))
    if not facts:
        checks["no_unsourced_number"] = {
            **_ok("no_unsourced_number"), "skipped": True,
            "detail": "this brief declares no facts, so a number cannot be traced"}
    else:
        # Compare the DIGITS, not the phrase. The shared helper groups a number with the word after
        # it ("90 count"), so a sourced 90 in "90 capsules" reads as unsourced — a false positive
        # the instrument must not have, because a check that fails on true copy teaches nothing.
        invented = _unsourced_digits(joined, facts)
        checks["no_unsourced_number"] = (
            _ok("no_unsourced_number", facts=list(facts)) if not invented else
            _bad("no_unsourced_number", f"numbers with no fact behind them: {invented}"))
    cross = _cross_brand_hits(joined, brand)
    checks["no_cross_brand"] = (
        _ok("no_cross_brand", brand=brand) if not cross else
        _bad("no_cross_brand", f"another brand's name appears: {cross}"))

    scored = _score(checks)
    row = {"id": brief.get("id"), "service": "adpilot", "path": "ad_copy",
           "checks": checks, **scored}
    return row


def load_briefs(path: Path | None = None) -> List[Dict[str, Any]]:
    data = json.loads(Path(path or BRIEFS).read_text(encoding="utf-8"))
    return list(data.get("ad_copy") or [])


def run_all(path: Path | None = None, *, work_dir: Path | None = None) -> Dict[str, Any]:
    rows = [run_ad_copy(brief, work_dir=work_dir) for brief in load_briefs(path)]
    passed = sum(1 for row in rows if row.get("passed"))
    mean = round(sum(float(row.get("score") or 0) for row in rows) / len(rows), 1) if rows else 0.0
    return {"service": "adpilot", "path": "ad_copy", "rows": rows,
            "scored": len(rows), "passed": passed, "mean": mean,
            "pass_rate": round(100.0 * passed / len(rows), 1) if rows else 0.0}


__all__ = ["BRIEFS", "load_briefs", "run_ad_copy", "run_all"]
