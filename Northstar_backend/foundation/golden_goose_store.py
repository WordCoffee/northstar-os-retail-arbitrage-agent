"""Golden Goose persistence (enables P5-T3 snapshots / P5-T4 round-trip).

Additive, org-scoped store for Golden Goose items and decisions. Never makes a
score authorize a purchase; ``purchase_ready`` is stored only as computed by the
gate/approval logic (SAMPLE can never be True).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

TABLE_ITEMS = "golden_goose_items"
TABLE_DECISIONS = "golden_goose_decisions"

_DDL_PG = [
    "CREATE TABLE IF NOT EXISTS golden_goose_items (item_id TEXT PRIMARY KEY, organization_id TEXT,"
    " category TEXT, match_state TEXT, resale_score DOUBLE PRECISION, net_per_unit DOUBLE PRECISION,"
    " economics_complete INTEGER, policy_exclusion_flag INTEGER, payload_json TEXT NOT NULL DEFAULT '{}',"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now())",
    "CREATE TABLE IF NOT EXISTS golden_goose_decisions (decision_id TEXT PRIMARY KEY, item_id TEXT NOT NULL,"
    " organization_id TEXT, decision_state TEXT NOT NULL, purchase_ready INTEGER NOT NULL DEFAULT 0,"
    " scorer_version TEXT, inputs_hash TEXT, payload_json TEXT NOT NULL DEFAULT '{}',"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
]
_DDL_SQLITE = [s.replace("TIMESTAMPTZ NOT NULL DEFAULT now()", "TEXT NOT NULL")
               .replace("DOUBLE PRECISION", "REAL") for s in _DDL_PG]


def _pg(db) -> bool:
    return getattr(db, "backend", "sqlite") == "postgresql"


def ensure_tables(db) -> None:
    for s in (_DDL_PG if _pg(db) else _DDL_SQLITE):
        if _pg(db):
            db._raw.execute(s)
        else:
            db.conn.execute(s)
    if _pg(db):
        db._raw.commit()
    else:
        db.conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_item(db, organization_id: str, item: dict) -> dict:
    ensure_tables(db)
    item_id = str(item.get("item_id") or "").strip()
    if not item_id:
        raise ValueError("item_id required")
    row = {
        "item_id": item_id, "organization_id": organization_id,
        "category": item.get("category"), "match_state": item.get("match_state"),
        "resale_score": item.get("resale_score"), "net_per_unit": item.get("net_per_unit"),
        "economics_complete": 1 if item.get("economics_complete") else 0,
        "policy_exclusion_flag": int(item.get("policy_exclusion_flag") or 0),
        "payload_json": json.dumps(item, default=str), "created_at": _now(), "updated_at": _now(),
    }
    if db.get(TABLE_ITEMS, {"item_id": item_id}) is None:
        db.insert_ignore(TABLE_ITEMS, row, conflict_cols=("item_id",))
    else:
        db.conn.execute(
            "UPDATE golden_goose_items SET organization_id=?, category=?, match_state=?, resale_score=?,"
            " net_per_unit=?, economics_complete=?, policy_exclusion_flag=?, payload_json=?, updated_at=?"
            " WHERE item_id=?",
            (row["organization_id"], row["category"], row["match_state"], row["resale_score"],
             row["net_per_unit"], row["economics_complete"], row["policy_exclusion_flag"],
             row["payload_json"], row["updated_at"], item_id))
        db.conn.commit()
    return get_item(db, organization_id, item_id)


def get_item(db, organization_id: str, item_id: str) -> Optional[dict]:
    ensure_tables(db)
    row = db.get(TABLE_ITEMS, {"item_id": item_id})
    if row is None or (row.get("organization_id") or "") != (organization_id or ""):
        return None
    return row


def list_items(db, organization_id: str) -> list:
    ensure_tables(db)
    return [r for r in db.list(TABLE_ITEMS)
            if (r.get("organization_id") or "") == (organization_id or "")]


def record_decision(db, organization_id: str, item_id: str, decision: dict, *,
                    inputs_hash: Optional[str] = None) -> dict:
    ensure_tables(db)
    decision_id = str(uuid4())
    row = {
        "decision_id": decision_id, "item_id": item_id, "organization_id": organization_id,
        "decision_state": decision.get("decision_state"), "purchase_ready": 1 if decision.get("purchase_ready") else 0,
        "scorer_version": decision.get("scorer_version"), "inputs_hash": inputs_hash,
        "payload_json": json.dumps(decision, default=str), "created_at": _now(),
    }
    db.insert_ignore(TABLE_DECISIONS, row, conflict_cols=("decision_id",))
    return row


def latest_decision(db, organization_id: str, item_id: str) -> Optional[dict]:
    ensure_tables(db)
    rows = [r for r in db.list(TABLE_DECISIONS)
            if r.get("item_id") == item_id and (r.get("organization_id") or "") == (organization_id or "")]
    if not rows:
        return None
    rows.sort(key=lambda r: str(r.get("created_at") or ""))
    return rows[-1]


# Derived columns exposed on customer-facing item views. Deliberately excludes
# ``payload_json`` (the raw embedded item blob, which may carry third-party
# source fields). P4-T3b policy #5: internal derived records are shown as
# derived records without exposing raw embedded third-party payload fields.
_DERIVED_ITEM_FIELDS = (
    "item_id", "organization_id", "category", "match_state", "resale_score",
    "net_per_unit", "economics_complete", "policy_exclusion_flag",
    "created_at", "updated_at",
)


def project_item(item: Optional[dict]) -> Optional[dict]:
    """Project a stored GG item row to its customer-safe derived view.

    Keeps only derived scalar columns computed from the item — never the raw
    ``payload_json`` blob (which may embed restricted third-party source
    fields). Records with no explicit third-party provenance remain ordinary
    internal, org-scoped derived records and are NOT labeled CUSTOMER_OK.
    """
    if not isinstance(item, dict):
        return None
    return {k: item.get(k) for k in _DERIVED_ITEM_FIELDS if k in item}
