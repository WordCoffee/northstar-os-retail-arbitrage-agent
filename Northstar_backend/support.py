"""Internal support queue (Phase F/S8, local only).

List / status / assign backed by the local SQLite DB. No real ticketing
integration (no network). Tickets are operator-visible; body text is treated
as internal (no PII policy enforced beyond email hiding).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data_layer import get_db

STATUSES = ("open", "in_progress", "resolved")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_table(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            assigned_to TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.commit()


def _db():
    db = get_db()
    _ensure_table(db)
    return db


def create_ticket(account_id: str, subject: str, body: str) -> Dict[str, Any]:
    if not subject or not str(subject).strip():
        raise ValueError("subject is required")
    tid = "tkt_" + secrets.token_hex(16)
    db = _db()
    db.execute(
        "INSERT INTO support_tickets (id, account_id, subject, body) VALUES (?, ?, ?, ?)",
        (tid, account_id, str(subject).strip(), str(body or "").strip()),
    )
    db.commit()
    return get_ticket(tid)


def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    db = _db()
    row = db.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
    return dict(row) if row else None


def list_tickets(status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = _db()
    if status:
        cur = db.execute(
            "SELECT * FROM support_tickets WHERE status = ? ORDER BY created_at DESC", (status,)
        )
    else:
        cur = db.execute("SELECT * FROM support_tickets ORDER BY created_at DESC")
    return [dict(r) for r in cur.fetchall()]


def set_status(ticket_id: str, status: str) -> Dict[str, Any]:
    if status not in STATUSES:
        raise ValueError("invalid status: %r" % (status,))
    db = _db()
    cur = db.execute("SELECT id FROM support_tickets WHERE id = ?", (ticket_id,))
    if cur.fetchone() is None:
        raise KeyError("unknown ticket")
    db.execute("UPDATE support_tickets SET status = ?, updated_at = ? WHERE id = ?",
               (status, _now(), ticket_id))
    db.commit()
    return get_ticket(ticket_id)


def assign(ticket_id: str, operator: str) -> Dict[str, Any]:
    db = _db()
    cur = db.execute("SELECT id FROM support_tickets WHERE id = ?", (ticket_id,))
    if cur.fetchone() is None:
        raise KeyError("unknown ticket")
    db.execute("UPDATE support_tickets SET assigned_to = ?, updated_at = ? WHERE id = ?",
               (operator or None, _now(), ticket_id))
    db.commit()
    return get_ticket(ticket_id)