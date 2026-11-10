"""Listing Optimizer — audit, keyword coverage, rewrite, re-score.

Reported gap: "Bojo does not optimize an uploaded listing properly, especially
for SEO. It lacks required inputs and a scoring rubric."

The rubric here is explicit and deterministic, and every score is traceable to a
named check — no invented keywords, no invented search volumes, no rank claims.
Target keywords can only come from the operator (or the Brand SEO Profile); if
none are supplied the agent asks instead of guessing.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

BACKEND_BYTE_LIMIT = 250
TITLE_SOFT_MAX = 200
# VERIFIED 2026-10-23 against nexscope-ai/Amazon-Skills
# (amazon-listing-optimization/SKILL.md line 160: "Bullet Points (5 bullets, max
# 500 chars each)"). The first build used 250 and flagged compliant bullets as
# too long.
BULLET_SOFT_MAX = 500
DESCRIPTION_SOFT_MAX = 2000

#: The studied 8-dimension rubric, with its published weights. Our agent can only
#: MEASURE the dimensions an operator uploads data for, so the rest are reported
#: as not_measured rather than silently scored as zero.
RUBRIC = (
    ("title", 15, "primary keyword near the front, brand, attributes, <=200 chars"),
    ("bullets", 15, "all five used, benefit-first, keyword embedded, <=500 chars each"),
    ("images", 15, "7+ images, white-background main, infographic, lifestyle, size ref, video"),
    ("aplus", 10, "present, brand story, comparison chart, lifestyle imagery"),
    ("description", 10, "keywords not already in title/bullets, problem-solution flow"),
    ("pricing", 10, "competitive, coupon or deal present"),
    ("reviews", 15, "4.0+ stars, 100+ reviews, recent reviews positive"),
    ("seo", 10, "primary keyword in title+bullets+description, long-tail present, no repeats"),
)

_PROMO = ("best seller", "best-seller", "#1", "number one", "free shipping",
          "sale", "discount", "buy now", "limited time", "guarantee",
          "100% satisfaction", "cheapest")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
_ALLCAPS = re.compile(r"\b[A-Z]{4,}\b")


def _words(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9][a-z0-9'+-]*", str(text or "").lower())]


def audit_title(title: str) -> List[str]:
    issues: List[str] = []
    t = str(title or "")
    if not t.strip():
        issues.append("title is empty")
        return issues
    if len(t) > TITLE_SOFT_MAX:
        issues.append(f"title is {len(t)} chars; keep it under {TITLE_SOFT_MAX}")
    if _EMOJI.search(t):
        issues.append("title contains emoji")
    if _ALLCAPS.search(t):
        issues.append(f"title shouts: {_ALLCAPS.search(t).group(0)}")
    low = t.lower()
    for word in _PROMO:
        if word in low:
            issues.append(f"promotional claim in title: '{word}'")
    if t.count(",") > 3:
        issues.append("too many commas — the title reads as a keyword dump")
    return issues


def audit_bullet(bullet: str, index: int = 1) -> List[str]:
    issues: List[str] = []
    b = str(bullet or "").strip()
    if not b:
        return [f"bullet {index} is empty"]
    if len(b) > BULLET_SOFT_MAX:
        issues.append(f"bullet {index} is {len(b)} chars; keep it under {BULLET_SOFT_MAX}")
    low = b.lower()
    for word in _PROMO:
        if word in low:
            issues.append(f"bullet {index} carries a promotional claim: '{word}'")
    if not re.match(r"^[A-Z0-9]", b):
        issues.append(f"bullet {index} does not start with a capital or number")
    return issues


def keyword_coverage(title: str, bullets: Sequence[str], backend: str,
                     keywords: Sequence[str]) -> Dict[str, Any]:
    haystack = " ".join([str(title or "")] + [str(b or "") for b in bullets]).lower()
    backend_low = str(backend or "").lower()
    rows = []
    for kw in keywords:
        k = str(kw).strip()
        if not k:
            continue
        in_copy = k.lower() in haystack
        in_backend = k.lower() in backend_low
        rows.append({"keyword": k, "in_copy": in_copy, "in_backend": in_backend,
                     "covered": in_copy or in_backend})
    covered = sum(1 for r in rows if r["covered"])
    return {
        "keywords": rows,
        "covered": covered,
        "total": len(rows),
        "coverage": round(covered / len(rows), 3) if rows else 0.0,
    }


def backend_bytes(terms: str) -> int:
    return len(str(terms or "").encode("utf-8"))


def clean_backend_terms(terms: Sequence[str], *, title: str, bullets: Sequence[str],
                        limit: int = BACKEND_BYTE_LIMIT) -> Dict[str, Any]:
    """Deduplicate against the visible copy and fit the byte limit.

    Amazon indexes the backend field; repeating a word already in the title buys
    nothing and burns the 250 bytes. Words are added in the operator's order.
    """
    visible = set(_words(title) + [w for b in bullets for w in _words(b)])
    seen: set = set()
    out: List[str] = []
    dropped: List[str] = []
    for raw in terms:
        for word in _words(raw):
            if word in visible or word in seen:
                dropped.append(word)
                continue
            candidate = " ".join(out + [word])
            if len(candidate.encode("utf-8")) > limit:
                dropped.append(word)
                continue
            out.append(word)
            seen.add(word)
    result = " ".join(out)
    return {"terms": result, "bytes": backend_bytes(result), "limit": limit,
            "dropped": sorted(set(dropped))}


def rewrite(title: str, bullets: Sequence[str], keywords: Sequence[str],
            *, max_bullets: int = 5) -> Dict[str, Any]:
    """Deterministic rewrite: primary keyword leads, squeezes promo, adds coverage."""
    kws = [str(k).strip() for k in keywords if str(k).strip()]
    primary = kws[0] if kws else ""
    base = re.sub(r"\s+", " ", str(title or "")).strip()
    for word in _PROMO:
        base = re.sub(re.escape(word), "", base, flags=re.IGNORECASE)
    base = _EMOJI.sub("", base).strip(" ,-|")
    new_title = base
    if primary and primary.lower() not in base.lower():
        new_title = f"{base} - {primary}" if base else primary
    if len(new_title) > TITLE_SOFT_MAX:
        new_title = new_title[:TITLE_SOFT_MAX].rstrip(" ,-")

    pool = [k for k in kws[1:]]
    new_bullets: List[str] = []
    for i, raw in enumerate(list(bullets)[:max_bullets]):
        text = re.sub(r"\s+", " ", str(raw or "")).strip()
        for word in _PROMO:
            text = re.sub(re.escape(word), "", text, flags=re.IGNORECASE)
        text = text.strip(" ,-|")
        if i < len(pool) and pool[i].lower() not in text.lower():
            text = f"{text} — {pool[i]}" if text else pool[i]
        new_bullets.append(text.strip())
    while len(new_bullets) < min(max_bullets, len(pool) + len(bullets)):
        add = pool[len(new_bullets) - len(bullets)] if len(new_bullets) - len(bullets) < len(pool) else None
        if not add:
            break
        new_bullets.append(f"{add[0].upper() + add[1:]}")
    return {"title": new_title[:TITLE_SOFT_MAX], "bullets": new_bullets[:max_bullets]}


def optimize(*, title: str, bullets: Sequence[str], keywords: Sequence[str],
             description: str = "", backend_terms: str = "") -> Dict[str, Any]:
    """Full pass with a before/after score and a change log."""
    if not [k for k in keywords if str(k).strip()]:
        return {
            "ok": False,
            "status": "needs_input",
            "summary": ("I need your target keywords before I can score SEO coverage — "
                        "I will not invent search terms."),
            "questions": [{"field": "keywords",
                           "question": "Which target keywords should this listing cover?"}],
        }
    bullets = [str(b) for b in bullets if str(b).strip()][:5]
    before_issues: List[str] = audit_title(title)
    for i, b in enumerate(bullets, 1):
        before_issues.extend(audit_bullet(b, i))
    before_cov = keyword_coverage(title, bullets, backend_terms, keywords)
    before_score = _score(before_issues, before_cov)

    new = rewrite(title, bullets, keywords)
    after_backend = clean_backend_terms(
        [k for k in keywords if k.lower() not in " ".join([new["title"]] + new["bullets"]).lower()],
        title=new["title"], bullets=new["bullets"])
    after_issues: List[str] = audit_title(new["title"])
    for i, b in enumerate(new["bullets"], 1):
        after_issues.extend(audit_bullet(b, i))
    after_cov = keyword_coverage(new["title"], new["bullets"], after_backend["terms"], keywords)
    after_score = _score(after_issues, after_cov)

    changes = []
    if new["title"] != title:
        changes.append({"field": "title", "before": title, "after": new["title"],
                        "why": "removed promotional language, led with the primary keyword"})
    for i, (old, thing) in enumerate(zip(bullets, new["bullets"]), 1):
        if old.strip() != thing:
            changes.append({"field": f"bullet {i}", "before": old, "after": thing,
                            "why": "stripped promo, attached an uncovered keyword"})
    if after_backend["terms"]:
        changes.append({"field": "backend_search_terms", "before": backend_terms,
                        "after": after_backend["terms"],
                        "why": f"{after_backend['bytes']}/{after_backend['limit']} bytes, "
                               f"deduplicated against visible copy"})

    return {
        "ok": True,
        "status": "optimized",
        "summary": (f"Score {before_score['total']} → {after_score['total']} "
                    f"(of 100). Keyword coverage {before_cov['covered']}/{before_cov['total']} "
                    f"→ {after_cov['covered']}/{after_cov['total']}."),
        "before": {"score": before_score, "issues": before_issues, "coverage": before_cov},
        "after": {"score": after_score, "issues": after_issues, "coverage": after_cov},
        "listing": {"title": new["title"], "bullets": new["bullets"],
                    "backend_search_terms": after_backend["terms"],
                    "backend_bytes": after_backend["bytes"]},
        "change_log": changes,
        "rubric": _rubric_block(title=new["title"], bullets=new["bullets"],
                                description=description, coverage=after_cov),
        "notes": ["Scores are deterministic rubric points, not Amazon rank or volume.",
                  "Rubric weights and character limits cited from nexscope-ai/Amazon-Skills "
                  "(MIT) — see research/amazon-skills/evidence.md.",
                  "Dimensions we cannot measure from your upload are reported as "
                  "not_measured, never scored as zero.",
                  "Upload the rewritten listing yourself; nothing is pushed to Amazon."],
    }


def _rubric_block(*, title: str, bullets: Sequence[str], description: str,
                  coverage: Dict[str, Any]) -> Dict[str, Any]:
    """Report all eight dimensions; score only the three we can actually measure."""
    measured = {
        "title": not audit_title(title),
        "bullets": all(not audit_bullet(b, i) for i, b in enumerate(bullets, 1)),
        "seo": bool(coverage.get("total")) and coverage["covered"] == coverage["total"],
    }
    rows = []
    for key, weight, criteria in RUBRIC:
        can = key in measured
        rows.append({
            "dimension": key,
            "weight": weight,
            "criteria": criteria,
            "measured": can,
            "passed": measured.get(key) if can else None,
            "needs": None if can else "operator data (images/A+/pricing/reviews/description)",
        })
    return {
        "source": "nexscope-ai/Amazon-Skills amazon-listing-optimization/SKILL.md (MIT)",
        "total_weight": sum(w for _k, w, _c in RUBRIC),
        "measurable_weight": sum(w for k, w, _c in RUBRIC if k in measured),
        "dimensions": rows,
    }


def _score(issues: Sequence[str], coverage: Dict[str, Any]) -> Dict[str, Any]:
    compliance = max(0, 60 - 8 * len(issues))
    cov_points = round(40 * float(coverage.get("coverage") or 0.0))
    total = min(100, compliance + cov_points)
    return {"total": total, "compliance": compliance, "seo": cov_points,
            "issues": len(issues)}
