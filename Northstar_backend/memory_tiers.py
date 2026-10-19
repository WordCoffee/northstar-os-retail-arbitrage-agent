"""Memory & knowledge vault separation (Thorn v5.0 §Secure Knowledge Isolation).

This EXTENDS the existing memory bank (`memory_bank.py` / the `memory_entries`
table) with the tier model the plan asks for. It does not create a second store
and it does not change the schema: the tier rides in the entry's `tags` as
`tier:<name>`, so every existing reader keeps working.

    transient   session buffer — flushed on session end
    project     the normal, account-scoped memory rows
    global      sanitised lessons promoted from project rows

Encryption boundary, stated honestly
------------------------------------
The plan calls this a "cryptographically isolated, encrypted" vault. **It is not.**
What exists in this repository is AES-256-GCM for *secrets* with the key held
outside the repo (`foundation/secrets.py`). Knowledge rows are plain SQLite.
`encryption_status()` reports exactly that, and encrypting the knowledge store is
owner decision D3 rather than a guarantee this module pretends to provide.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import memory_bank

TIER_TAG_PREFIX = "tier:"
TIERS = ("transient", "project", "global")
DEFAULT_TIER = "project"

_URL = re.compile(r"https?://\S+")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
_LONGNUM = re.compile(r"(?<!\d)\d{4,}(?!\d)")
_QUOTED = re.compile(r"[\"'“”][^\"'“”]{3,}[\"'“”]")
_WINPATH = re.compile(r"[A-Za-z]:\\[^\s\"']{3,}")


# ── tag helpers ──────────────────────────────────────────────────────────────

def _tags_of(entry: Dict[str, Any]) -> List[str]:
    tags = entry.get("tags")
    if isinstance(tags, list):
        return [str(t) for t in tags]
    if isinstance(tags, str) and tags.strip():
        try:
            import json
            parsed = json.loads(tags)
            return [str(t) for t in parsed] if isinstance(parsed, list) else [tags]
        except Exception:  # noqa: BLE001
            return [tags]
    return []


def tier_of(entry: Dict[str, Any]) -> str:
    for tag in _tags_of(entry):
        if tag.startswith(TIER_TAG_PREFIX):
            name = tag[len(TIER_TAG_PREFIX):]
            if name in TIERS:
                return name
    return DEFAULT_TIER


def _tier_tags(tier: str, session_id: Optional[str] = None) -> List[str]:
    tags = [f"{TIER_TAG_PREFIX}{tier}"]
    if tier == "transient" and session_id:
        tags.append(f"session:{session_id}")
    return tags


# ── writing ──────────────────────────────────────────────────────────────────

def remember(content: str, *, tier: str = DEFAULT_TIER, account_id: str = "default",
             entry_type: str = "fact", source: str = "chat", confidence: float = 0.8,
             session_id: Optional[str] = None,
             provenance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Store one memory row in an explicit tier."""
    if tier not in TIERS:
        return {"ok": False, "error": f"unknown tier {tier!r}", "known": list(TIERS)}
    if not (content or "").strip():
        return {"ok": False, "error": "refusing to store an empty memory"}
    if tier == "transient" and not session_id:
        return {"ok": False, "error": "a transient memory needs a session_id so it can be flushed"}
    if tier == "global":
        return {"ok": False,
                "error": "global lessons are created by promote_to_global(), not written directly"}

    prov = dict(provenance or {})
    prov["tier"] = tier
    if session_id:
        prov["session_id"] = session_id
    eid = memory_bank.ingest(content.strip(), entry_type=entry_type, account_id=account_id,
                             source=source, confidence=confidence,
                             tags=_tier_tags(tier, session_id), provenance=prov)
    return {"ok": True, "id": eid, "tier": tier}


def promote_to_global(entry_id: str, *, account_id: str = "default") -> Dict[str, Any]:
    """Copy a project row into the global tier as a SANITISED lesson.

    Concrete identifiers (URLs, emails, long digit runs, quoted strings, file
    paths) are stripped: the global tier is for the lesson, not the evidence.
    The project row is left untouched.
    """
    db = memory_bank._db()
    cur = db.execute("SELECT * FROM memory_entries WHERE id = ? AND retired_at IS NULL",
                     (entry_id,))
    row = cur.fetchone()
    if row is None:
        return {"ok": False, "error": "no active memory entry with that id"}
    entry = memory_bank._deserialize(row)
    if entry.get("account_id") != account_id:
        return {"ok": False, "error": "entry belongs to a different account"}

    raw = str(entry.get("content") or "")
    clean, counts = _sanitise(raw)
    # A length check is not enough: "[url] [number] [email]" is 21 characters and
    # contains no lesson at all. Count the meaningful words that survive.
    words = re.findall(r"[A-Za-z]{3,}",
                       re.sub(r"\[(?:url|email|path|number|quote)\]", " ", clean))
    if len(words) < 4:
        return {"ok": False,
                "error": (f"after stripping identifiers only {len(words)} meaningful word(s) "
                          "remain — too little remains to be a lesson"),
                "stripped": counts,
                "remaining": clean}

    new_id = memory_bank.ingest(
        clean, entry_type="learning", account_id=account_id, source="promotion",
        confidence=float(entry.get("confidence") or 0.8),
        tags=[f"{TIER_TAG_PREFIX}global"],
        provenance={"tier": "global", "promoted_from": entry_id,
                    "stripped": counts},
    )
    return {"ok": True, "id": new_id, "tier": "global", "stripped": counts,
            "content": clean}


def _sanitise(text: str) -> tuple:
    counts: Dict[str, int] = {}
    out = text
    for name, pattern, token in (
        ("url", _URL, "[url]"),
        ("email", _EMAIL, "[email]"),
        ("path", _WINPATH, "[path]"),
        ("long_number", _LONGNUM, "[number]"),
        ("quoted", _QUOTED, "[quote]"),
    ):
        out, n = pattern.subn(token, out)
        if n:
            counts[name] = n
    return re.sub(r"\s{2,}", " ", out).strip(), counts


# ── reading ──────────────────────────────────────────────────────────────────

def list_tier(tier: str, *, account_id: str = "default", limit: int = 50) -> List[Dict[str, Any]]:
    rows = memory_bank.search("", account_id=account_id, limit=max(limit * 4, 200))
    hits = [r for r in rows if tier_of(r) == tier]
    return hits[:limit]


def tiers(account_id: str = "default") -> Dict[str, Any]:
    db = memory_bank._db()
    cur = db.execute(
        "SELECT tags FROM memory_entries WHERE account_id = ? AND retired_at IS NULL",
        (account_id,))
    counts = {t: 0 for t in TIERS}
    for row in cur.fetchall():
        counts[tier_of(memory_bank._deserialize(row))] += 1
    return {
        "account_id": account_id,
        "counts": counts,
        "total": sum(counts.values()),
        "boundary": encryption_status(),
    }


def flush_transient(account_id: str = "default", session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retire the transient buffer. Called at session end."""
    rows = list_tier("transient", account_id=account_id, limit=500)
    if session_id:
        rows = [r for r in rows if f"session:{session_id}" in _tags_of(r)]
    retired = 0
    for r in rows:
        if memory_bank.retire(r["id"]):
            retired += 1
    return {"ok": True, "retired": retired, "session_id": session_id}


def encryption_status() -> Dict[str, Any]:
    """What is actually encrypted in this repository, and what is not."""
    return {
        "knowledge_store_encrypted": False,
        "storage": "plain SQLite (memory_entries)",
        "encrypted_elsewhere": {
            "what": "provider credentials / staging secrets",
            "how": "AES-256-GCM, key held outside the repository",
            "module": "foundation/secrets.py",
        },
        "gap": ("The plan describes an encrypted knowledge vault. Knowledge rows are "
                "NOT encrypted. Doing so is owner decision D3 (key management), not a "
                "property this module can assert."),
        "mitigations_in_place": [
            "global-tier promotion strips identifiers instead of copying them",
            "transient rows are retired at session end",
            "memory is account-scoped and retired rows are excluded from reads",
        ],
    }
