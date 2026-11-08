"""Relevance, ranking and the gap list (D11 / A21).

Scoring is explainable and fixed:

``score = 100 * (0.35*relevance + 0.15*licence + 0.10*popularity + 0.10*vet + 0.10*evidence + 0.20*lift)``

* ``relevance``  keyword evidence against ``ty/services.json`` profiles (0..1)
* ``licence``    licence cleanliness (unknown is low, non-commercial is zero)
* ``popularity`` log10(stars or downloads) normalised against 100k
* ``vet``        OSV verdict factor (malicious is zero, incomplete is low)
* ``evidence``   how many independent fields the hit actually carries
* ``lift``       gap-capped estimated score lift, normalised to 0..1

``estimated_lift`` is a *service score point* estimate, capped by the remaining
gap in ``ty/scorecards.json``.  It is explicitly an estimate and its basis is
written into every finding, so nobody can mistake it for a measurement.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import config, evidence as evidence_engine
from .licence import cleanliness

_TOKEN = re.compile(r"[^a-z0-9]+")
_STOP = {"the", "and", "for", "with", "from", "your", "our", "that", "this",
         "app", "tool", "tools", "open", "source", "free", "based", "using"}


def _terms(text: str) -> List[str]:
    return [token for token in _TOKEN.split(str(text or "").lower())
            if len(token) >= 3 and token not in _STOP]


def _profile(service: Dict[str, Any]) -> Dict[str, List[str]]:
    service_id = str(service.get("id") or "")
    curated = config.SERVICE_KEYWORDS.get(service_id)
    if curated:
        return {"primary": [t.lower() for t in curated.get("primary", [])],
                "secondary": [t.lower() for t in curated.get("secondary", [])]}
    label = str(service.get("label") or service_id).lower()
    words = [word for word in _terms(label) if len(word) >= 4]
    return {"primary": [" ".join(words)] if len(words) > 1 else words,
            "secondary": words}


def _text_of(hit: Dict[str, Any]) -> str:
    parts = [str(hit.get("title") or ""), str(hit.get("description") or "")]
    for key in ("topics", "tags", "classifiers", "primary_category"):
        value = hit.get(key)
        if isinstance(value, (list, tuple)):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    raw = " ".join(parts).lower()
    # Keep both forms: "background-removal" and "background removal" must match.
    spaced = re.sub(r"[-_/]+", " ", raw)
    return f"{raw} {spaced}"


def off_domain(hit: Dict[str, Any]) -> Optional[str]:
    """Return the off-domain marker that disqualifies a hit, or ``None``."""
    text = _text_of(hit)
    hard = next((term for term in config.HARD_OFF_DOMAIN if term in text), None)
    if hard:
        return hard
    marker = next((term for term in config.OFF_DOMAIN if term in text), None)
    if not marker:
        return None
    if any(term in text for term in config.RETAIL_CONTEXT):
        return None
    return marker


def match_services(hit: Dict[str, Any], services: Iterable[Dict[str, Any]],
                   *, hint: Optional[str] = None) -> Tuple[Optional[str], float, List[str]]:
    """Best service for a hit plus its relevance (0..1) and matched terms."""
    text = _text_of(hit)
    if not text.strip():
        return None, 0.0, []
    best_id: Optional[str] = None
    best_relevance = 0.0
    best_terms: List[str] = []
    for service in services:
        service_id = str(service.get("id") or "")
        profile = _profile(service)
        matched: List[str] = []
        raw = 0.0
        for term in profile["primary"]:
            if term and term in text:
                raw += 1.0
                matched.append(term)
        for term in profile["secondary"]:
            if term and term in text and term not in matched:
                raw += 0.5
                matched.append(term)
        if raw <= 0:
            continue
        relevance = min(1.0, raw / 2.5)
        if hint and hint == service_id:
            relevance = min(1.0, relevance + 0.10)
        if relevance > best_relevance:
            best_id, best_relevance, best_terms = service_id, relevance, matched
    return best_id, round(best_relevance, 3), best_terms


def popularity(value: Optional[int]) -> float:
    if value is None:
        return 0.0
    try:
        number = max(0, int(value))
    except (TypeError, ValueError):
        return 0.0
    return round(min(1.0, math.log10(1 + number) / 5.0), 4)


def composite(*, relevance: float, licence_class: str, popularity_score: float,
              vet_score: float, evidence_score: float, lift: float = 0.0) -> float:
    weights = config.WEIGHTS
    lift_norm = min(1.0, max(0.0, float(lift)) / config.LIFT_CEILING)
    total = (weights["relevance"] * relevance
             + weights["licence"] * cleanliness(licence_class)
             + weights["popularity"] * popularity_score
             + weights["vet"] * vet_score
             + weights["evidence"] * evidence_score
             + weights["lift"] * lift_norm)
    return round(100.0 * min(1.0, max(0.0, total)), 1)


def estimated_lift(*, relevance: float, licence_class: str, popularity_score: float,
                   vet_score: float, gap: Optional[float]) -> Tuple[float, str]:
    base = 2.0 + 12.0 * (0.50 * relevance
                         + 0.20 * cleanliness(licence_class)
                         + 0.15 * popularity_score
                         + 0.15 * vet_score)
    cap = 100.0 if gap is None else max(0.0, float(gap))
    lift = round(min(cap, base), 1)
    basis = ("gap_capped(2 + 12*(0.50*relevance + 0.20*licence + 0.15*popularity "
             "+ 0.15*vet)); gap=" + ("unknown" if gap is None else f"{cap:.1f}"))
    return lift, basis


def rank(findings: Iterable[Dict[str, Any]], services: List[Dict[str, Any]], *,
         gaps: Optional[Dict[str, float]] = None,
         hints: Optional[Dict[str, str]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Assign service/score/lift and return ``(ranked, dropped)``.

    A hit with no service keyword evidence is dropped here and counted by the
    caller; it is not silently assigned to a random service.
    """
    gaps = gaps or {}
    hints = hints or {}
    ranked: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for finding in findings:
        marker = off_domain(finding)
        if marker:
            finding["drop_reason"] = f"off_domain:{marker}"
            dropped.append(finding)
            continue
        hint = (str(finding.get("_service_hint") or "")
                or hints.get(str(finding.get("identity") or "").lower()))
        service_id, relevance, matched = match_services(finding, services, hint=hint)
        if not service_id or relevance < config.MIN_RELEVANCE:
            finding["relevance"] = relevance
            finding["matched_terms"] = matched
            dropped.append(finding)
            continue
        pop = popularity(finding.get("stars") if finding.get("stars") is not None
                         else finding.get("downloads"))
        from .vet import vet_factor  # local import avoids a cycle at module load

        vet_score = vet_factor(finding.get("vet"))
        evidence_score = evidence_engine.strength(finding)
        gap = gaps.get(service_id)
        lift, lift_basis = estimated_lift(
            relevance=relevance, licence_class=str(finding.get("licence_class") or "unknown"),
            popularity_score=pop, vet_score=vet_score, gap=gap)
        finding.update({
            "service": service_id,
            "service_label": _label(service_id, services),
            "relevance": relevance,
            "matched_terms": matched,
            "popularity_score": pop,
            "vet_score": vet_score,
            "evidence_score": evidence_score,
            "estimated_lift": lift,
            "lift_basis": lift_basis,
            "gap_remaining": gap,
            "score": composite(relevance=relevance,
                               licence_class=str(finding.get("licence_class") or "unknown"),
                               popularity_score=pop, vet_score=vet_score,
                               evidence_score=evidence_score, lift=lift),
        })
        ranked.append(finding)

    ranked.sort(key=lambda row: (-float(row.get("score") or 0.0),
                                 -float(row.get("estimated_lift") or 0.0),
                                 str(row.get("title") or "").lower()))
    for position, finding in enumerate(ranked, start=1):
        finding["rank"] = position
    return ranked, dropped


def _label(service_id: str, services: List[Dict[str, Any]]) -> str:
    for service in services:
        if str(service.get("id")) == service_id:
            return str(service.get("label") or service_id)
    return service_id


def gaps_from(findings: List[Dict[str, Any]], services: List[Dict[str, Any]],
              *, top: int = 3) -> List[Dict[str, Any]]:
    """A21 gap list: per service, best findings + a falsifiable hypothesis."""
    by_service: Dict[str, List[Dict[str, Any]]] = {}
    for finding in findings:
        by_service.setdefault(str(finding.get("service")), []).append(finding)
    rows: List[Dict[str, Any]] = []
    for service_id, items in by_service.items():
        items.sort(key=lambda row: (-float(row.get("estimated_lift") or 0.0),
                                    -float(row.get("score") or 0.0)))
        chosen = items[:top]
        lift = round(sum(float(item.get("estimated_lift") or 0.0) for item in chosen), 1)
        gap = chosen[0].get("gap_remaining")
        if gap is not None:
            lift = round(min(float(gap), lift), 1)
        lead = chosen[0]
        rows.append({
            "service": service_id,
            "service_label": lead.get("service_label"),
            "open_gap": gap,
            "yield_score": lift,
            "findings": [item.get("id") for item in chosen],
            "hypothesis": (
                f"If {lead.get('service_label') or service_id} adopts "
                f"{lead.get('title')} ({lead.get('licence')}, status "
                f"{lead.get('status')}), expect up to {lead.get('estimated_lift')} pts "
                f"because {evidence_engine.summarise(lead.get('evidence') or {})}."
            ),
        })
    rows.sort(key=lambda row: (-float(row.get("yield_score") or 0.0),
                               str(row.get("service") or "")))
    return rows
