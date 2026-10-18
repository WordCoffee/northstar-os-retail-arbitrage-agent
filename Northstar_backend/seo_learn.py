"""Profile learning from imported measurement (V3 S7 §5.4) — honest by design.

The Brand Analytics importer lands Search Query Performance rows in
`search_query_performance` (nothing here re-reads the network). This module turns
those *measured* rows into **candidate** keyword additions for a brand profile.

Rules that keep it honest:
  • It only proposes terms that are NOT already in the profile's clusters.
  • Ranking uses the measured `search_frequency_rank` (lower = more frequent),
    then impressions — never a modelled or invented number.
  • It makes **no rank / traffic / volume claims**; a proposal is a candidate for
    the operator to accept or reject, never an automatic edit.
  • Approving is an operator action and appends a new profile version (the
    existing append-only version path); nothing is written silently here.

Pure and offline: `propose_from_sqp` takes rows in, returns proposals out.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from seo_score import keyword_clusters


def _int(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError, AttributeError):
        return 0


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError, AttributeError):
        return None


def propose_from_sqp(
    profile_body: Dict[str, Any],
    rows: List[Dict[str, Any]],
    *,
    limit: int = 12,
    min_impressions: int = 0,
) -> Dict[str, Any]:
    """Return candidate profile terms derived from imported SQP rows.

    Deterministic. Proposals only; the engine never writes a profile.
    """
    head, body, negative = keyword_clusters(profile_body)
    known = {t for t in (head + body + negative) if t}

    def covered(query: str) -> bool:
        return any(k in query or query in k for k in known)

    agg: Dict[str, Dict[str, Any]] = {}
    for row in rows or []:
        query = str(row.get("query") or "").strip()
        if not query:
            continue
        key = query.lower()
        a = agg.setdefault(key, {"term": query, "impressions": 0, "clicks": 0,
                                 "purchases": 0, "search_frequency_rank": None})
        a["impressions"] += _int(row.get("impressions"))
        a["clicks"] += _int(row.get("clicks"))
        a["purchases"] += _int(row.get("purchases"))
        sfr = _int_or_none(row.get("search_frequency_rank"))
        if sfr is not None and (a["search_frequency_rank"] is None or sfr < a["search_frequency_rank"]):
            a["search_frequency_rank"] = sfr

    candidates = [a for key, a in agg.items()
                  if a["impressions"] >= min_impressions and not covered(key)]
    candidates.sort(key=lambda a: (a["search_frequency_rank"] if a["search_frequency_rank"] is not None
                                   else 10 ** 9, -a["impressions"]))
    proposals = []
    for a in candidates[:max(int(limit), 0)]:
        proposals.append({
            "term": a["term"],
            "evidence": "imported SQP",
            "impressions": a["impressions"],
            "clicks": a["clicks"],
            "purchases": a["purchases"],
            "search_frequency_rank": a["search_frequency_rank"],
        })

    caveats = [
        "Candidates from imported Search Query Performance rows — not recommendations.",
        "No rank, traffic or volume is predicted; ranking uses measured search frequency rank.",
        "Approving a proposal is an operator action that appends a new profile version.",
    ]
    if not rows:
        caveats.append("No SQP rows were supplied; nothing to propose from.")
    if not proposals and rows:
        caveats.append("No new terms: the imported queries are already covered by the profile.")

    return {
        "proposals": proposals,
        "proposal_count": len(proposals),
        "known_term_count": len(known),
        "considered_query_count": len(agg),
        "caveats": caveats,
    }
