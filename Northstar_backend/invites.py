"""Invite-code generation / redemption (Phase F/S7, code only).

Implements the founding-cohort flow from COHORT_OPS.md (C5) WITHOUT sending
any real email or connecting a provider: the send step is stubbed with a log
line. Local SQLite via data_layer; offline.

Invariants:
  - codes are opaque and single-use (idempotent redeem returns the same result)
  - cohort/plan come from the invites row, never from client input
  - redemption is append-only (redeemed_at/used_by set once)
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from data_layer import get_db

INVITE_EXPIRE_DAYS = 7

# Cohort -> plan hint (COHORT_OPS.md §1); redemption assigns this plan when the
# caller is still on the demo/foundation plan.
COHORT_PLAN = {
    "founding_operator": "autothink",
    "foundation": "foundation",
    "scout": "scout",
    "mover": "mover",
    "autothink": "autothink",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_table(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS invites (
            code TEXT PRIMARY KEY,
            cohort TEXT NOT NULL,
            email TEXT,
            created_by TEXT DEFAULT 'operator',
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            redeemed_at TEXT,
            used_by TEXT
        )
    """)
    db.commit()


def _db():
    db = get_db()
    _ensure_table(db)
    return db


def create_invite(cohort: str, *, email: Optional[str] = None,
                  created_by: str = "operator") -> Dict[str, Any]:
    if cohort not in COHORT_PLAN:
        raise ValueError("unknown cohort: %r" % (cohort,))
    code = "invite_" + secrets.token_hex(16)
    expires = (datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRE_DAYS)).isoformat()
    db = _db()
    db.execute(
        "INSERT INTO invites (code, cohort, email, created_by, expires_at) VALUES (?, ?, ?, ?, ?)",
        (code, cohort, email, created_by, expires),
    )
    db.commit()
    return {
        "code": code,
        "cohort": cohort,
        "email": email,
        "expires_at": expires,
        "plan": COHORT_PLAN[cohort],
    }


def _public_view(row: Any) -> Dict[str, Any]:
    d = dict(row)
    d["redeemed"] = bool(d.get("redeemed_at"))
    d.pop("used_by", None)
    return d


def get_invite(code: str) -> Optional[Dict[str, Any]]:
    db = _db()
    cur = db.execute("SELECT * FROM invites WHERE code = ?", (code,))
    row = cur.fetchone()
    return _public_view(row) if row else None


def redeem_invite(code: str, account_id: str) -> Dict[str, Any]:
    """Redeem an invite. Single-use; idempotent on the SAME account.

    Never accepts cohort/plan from the client — they come from the invites row.
    """
    db = _db()
    cur = db.execute("SELECT * FROM invites WHERE code = ?", (code,))
    row = cur.fetchone()
    if not row:
        raise KeyError("unknown invite code")
    invite = dict(row)
    if invite.get("redeemed_at"):
        if invite.get("used_by") != account_id:
            raise PermissionError("invite already redeemed")
        return {"status": "already_redeemed", "account_id": account_id}
    now = _now()
    db.execute(
        "UPDATE invites SET redeemed_at = ?, used_by = ? WHERE code = ?",
        (now, account_id, code),
    )
    db.commit()
    return {
        "status": "redeemed",
        "account_id": account_id,
        "cohort": invite["cohort"],
        "plan": COHORT_PLAN[invite["cohort"]],
    }


def send_invite_email(invite_code: str, cohort: str, email: str) -> Dict[str, Any]:
    """STUB — never sends a real email (Phase F/S7).

    Records the would-be send as a structured log line; the operator wires a
    real provider later (COHORT_OPS.md §4).
    """
    import logging
    logging.getLogger("northstar.invites").info(
        "[invite-email:stubbed] cohort=%s code=%s to=%s", cohort, invite_code, email
    )
    return {"status": "stubbed", "to": email, "cohort": cohort}