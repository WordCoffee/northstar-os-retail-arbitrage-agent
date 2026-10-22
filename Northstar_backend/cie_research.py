"""Research step: turn an observed gap into a candidate atom.

Research here is *retrieval from a curated source corpus*, not free-form
generation. That keeps every candidate traceable to a snippet, and lets the
loop run offline and deterministically. A later online fetcher can append to the
same corpus; the contract (do / dont / why / source) does not change.

Sources live in ``knowledge/sources/<domain>.jsonl``:
  {"id","title","source","url","do","dont","why","effective_date"}
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from knowledge_pack import all_atoms, score_atom, validate_atom

_REPO = Path(__file__).resolve().parent.parent


def root() -> Path:
    return Path(os.environ.get("NORTHSTAR_CIE_ROOT") or _REPO)


def sources_dir() -> Path:
    return root() / "knowledge" / "sources"


def load_snippets(domain: str) -> List[Dict[str, Any]]:
    """All corpus entries for one domain, from every *.jsonl in sources/."""
    out: List[Dict[str, Any]] = []
    directory = sources_dir()
    if not directory.exists():
        return out
    for path in sorted(directory.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and str(row.get("domain") or "") == domain:
                    out.append(row)
    return out


def _slug(text: str, limit: int = 44) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:limit] or "atom"


def _overlap(query: str, snippet: Dict[str, Any]) -> float:
    probe = {"id": snippet.get("title", ""), "do": snippet.get("do", ""),
             "dont": snippet.get("dont", ""), "why": snippet.get("why", ""),
             "tags": []}
    return score_atom(query, probe)


def best_snippet(gap: str, domain: str,
                 atom_id: Optional[str] = None) -> Optional[Tuple[float, Dict[str, Any]]]:
    snips = load_snippets(domain)
    if atom_id:
        exact = next((s for s in snips if str(s.get("id")) == atom_id), None)
        if exact is not None:
            return 1.0, exact
    scored = [(_overlap(gap, s), s) for s in snips]
    scored = [pair for pair in scored if pair[0] > 0]
    if not scored:
        return None
    scored.sort(key=lambda p: p[0], reverse=True)
    return scored[0]


def candidate_atom(gap: str, domain: str,
                   atom_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Build a candidate atom from the best matching snippet, or None."""
    found = best_snippet(gap, domain, atom_id)
    if not found:
        return None
    score, snip = found
    if score < 0.25:
        return None
    atom_id = atom_id or f"{domain}.auto.{_slug(gap)}"
    return {
        "id": atom_id,
        "domain": domain,
        "applies_to": snip.get("applies_to") or ["pl", "reseller"],
        "do": snip.get("do") or "",
        "dont": snip.get("dont") or "",
        "why": snip.get("why") or "",
        "source": snip.get("source") or snip.get("title") or "curated source",
        "source_kind": "curated_snippet",
        "effective_date": snip.get("effective_date") or "unknown",
        "last_verified": "unverified",
        "confidence": snip.get("confidence") or "medium",
        "needs_verification": True,
        "tags": [domain, "auto"],
        "_research": {"gap": gap, "snippet": snip.get("id"), "match": score},
    }


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 3}


def similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    ta = _tokens(f"{a.get('do','')} {a.get('dont','')}")
    tb = _tokens(f"{b.get('do','')} {b.get('dont','')}")
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 4)


def review(candidate: Dict[str, Any], existing: Iterable[Dict[str, Any]],
           *, dup_threshold: float = 0.85) -> Dict[str, Any]:
    """Lint + dedupe a candidate. Returns {ok, reasons, duplicate_of}."""
    reasons = validate_atom(candidate)
    duplicate_of = None
    for atom in existing:
        if atom.get("id") == candidate.get("id"):
            reasons.append(f"id already exists: {candidate['id']}")
            continue
        sim = similarity(candidate, atom)
        if sim >= dup_threshold:
            duplicate_of = atom.get("id")
            reasons.append(f"near-duplicate of {atom.get('id')} ({sim})")
            break
    return {"ok": not reasons, "reasons": reasons, "duplicate_of": duplicate_of}


def corpus_stats() -> Dict[str, int]:
    out: Dict[str, int] = {}
    for path in sorted(sources_dir().glob("*.jsonl")):
        try:
            out[path.stem] = sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                                 if line.strip())
        except OSError:
            out[path.stem] = 0
    return out
