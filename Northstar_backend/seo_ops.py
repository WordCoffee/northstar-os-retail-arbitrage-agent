"""Deterministic cross-service SEO operations (V3 S7 §5.3 pipeline features).

Beyond *scoring* copy (`seo_score`), two services need to *act* on the profile:

  • AdPilot — turn a list of search terms into **negatives** (terms matching the
    profile's negative cluster or a competitor) and **harvest** candidates
    (terms matching a head/body cluster worth adding as exact keywords).
  • SourceScout / ListingForge — **retitle** a raw title toward the profile's
    head clusters, inside a length budget.

Both are pure, deterministic transforms of the operator's OWN profile. Nothing
here calls a network, predicts a rank, or invents a keyword that is not already in
the profile. Neither writes anything: they return suggestions the operator acts on.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from seo_score import keyword_clusters


def _split_terms(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = re.split(r"[\n,]+", value)
    elif isinstance(value, (list, tuple)):
        raw = []
        for v in value:
            raw.extend(re.split(r"[\n,]+", str(v)))
    else:
        raw = [str(value)]
    out, seen = [], set()
    for t in raw:
        s = t.strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def classify_search_terms(profile: Dict[str, Any], terms: Any) -> Dict[str, Any]:
    """Split search terms into negatives / harvest / ignored against the profile.

    Deterministic substring matching on the operator's own clusters. No inference
    about performance is made — a harvest term is 'worth testing', not 'a winner'.
    """
    head, body, negative = keyword_clusters(profile)
    competitors = [str(c).strip().lower() for c in ((profile or {}).get("competitors") or [])
                   if str(c).strip()]

    negatives: List[Dict[str, Any]] = []
    harvest: List[Dict[str, Any]] = []
    ignored: List[str] = []

    for term in _split_terms(terms):
        low = term.lower()
        neg_hit = next((n for n in negative if n in low or low in n), None)
        comp_hit = next((c for c in competitors if c in low or low in c), None)
        if neg_hit or comp_hit:
            negatives.append({"term": term,
                              "reason": f"negative '{neg_hit}'" if neg_hit
                              else f"competitor '{comp_hit}'"})
            continue
        head_hit = next((h for h in head if h in low), None)
        if head_hit:
            harvest.append({"term": term, "section": "head", "match": head_hit})
            continue
        body_hit = next((b for b in body if b in low), None)
        if body_hit:
            harvest.append({"term": term, "section": "body", "match": body_hit})
            continue
        ignored.append(term)

    caveats = [
        "Deterministic matching against the operator's own profile clusters.",
        "A harvest term is a candidate to test — no performance is predicted.",
    ]
    if not _split_terms(terms):
        caveats.append("No search terms were supplied.")

    return {
        "negatives": negatives,
        "harvest": harvest,
        "ignored": ignored,
        "negative_count": len(negatives),
        "harvest_count": len(harvest),
        "caveats": caveats,
    }


def retitle(profile: Dict[str, Any], title: Any, *, max_len: int = 200,
            separator: str = " — ") -> Dict[str, Any]:
    """Normalise a title toward the profile's head clusters within a length budget.

    Prepends missing head terms (cluster order) while the result fits; truncates
    honestly at the budget. A starting point for the operator — not a ranking claim.
    """
    original = " ".join(str(title or "").split())
    head, _body, _neg = keyword_clusters(profile)
    try:
        max_len = max(int(max_len), 20)
    except (TypeError, ValueError):
        max_len = 200

    low = original.lower()
    present = [h for h in head if h in low]
    missing = [h for h in head if h not in low]

    new = original
    changes: List[str] = []
    added: List[str] = []
    for h in missing:
        trial_labels = [x.strip().title() for x in (added + [h])]
        trial = separator.join(trial_labels + ([original] if original else []))
        if len(trial) <= max_len:
            added.append(h)
    if added:
        labels = [x.strip().title() for x in added]
        new = separator.join(labels + ([original] if original else []))
        changes.extend(f"prepended head term '{h}'" for h in added)

    if len(new) > max_len:
        new = new[:max_len].rstrip()
        changes.append(f"truncated to {max_len} characters")

    if not changes:
        changes.append("no change — head terms already present or no room within the budget")

    return {
        "title": new,
        "original": original,
        "present_head": present,
        "missing_head": missing,
        "length": len(new),
        "max_len": max_len,
        "changes": changes,
        "caveats": [
            "Deterministic rewrite toward the operator's own head terms.",
            "Not a promise of ranking or traffic — a compliant starting point.",
        ],
    }
