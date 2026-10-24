"""AutothinK Memory Bank — per-account learning and knowledge store.

Ingests facts, preferences, experiences, and AI-derived learnings
from text/images/voice. Retrieves by intent at generation time.
Supports revisions and unlearning. All local, all free.

Memory types:
- preference: User preferences (brand voice, pricing strategy, etc.)
- fact: Verified facts about products, suppliers, competitors
- experience: Past decisions and outcomes (bought X, sold Y, lost Z)
- learning: AI-derived insights (this keyword converts better, etc.)
- brand_voice: Brand tone and style guidelines
- workflow: Automated workflow patterns
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _db():
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from data_layer import get_db
    return get_db()


def ingest(
    content: str,
    entry_type: str = "fact",
    account_id: str = "default",
    source: str = "chat",
    confidence: float = 0.8,
    tags: Optional[List[str]] = None,
    provenance: Optional[Dict] = None,
) -> str:
    """Add a memory entry. Returns the entry ID."""
    db = _db()
    eid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        """INSERT INTO memory_entries
           (id, account_id, entry_type, content, source, confidence, tags, provenance, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            eid, account_id, entry_type, content, source, confidence,
            json.dumps(tags) if tags else None,
            json.dumps(provenance) if provenance else None,
            now, now,
        ),
    )
    db.commit()
    return eid


def search(
    intent: str,
    account_id: str = "default",
    entry_type: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search memory entries by intent (keyword match)."""
    db = _db()
    sql = "SELECT * FROM memory_entries WHERE account_id = ? AND retired_at IS NULL AND content LIKE ?"
    params = [account_id, f"%{intent}%"]

    if entry_type:
        sql += " AND entry_type = ?"
        params.append(entry_type)

    sql += " ORDER BY confidence DESC, created_at DESC LIMIT ?"
    params.append(limit)

    cur = db.execute(sql, tuple(params))
    return [_deserialize(row) for row in cur.fetchall()]


def retrieve_context(
    intent: str,
    account_id: str = "default",
    max_tokens: int = 500,
) -> str:
    """Retrieve relevant memory as context string for LLM generation.

    Returns a formatted string of relevant memories that can be injected
    into LLM prompts as context.
    """
    entries = search(intent, account_id=account_id, limit=5)
    if not entries:
        return ""

    lines = ["[Memory Bank — relevant context:]"]
    for entry in entries:
        lines.append(f"- [{entry['entry_type']}] {entry['content']}")
    return "\n".join(lines)


def update(
    eid: str,
    content: Optional[str] = None,
    confidence: Optional[float] = None,
    tags: Optional[List[str]] = None,
) -> bool:
    """Update a memory entry."""
    db = _db()
    now = datetime.now(timezone.utc).isoformat()
    updates = ["updated_at = ?"]
    params = [now]

    if content is not None:
        updates.append("content = ?")
        params.append(content)
    if confidence is not None:
        updates.append("confidence = ?")
        params.append(confidence)
    if tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(tags))

    params.append(eid)
    db.execute(f"UPDATE memory_entries SET {', '.join(updates)} WHERE id = ?", tuple(params))
    db.commit()
    return True


def retire(eid: str) -> bool:
    """Retire (unlearn) a memory entry."""
    db = _db()
    now = datetime.now(timezone.utc).isoformat()
    cur = db.execute("UPDATE memory_entries SET retired_at = ? WHERE id = ?", (now, eid))
    db.commit()
    return cur.rowcount > 0


# --- Revision gate (AgentConnect organisation-knowledge pattern) ------------
# An AI turn never rewrites an approved memory silently. It proposes a
# revision; retrieval keeps serving the approved content until the operator
# approves. This is the same trust shape as organisation Knowledge and
# Chrome-Connect lessons: agent output stays PROPOSED until a human blesses it.

REV_PENDING = "proposed"
REV_APPROVED = "approved"
REV_REJECTED = "rejected"


def _ensure_revisions(db) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS memory_revisions (
               id TEXT PRIMARY KEY,
               entry_id TEXT NOT NULL,
               proposed_content TEXT,
               proposed_confidence REAL,
               proposed_tags TEXT,
               note TEXT,
               proposed_by TEXT NOT NULL,
               proposed_at TEXT NOT NULL,
               status TEXT NOT NULL,
               reviewed_at TEXT,
               reviewed_by TEXT,
               review_note TEXT
           )"""
    )


def _revision_row_to_dict(row) -> Dict[str, Any]:
    d = dict(row)
    if d.get("proposed_tags"):
        try:
            d["proposed_tags"] = json.loads(d["proposed_tags"])
        except Exception:  # noqa: BLE001 - corrupt tags must not break retrieval
            pass
    return d


def propose_revision(
    eid: str,
    content: Optional[str] = None,
    confidence: Optional[float] = None,
    tags: Optional[List[str]] = None,
    proposed_by: str = "agent",
    note: Optional[str] = None,
) -> str:
    """Propose a change to an approved memory. The entry itself is untouched."""
    db = _db()
    _ensure_revisions(db)
    rid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO memory_revisions
           (id, entry_id, proposed_content, proposed_confidence, proposed_tags,
            note, proposed_by, proposed_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rid, eid, content, confidence,
         json.dumps(tags) if tags is not None else None,
         note, proposed_by, now, REV_PENDING),
    )
    db.commit()
    return rid


def pending_revisions(entry_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Unapproved agent proposals, oldest first; retrieval never reads these."""
    db = _db()
    _ensure_revisions(db)
    if entry_id:
        cur = db.execute(
            "SELECT * FROM memory_revisions WHERE status = ? AND entry_id = ? "
            "ORDER BY proposed_at", (REV_PENDING, entry_id))
    else:
        cur = db.execute(
            "SELECT * FROM memory_revisions WHERE status = ? ORDER BY proposed_at",
            (REV_PENDING,))
    return [_revision_row_to_dict(row) for row in cur.fetchall()]


def _apply_revision_values(db, rev: Dict[str, Any]) -> None:
    sets: List[str] = ["updated_at = ?"]
    params: List[Any] = [datetime.now(timezone.utc).isoformat()]
    if rev.get("proposed_content") is not None:
        sets.append("content = ?")
        params.append(rev["proposed_content"])
    if rev.get("proposed_confidence") is not None:
        sets.append("confidence = ?")
        params.append(rev["proposed_confidence"])
    if rev.get("proposed_tags") is not None:
        sets.append("tags = ?")
        params.append(json.dumps(rev["proposed_tags"]))
    params.append(rev["entry_id"])
    db.execute(f"UPDATE memory_entries SET {', '.join(sets)} WHERE id = ?", tuple(params))


def approve_revision(rev_id: str, reviewer: str = "operator") -> Dict[str, Any]:
    """Operator blessing: apply the proposed values to the approved entry."""
    db = _db()
    _ensure_revisions(db)
    cur = db.execute("SELECT * FROM memory_revisions WHERE id = ?", (rev_id,))
    row = cur.fetchone()
    if row is None:
        return {"approved": False, "reason": "no such revision"}
    rev = _revision_row_to_dict(row)
    if rev["status"] != REV_PENDING:
        return {"approved": False, "reason": f"already {rev['status']}"}
    now = datetime.now(timezone.utc).isoformat()
    _apply_revision_values(db, rev)
    db.execute(
        "UPDATE memory_revisions SET status = ?, reviewed_at = ?, reviewed_by = ? WHERE id = ?",
        (REV_APPROVED, now, reviewer, rev_id),
    )
    db.commit()
    return {"approved": True, "entry_id": rev["entry_id"]}


def reject_revision(rev_id: str, note: str, reviewer: str = "operator") -> Dict[str, Any]:
    """Operator refusal: the approved content stays exactly as it was."""
    db = _db()
    _ensure_revisions(db)
    cur = db.execute(
        "UPDATE memory_revisions SET status = ?, reviewed_at = ?, reviewed_by = ?, "
        "review_note = ? WHERE id = ? AND status = ?",
        (REV_REJECTED, datetime.now(timezone.utc).isoformat(), reviewer,
         note[:200], rev_id, REV_PENDING),
    )
    db.commit()
    return {"rejected": cur.rowcount > 0,
            "reason": None if cur.rowcount else "no pending revision with that id"}


def list_by_type(
    entry_type: str,
    account_id: str = "default",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List memory entries by type."""
    db = _db()
    cur = db.execute(
        "SELECT * FROM memory_entries WHERE account_id = ? AND entry_type = ? AND retired_at IS NULL ORDER BY created_at DESC LIMIT ?",
        (account_id, entry_type, limit),
    )
    return [_deserialize(row) for row in cur.fetchall()]


def stats(account_id: str = "default") -> Dict[str, Any]:
    """Memory bank statistics."""
    db = _db()
    cur = db.execute(
        "SELECT entry_type, COUNT(*) as cnt FROM memory_entries WHERE account_id = ? AND retired_at IS NULL GROUP BY entry_type",
        (account_id,),
    )
    by_type = {row["entry_type"]: row["cnt"] for row in cur.fetchall()}
    total = sum(by_type.values())

    cur = db.execute(
        "SELECT COUNT(*) as cnt FROM memory_entries WHERE account_id = ? AND retired_at IS NOT NULL",
        (account_id,),
    )
    retired = cur.fetchone()["cnt"]

    return {
        "total_active": total,
        "total_retired": retired,
        "by_type": by_type,
        "account_id": account_id,
    }


def detect_patterns(account_id: str = "default") -> List[Dict[str, Any]]:
    """Detect patterns in memory that could trigger proactive suggestions.

    Looks for:
    - Repeated decisions (consistency signals)
    - High-confidence learnings that could inform new actions
    - Preference clusters
    """
    db = _db()
    patterns = []

    # Find high-confidence learnings
    cur = db.execute(
        """SELECT content, COUNT(*) as cnt FROM memory_entries
           WHERE account_id = ? AND entry_type = 'learning' AND retired_at IS NULL
           GROUP BY content HAVING cnt > 1""",
        (account_id,),
    )
    for row in cur.fetchall():
        patterns.append({
            "type": "repeated_learning",
            "content": row["content"],
            "occurrence_count": row["cnt"],
            "suggestion": f"Consider automating: {row['content'][:100]}",
        })

    # Find preference clusters
    cur = db.execute(
        """SELECT content FROM memory_entries
           WHERE account_id = ? AND entry_type = 'preference' AND retired_at IS NULL
           ORDER BY created_at DESC LIMIT 10""",
        (account_id,),
    )
    preferences = [row["content"] for row in cur.fetchall()]
    if len(preferences) >= 3:
        patterns.append({
            "type": "preference_cluster",
            "count": len(preferences),
            "suggestion": "Multiple preferences detected — consider creating a brand voice profile",
        })

    return patterns


def _deserialize(row) -> Dict[str, Any]:
    """Deserialize a database row."""
    result = dict(row)
    if result.get("tags") and isinstance(result["tags"], str):
        try:
            result["tags"] = json.loads(result["tags"])
        except (json.JSONDecodeError, ValueError):
            pass
    if result.get("provenance") and isinstance(result["provenance"], str):
        try:
            result["provenance"] = json.loads(result["provenance"])
        except (json.JSONDecodeError, ValueError):
            pass
    return result
