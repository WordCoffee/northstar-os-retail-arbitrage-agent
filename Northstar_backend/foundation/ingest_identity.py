"""Identity ingest contract (Master Plan P4-T2).

Additive Foundation tables + a versioned, idempotent ingest of pipeline identity
outputs:
  - ``ingest_runs``          — one row per ingest run.
  - ``identity_pairs``       — pair-level identity/membership (per lane).
  - ``resale_score_inputs``  — distinct pack/unit/quantity/dimension inputs.

Distinctions preserved (never collapsed):
  supplier pack | marketplace pack | unit_count | net_quantity | package dims.

Provenance: every row keeps raw claims + normalized values + source + observed_at.
Absent / ambiguous / conflicting / stale evidence stays UNKNOWN or is flagged.
``pack_match_state`` is never upgraded to MATCH merely because a row exists.

SellerSprite, when present, is a ONE-TIME historical export only; this contract
does not depend exclusively on it (alternatives carry their own source label,
including manual observed capture).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

TABLE_RUNS = "ingest_runs"
TABLE_PAIRS = "identity_pairs"
TABLE_INPUTS = "resale_score_inputs"

SCHEMA_VERSION = "identity-ingest-1.0.0"

_ALLOWED_MATCH_STATES = {"EXACT_UPC", "EXACT_ASIN", "STRONG", "CANDIDATE",
                         "CONFLICT", "NONE", "UNKNOWN"}
_ALLOWED_PACK_STATES = {"MATCH", "MISMATCH", "UNKNOWN"}
_ASIN_RE = re.compile(r"^B[0-9A-Z]{9}$")

_DDL_PG = [
    "CREATE TABLE IF NOT EXISTS ingest_runs (run_id TEXT PRIMARY KEY, source TEXT NOT NULL,"
    " schema_version TEXT NOT NULL, observed_at TEXT, status TEXT NOT NULL, rows_in INTEGER NOT NULL DEFAULT 0,"
    " pairs_upserted INTEGER NOT NULL DEFAULT 0, inputs_upserted INTEGER NOT NULL DEFAULT 0,"
    " conflicts INTEGER NOT NULL DEFAULT 0, invalid INTEGER NOT NULL DEFAULT 0, notes TEXT,"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
    "CREATE TABLE IF NOT EXISTS identity_pairs (pair_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,"
    " lane TEXT, source_id TEXT, asin TEXT, match_state TEXT NOT NULL, match_score DOUBLE PRECISION,"
    " pack_match_state TEXT NOT NULL DEFAULT 'UNKNOWN', evidence_json TEXT NOT NULL DEFAULT '{}',"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
    "CREATE TABLE IF NOT EXISTS resale_score_inputs (input_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,"
    " pair_id TEXT, asin TEXT, supplier_pack INTEGER, marketplace_pack INTEGER, unit_count INTEGER,"
    " net_quantity DOUBLE PRECISION, package_dimensions_json TEXT, raw_claims_json TEXT NOT NULL DEFAULT '{}',"
    " normalized_json TEXT NOT NULL DEFAULT '{}', source TEXT, observed_at TEXT, freshness_state TEXT NOT NULL,"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
]
_DDL_SQLITE = [s.replace("TIMESTAMPTZ NOT NULL DEFAULT now()", "TEXT NOT NULL")
               .replace("DOUBLE PRECISION", "REAL") for s in _DDL_PG]


def _pg(db) -> bool:
    return getattr(db, "backend", "sqlite") == "postgresql"


def ensure_tables(db) -> None:
    ddl = _DDL_PG if _pg(db) else _DDL_SQLITE
    if _pg(db):
        for s in ddl:
            db._raw.execute(s)
        db._raw.commit()
    else:
        for s in ddl:
            db.conn.execute(s)
        db.conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freshness(observed_at: Optional[str], max_age_days: int = 30) -> str:
    """OBSERVED (fresh) | CACHED (stale) | UNKNOWN (missing/unparseable)."""
    if not observed_at:
        return "UNKNOWN"
    try:
        ts = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return "UNKNOWN"
    age_days = (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
    if age_days < 0:
        return "UNKNOWN"
    return "OBSERVED" if age_days <= max_age_days else "CACHED"


def _norm_match_state(v) -> str:
    s = str(v or "UNKNOWN").upper().strip()
    return s if s in _ALLOWED_MATCH_STATES else "UNKNOWN"


def _norm_pack_state(v) -> str:
    """Never upgrade UNKNOWN -> MATCH. Only an explicit MATCH/MISMATCH passes."""
    s = str(v or "UNKNOWN").upper().strip()
    return s if s in _ALLOWED_PACK_STATES else "UNKNOWN"


def _as_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        i = int(v)
        return i if i >= 0 else None
    except (ValueError, TypeError):
        return None


def _as_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _dumps(v) -> str:
    try:
        return json.dumps(v, sort_keys=True)
    except (TypeError, ValueError):
        return json.dumps({})


def ingest(db, payload: dict, *, max_age_days: int = 30,
           actor_user_id: Optional[str] = None, audit=None) -> dict:
    """Idempotent ingest of a pipeline identity artifact.

    payload: {run_id, source, observed_at?, pairs?[], score_inputs?[]}
    Re-ingesting the same run_id is a no-op returning the stored summary.
    """
    ensure_tables(db)
    run_id = str((payload or {}).get("run_id") or "").strip()
    if not run_id:
        return {"ok": False, "error": "missing_run_id"}
    source = str((payload or {}).get("source") or "unknown").strip()

    existing = db.get(TABLE_RUNS, {"run_id": run_id})
    if existing is not None:
        return {"ok": True, "idempotent": True, "run_id": run_id,
                "pairs_upserted": int(existing.get("pairs_upserted") or 0),
                "inputs_upserted": int(existing.get("inputs_upserted") or 0),
                "conflicts": int(existing.get("conflicts") or 0),
                "invalid": int(existing.get("invalid") or 0)}

    pairs = payload.get("pairs") or []
    inputs = payload.get("score_inputs") or []
    rows_in = len(pairs) + len(inputs)
    pairs_ok = inputs_ok = conflicts = invalid = 0

    for p in pairs:
        pair_id = str(p.get("pair_id") or "").strip()
        asin = p.get("asin")
        if not pair_id:
            invalid += 1
            continue
        if asin and not _ASIN_RE.match(str(asin)):
            asin = None  # keep the row but mark the identifier unusable
        row = {
            "pair_id": pair_id, "run_id": run_id, "lane": p.get("lane"),
            "source_id": p.get("source_id"), "asin": asin,
            "match_state": _norm_match_state(p.get("match_state")),
            "match_score": _as_float(p.get("match_score")),
            "pack_match_state": _norm_pack_state(p.get("pack_match_state")),
            "evidence_json": _dumps(p.get("evidence") or {}),
            "created_at": _now(),
        }
        prior = db.get(TABLE_PAIRS, {"pair_id": pair_id})
        if prior is not None:
            if prior.get("match_state") != row["match_state"]:
                conflicts += 1  # keep first; never overwrite silently
            continue
        db.insert_ignore(TABLE_PAIRS, row, conflict_cols=("pair_id",))
        pairs_ok += 1

    for s in inputs:
        input_id = str(s.get("input_id") or "").strip()
        if not input_id:
            invalid += 1
            continue
        raw = s.get("raw_claims") or {}
        normalized = {
            "supplier_pack": _as_int(s.get("supplier_pack")),
            "marketplace_pack": _as_int(s.get("marketplace_pack")),
            "unit_count": _as_int(s.get("unit_count")),
            "net_quantity": _as_float(s.get("net_quantity")),
            "package_dimensions": s.get("package_dimensions"),
            "pack_match_state": _norm_pack_state(s.get("pack_match_state")),
        }
        row = {
            "input_id": input_id, "run_id": run_id, "pair_id": s.get("pair_id"),
            "asin": s.get("asin"),
            "supplier_pack": normalized["supplier_pack"],
            "marketplace_pack": normalized["marketplace_pack"],
            "unit_count": normalized["unit_count"],
            "net_quantity": normalized["net_quantity"],
            "package_dimensions_json": _dumps(s.get("package_dimensions") or {}),
            "raw_claims_json": _dumps(raw),
            "normalized_json": _dumps(normalized),
            "source": s.get("source") or source,
            "observed_at": s.get("observed_at"),
            "freshness_state": _freshness(s.get("observed_at"), max_age_days),
            "created_at": _now(),
        }
        prior = db.get(TABLE_INPUTS, {"input_id": input_id})
        if prior is not None:
            if prior.get("normalized_json") != row["normalized_json"]:
                conflicts += 1
            continue
        db.insert_ignore(TABLE_INPUTS, row, conflict_cols=("input_id",))
        inputs_ok += 1

    db.insert_ignore(TABLE_RUNS, {
        "run_id": run_id, "source": source, "schema_version": SCHEMA_VERSION,
        "observed_at": payload.get("observed_at"), "status": "completed",
        "rows_in": rows_in, "pairs_upserted": pairs_ok, "inputs_upserted": inputs_ok,
        "conflicts": conflicts, "invalid": invalid, "notes": None, "created_at": _now(),
    }, conflict_cols=("run_id",))

    if audit is not None:
        try:
            audit.record(action="pipeline.ingest_identity", actor_user_id=actor_user_id,
                         resource_type="ingest_run", resource_id=run_id,
                         after_meta={"source": source, "rows_in": rows_in,
                                     "pairs": pairs_ok, "inputs": inputs_ok,
                                     "conflicts": conflicts, "invalid": invalid})
        except Exception:  # noqa: BLE001
            pass

    return {"ok": True, "idempotent": False, "run_id": run_id, "rows_in": rows_in,
            "pairs_upserted": pairs_ok, "inputs_upserted": inputs_ok,
            "conflicts": conflicts, "invalid": invalid}


def run_summary(db, run_id: str) -> Optional[dict]:
    ensure_tables(db)
    return db.get(TABLE_RUNS, {"run_id": run_id})