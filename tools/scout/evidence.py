"""Evidence extractor (D11 / A20).

A finding is only worth anything if the field that supports it can be named.
This module builds that field set from the payload we already hold; it does not
fetch anything.

A20 in the automation gate is "REA extractor: repo ``file:line``, video
timestamps, screenshots".  In this lane the extractor covers the first third
and the general form: ``citations()`` pulls ``path.ext:line`` anchors out of
any text field (README, summary, description) and ``build()`` names the
concrete source fields.  Video timestamps and screenshots belong to the media
lane, which this unit does not drive; the report says so rather than pretending
the extractor is complete.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

CITATION = re.compile(
    r"\b([A-Za-z0-9_][A-Za-z0-9_.\-/]*\.(?:py|js|jsx|ts|tsx|json|ya?ml|md|sh|html|css|ipynb))"
    r":(\d{1,5})\b"
)
_SPACE = re.compile(r"\s+")


def excerpt(text: Any, limit: int = 220) -> str:
    """First meaningful words, whitespace collapsed, no markup added."""
    cleaned = _SPACE.sub(" ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "..."


def citations(*texts: Any) -> List[str]:
    """``file:line`` anchors found in the given texts, de-duplicated, in order."""
    found: List[str] = []
    for text in texts:
        for match in CITATION.finditer(str(text or "")):
            anchor = f"{match.group(1)}:{match.group(2)}"
            if anchor not in found:
                found.append(anchor)
    return found


def build(hit: Dict[str, Any]) -> Dict[str, Any]:
    """The concrete fields that support this finding, per source."""
    source = str(hit.get("source") or "")
    evidence: Dict[str, Any] = {}
    if hit.get("stars") is not None:
        evidence["stars"] = hit["stars"]
    if hit.get("downloads") is not None:
        evidence["downloads"] = hit["downloads"]
    if hit.get("version"):
        evidence["version"] = hit["version"]
    if source == "github":
        if hit.get("forks") is not None:
            evidence["forks"] = hit["forks"]
        if hit.get("language"):
            evidence["language"] = hit["language"]
        if hit.get("topics"):
            evidence["topics"] = list(hit["topics"])[:6]
    elif source == "huggingface":
        if hit.get("likes") is not None:
            evidence["likes"] = hit["likes"]
        if hit.get("pipeline_tag"):
            evidence["pipeline_tag"] = hit["pipeline_tag"]
        if hit.get("tags"):
            evidence["tags"] = list(hit["tags"])[:8]
    elif source == "pypi":
        if hit.get("classifiers"):
            evidence["classifiers"] = list(hit["classifiers"])[:3]
        if hit.get("requires_python"):
            evidence["requires_python"] = hit["requires_python"]
    elif source == "npm":
        if hit.get("npm_score") is not None:
            evidence["npm_score"] = hit["npm_score"]
        if hit.get("publisher"):
            evidence["publisher"] = hit["publisher"]
    elif source == "arxiv":
        if hit.get("published_at"):
            evidence["published_at"] = hit["published_at"]
        if hit.get("authors"):
            evidence["authors"] = list(hit["authors"])[:4]
        if hit.get("primary_category"):
            evidence["primary_category"] = hit["primary_category"]
    if hit.get("description"):
        evidence["description"] = excerpt(hit.get("description"))
    if hit.get("updated_at"):
        evidence["updated_at"] = hit["updated_at"]
    anchors = citations(hit.get("description"), hit.get("summary"))
    if anchors:
        evidence["file_line"] = anchors[:5]
    evidence["source_field"] = _source_field(hit)
    return evidence


def _source_field(hit: Dict[str, Any]) -> str:
    source = str(hit.get("source") or "")
    return {
        "github": "repositories.search.items[*]",
        "huggingface": "api/models[*]",
        "pypi": "pypi/<name>/json.info",
        "npm": "registry/-/v1/search + /<name>/latest",
        "arxiv": "api/query atom entry",
    }.get(source, "unknown")


def strength(hit: Dict[str, Any]) -> float:
    """0..1: how much independent evidence the hit actually carries."""
    has_desc = bool(str(hit.get("description") or "").strip())
    has_version = bool(hit.get("version"))
    has_popularity = hit.get("stars") is not None or hit.get("downloads") is not None
    score = 0.55 + (0.15 if has_desc else 0) + (0.15 if has_version else 0) \
        + (0.15 if has_popularity else 0)
    return round(min(1.0, score), 3)


def summarise(evidence: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("stars", "downloads", "version", "pipeline_tag", "published_at"):
        if key in evidence:
            parts.append(f"{key}={evidence[key]}")
    if evidence.get("description"):
        parts.append(f'"{evidence["description"][:120]}"')
    return "; ".join(parts[:4]) or "name only"


def merge(*dicts: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in dicts:
        out.update(item or {})
    return out
