"""Knowledge packs — do/don't atoms for Amazon selling domains.

An atom is the smallest verifiable piece of selling knowledge. It always carries
a paired *do* and *don't*, a reason, a source, a date and a confidence, because
"what not to do" is the part sellers actually need.

Layout:
  knowledge/domains.json
  knowledge/<domain>/atoms.json   (list of atoms)
  knowledge/<domain>/pack.json    (version + hash, written on promotion)

Nothing here calls a model or the network. Retrieval is deterministic keyword
overlap so every score can be reproduced.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

CONFIDENCE = ("high", "medium", "low")
APPLIES_TO = {"pl", "reseller", "both"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,80}$")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is",
    "are", "be", "do", "does", "not", "your", "you", "it", "this", "that",
    "how", "what", "why", "when", "should", "can", "will", "at", "by", "from",
}


def root() -> Path:
    return Path(os.environ.get("NORTHSTAR_CIE_ROOT") or REPO_ROOT)


def knowledge_dir() -> Path:
    return root() / "knowledge"


def domains() -> List[str]:
    path = knowledge_dir() / "domains.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [d["id"] for d in data.get("domains", [])]


def domain_meta() -> List[Dict[str, Any]]:
    path = knowledge_dir() / "domains.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("domains", [])


def atoms_path(domain: str) -> Path:
    return knowledge_dir() / domain / "atoms.json"


def pack_path(domain: str) -> Path:
    return knowledge_dir() / domain / "pack.json"


def load_atoms(domain: str) -> List[Dict[str, Any]]:
    path = atoms_path(domain)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def save_atoms(domain: str, atoms: List[Dict[str, Any]]) -> None:
    path = atoms_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(atoms, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def all_atoms() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in domains():
        out.extend(load_atoms(d))
    return out


REQUIRED = ("id", "domain", "applies_to", "do", "dont", "why", "source",
            "source_kind", "effective_date", "last_verified", "confidence")


def validate_atom(atom: Dict[str, Any], *, known_domains: Optional[Iterable[str]] = None) -> List[str]:
    """Return a list of problems. Empty means the atom is valid."""
    errors: List[str] = []
    if not isinstance(atom, dict):
        return ["atom is not an object"]
    for key in REQUIRED:
        if key not in atom or atom[key] in (None, "", []):
            errors.append(f"missing {key}")
    aid = str(atom.get("id") or "")
    if aid and not _ID_RE.match(aid):
        errors.append("id must match ^[a-z0-9][a-z0-9_.-]{2,80}$")
    known = set(known_domains or domains())
    if atom.get("domain") and known and atom["domain"] not in known:
        errors.append(f"unknown domain: {atom['domain']}")
    applies = atom.get("applies_to")
    if isinstance(applies, str):
        applies = [applies]
    if applies and not set(applies) <= APPLIES_TO:
        errors.append("applies_to must be a subset of pl/reseller/both")
    if atom.get("confidence") and atom["confidence"] not in CONFIDENCE:
        errors.append("confidence must be high|medium|low")
    for key in ("do", "dont", "why"):
        text = str(atom.get(key) or "")
        if text and len(text) < 12:
            errors.append(f"{key} is too short to be useful")
    return errors


def content_key(atom: Dict[str, Any]) -> str:
    parts = [str(atom.get(k) or "") for k in
             ("id", "do", "dont", "why", "source", "effective_date", "confidence")]
    return "|".join(parts)


def pack_version(domain: str) -> str:
    atoms = load_atoms(domain)
    h = hashlib.sha256()
    for atom in sorted(atoms, key=lambda a: str(a.get("id"))):
        h.update(content_key(atom).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def pack_versions() -> Dict[str, str]:
    return {d: pack_version(d) for d in domains()}


def write_pack_meta(domain: str) -> Dict[str, Any]:
    meta = {
        "domain": domain,
        "version": pack_version(domain),
        "atoms": len(load_atoms(domain)),
        "updated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path = pack_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


# ── retrieval ───────────────────────────────────────────────────────────────

def _tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if len(w) > 2 and w not in _STOP]


def score_atom(query: str, atom: Dict[str, Any]) -> float:
    """Deterministic relevance: token overlap weighted by field importance."""
    q = set(_tokens(query))
    if not q:
        return 0.0
    fields = (
        (str(atom.get("id") or "").replace(".", " "), 1.0),
        (str(atom.get("do") or ""), 1.0),
        (str(atom.get("dont") or ""), 1.0),
        (str(atom.get("why") or ""), 0.5),
        (" ".join(atom.get("tags") or []), 1.5),
    )
    best = 0.0
    for text, weight in fields:
        t = set(_tokens(text))
        if not t:
            continue
        overlap = len(q & t) / (len(q) ** 0.5)
        best = max(best, overlap * weight)
    return round(best, 4)


def retrieve(query: str, domain: Optional[str] = None, limit: int = 8,
             min_score: float = 0.0) -> List[Tuple[float, Dict[str, Any]]]:
    pool: List[Dict[str, Any]] = []
    if domain:
        pool = load_atoms(domain)
    else:
        pool = all_atoms()
    scored = [(score_atom(query, a), a) for a in pool]
    scored = [s for s in scored if s[0] > min_score]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:max(0, int(limit))]


def coverage(query: str, domain: Optional[str] = None, threshold: float = 0.35) -> bool:
    hits = retrieve(query, domain, limit=1)
    return bool(hits) and hits[0][0] >= threshold


def format_for_prompt(atoms: Iterable[Dict[str, Any]], limit: int = 10) -> str:
    lines: List[str] = []
    for atom in list(atoms)[:limit]:
        lines.append(
            f"- {atom['id']} (source: {atom.get('source')}, eff. {atom.get('effective_date')})\n"
            f"  DO: {atom['do']}\n  DON'T: {atom['dont']}")
    if not lines:
        return ""
    return "Amazon selling rules that apply here:\n" + "\n".join(lines)


def stats(error: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {"domains": {}, "total": 0}
    for d in domains():
        atoms = load_atoms(d)
        bad = sum(1 for a in atoms if validate_atom(a))
        out["domains"][d] = {"atoms": len(atoms), "invalid": bad,
                             "version": pack_version(d)}
        out["total"] += len(atoms)
    return out
