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
