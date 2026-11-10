"""Durable SQLite persistence for the Costco Non-Kirkland pipeline.

Extends the CANONICAL Northstar internal database (`data_layer.get_db()` →
`Northstar_backend/data/northstar.db`) with pipeline tables. Uses
CREATE TABLE IF NOT EXISTS (additive-only), following the repo convention
(auth.py adds its own tables the same way). No new engine; no parallel store.

Tables:
  costco_pipeline_runs            run manifests (import / exclusion / match / score / enrichment)
  costco_source_products          canonical normalized Costco records (with exclusion markers)
  amazon_match_candidates         offline Amazon match queue
  costco_evidence                 evidence / provenance rows
  costco_enrichment_manifests     approval-gated enrichment manifests
  costco_gg_scores                Golden Goose score outputs
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .enums import PURCHASE_AUTHORIZATION_NOT_AUTHORIZED

try:  # cwd = Northstar_backend
    from data_layer import get_db
except ImportError:  # pragma: no cover
    from ..data_layer import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json(x: Any) -> str:
    return json.dumps(x, default=str)


DDL_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS costco_pipeline_runs (
        run_id TEXT PRIMARY KEY,
        run_name TEXT NOT NULL,
        command TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        counts_json TEXT,
        error_summary TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS costco_source_products (
        id TEXT PRIMARY KEY,
        run_id TEXT,
        source_name TEXT,
        source_record_id TEXT,
        source_file_or_dataset TEXT,
        source_url TEXT,
        costco_item_number TEXT,
        title_raw TEXT,
        title_normalized TEXT,
        brand_raw TEXT,
        brand_normalized TEXT,
        upc TEXT,
        ean TEXT,
        gtin TEXT,
        manufacturer_part_number TEXT,
        costco_price REAL,
        currency TEXT,
        costco_pack_raw TEXT,
        normalized_unit_count REAL,
        normalized_unit_kind TEXT,
        size_or_weight_raw TEXT,
        availability_status TEXT,
        warehouse_or_location TEXT,
        observed_at TEXT,
        imported_at TEXT,
        freshness_status TEXT,
        evidence_class TEXT,
        identity_status TEXT,
        exclusion_reason TEXT,
        manual_review_required INTEGER,
        eligible_for_costco_non_kirkland_workflow INTEGER,
        disallowed_classes TEXT,
        raw_json TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS amazon_match_candidates (
        id TEXT PRIMARY KEY,
        run_id TEXT,
        costco_source_product_id TEXT,
        asin TEXT,
        marketplace TEXT DEFAULT 'US',
        match_method TEXT,
        match_confidence REAL,
        title_similarity REAL,
        brand_match_status TEXT,
        pack_match_status TEXT,
        size_match_status TEXT,
        variation_match_status TEXT,
        identity_status TEXT,
        match_rationale TEXT,
        manual_review_required INTEGER,
        created_at TEXT,
        amazon_title TEXT,
        amazon_brand TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS costco_evidence (
        id TEXT PRIMARY KEY,
        run_id TEXT,
        candidate_id TEXT,
        source TEXT,
        source_url TEXT,
        field_name TEXT,
        field_value TEXT,
        evidence_class TEXT,
        freshness_status TEXT,
        capture_status TEXT,
        captured_at TEXT,
        limitations TEXT,
        metadata_json TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS costco_enrichment_manifests (
        manifest_id TEXT PRIMARY KEY,
        run_id TEXT,
        provider TEXT,
        status TEXT DEFAULT 'planned',
        max_items INTEGER,
        spend_cap REAL,
        approved INTEGER DEFAULT 0,
        approval_token TEXT,
        created_at TEXT,
        approved_at TEXT,
        items_json TEXT,
        preflight_json TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS costco_gg_scores (
        id TEXT PRIMARY KEY,
        run_id TEXT,
        costco_source_product_id TEXT,
        amazon_match_candidate_id TEXT,
        score REAL,
        score_version TEXT,
        score_components_json TEXT,
        positive_evidence_json TEXT,
        penalties_json TEXT,
        risk_flags_json TEXT,
        missing_evidence_json TEXT,
        confidence_level TEXT,
        recommendation_status TEXT,
        purchase_authorization_status TEXT,
        manual_review_required INTEGER,
        evidence_summary TEXT,
        scored_at TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS costco_confirmations (
        confirmation_id TEXT PRIMARY KEY,
        action_key TEXT NOT NULL,
        description TEXT,
        granted_at TEXT NOT NULL,
        granted_by TEXT,
        expires_at TEXT,
        UNIQUE(action_key)
    );""",
    """CREATE TABLE IF NOT EXISTS costco_identity_enrichment (
        id TEXT PRIMARY KEY,
        costco_item_number TEXT,
        source_record_id TEXT,
        source_product_id TEXT,
        provider_name TEXT,
        provider_snapshot_id TEXT,
        snapshot_sha256 TEXT,
        brand TEXT,
        manufacturer TEXT,
        title TEXT,
        description TEXT,
        category_path TEXT,
        upc TEXT,
        ean TEXT,
        gtin TEXT,
        mpn TEXT,
        manufacturer_model TEXT,
        identifier_type TEXT,
        identifier_value TEXT,
        identifier_source TEXT,
        identifier_capture_status TEXT,
        net_weight TEXT,
        shipping_weight TEXT,
        package_length TEXT,
        package_width TEXT,
        package_height TEXT,
        outer_pack_count TEXT,
        inner_unit_count TEXT,
        unit_count TEXT,
        unit_measure TEXT,
        split_pack_status TEXT,
        captured_at TEXT,
        ingested_at TEXT,
        freshness_status TEXT,
        contract_json TEXT,
        field_capture_status_json TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS costco_identifier_resolution_queue (
        id TEXT PRIMARY KEY,
        run_id TEXT,
        source_product_id TEXT,
        costco_item_number TEXT,
        missing_identity_fields TEXT,
        missing_physical_fields TEXT,
        possible_next_source TEXT,
        title_only_insufficient INTEGER DEFAULT 1,
        physical_pack_missing INTEGER DEFAULT 1,
        created_at TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS costco_provider_imports (
        import_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        filename TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        parse_kind TEXT,
        schema_version TEXT,
        rows_total INTEGER,
        rows_imported INTEGER,
        row_status_counts_json TEXT,
        imported_at TEXT NOT NULL
    );""",
    """CREATE TABLE IF NOT EXISTS costco_market_snapshots (
        id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        asin TEXT,
        provider_export_filename TEXT,
        provider_export_sha256 TEXT,
        provider_row_number INTEGER,
        provider_record_id TEXT,
        provider_snapshot_id TEXT,
        observed_at TEXT,
        ingested_at TEXT,
        freshness_status TEXT,
        identity_json TEXT,
        marketplace_json TEXT,
        demand_json TEXT,
        fees_json TEXT,
        size_json TEXT,
        risk_json TEXT,
        fields_json TEXT,
        raw_source_reference TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS costco_candidate_decisions (
        id TEXT PRIMARY KEY,
        candidate_id TEXT,
        costco_source_product_id TEXT,
        asin TEXT,
        identity_state TEXT,
        split_pack_state TEXT,
        market_snapshot_id TEXT,
        provider TEXT,
        competition_state TEXT,
        economics_json TEXT,
        market_snapshot_json TEXT,
        mfn_score REAL,
        mfn_score_version TEXT,
        recommendation_status TEXT,
        reason_codes_json TEXT,
        risk_flags_json TEXT,
        purchase_authorization_status TEXT,
        evidence_summary TEXT,
        source_name TEXT,
        source_sku TEXT,
        source_url TEXT,
        source_price REAL,
        source_price_observed_at TEXT,
        source_pack_text TEXT,
        updated_at TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS costco_approvals (
        approval_id TEXT PRIMARY KEY,
        candidate_id TEXT,
        costco_source_product_id TEXT,
        asin TEXT,
        source_name TEXT,
        source_sku TEXT,
        source_url TEXT,
        source_price REAL,
        source_price_observed_at TEXT,
        source_pack_text TEXT,
        quantity INTEGER,
        approved_by TEXT,
        state TEXT DEFAULT 'requested',
        granted_at TEXT,
        expires_at TEXT,
        revoked_at TEXT,
        revoke_reason TEXT,
        invalidated_at TEXT,
        invalidate_reason TEXT,
        economics_snapshot_json TEXT,
        market_snapshot_json TEXT,
        reason_codes_json TEXT,
        created_at TEXT,
        updated_at TEXT
    );""",
]


class PipelineStore:
    """CRUD over the pipeline tables on the canonical DB connection."""

    def __init__(self, db=None):
        self._db = db or get_db()
        self._ensure_tables()

    def _ensure_tables(self):
        for stmt in DDL_STATEMENTS:
            self._db.execute(stmt)
        self._ensure_disallowed_column()
        self._db.commit()

    def _ensure_disallowed_column(self):
        """Additive-only: add disallowed_classes column if missing (SQLite)."""
        try:
            cols = [r[1] for r in self._db.execute("PRAGMA table_info(costco_source_products)").fetchall()]
            if "disallowed_classes" not in cols:
                self._db.execute("ALTER TABLE costco_source_products ADD COLUMN disallowed_classes TEXT")
        except Exception:
            pass

    # ---------------- runs ----------------
    def create_run(self, run_name: str, command: Optional[str] = None) -> Dict[str, Any]:
        run_id = _uid("run")
        now = _now()
        self._db.execute(
            "INSERT INTO costco_pipeline_runs (run_id, run_name, command, status, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (run_id, run_name, command, "active", now, now),
        )
        self._db.commit()
        return {"run_id": run_id, "run_name": run_name, "command": command, "status": "active",
                "created_at": now, "updated_at": now}

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT * FROM costco_pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def update_run(self, run_id: str, **fields) -> None:
        allowed = ("status", "counts_json", "error_summary")
        sets = [f"{k}=?" for k in fields if k in allowed]
        if not sets:
            return
        params = [fields[k] for k in fields if k in allowed] + [_now(), run_id]
        self._db.execute(f"UPDATE costco_pipeline_runs SET {', '.join(sets)}, updated_at=? WHERE run_id=?", params)
        self._db.commit()

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM costco_pipeline_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---------------- source products ----------------
    def upsert_source_product(self, rec: Dict[str, Any], run_id: Optional[str] = None) -> Dict[str, Any]:
        rid = rec.get("id") or _uid("csp")
        now = _now()
        rec.setdefault("eligible_for_costco_non_kirkland_workflow", 1)
        self._db.execute(
            """INSERT INTO costco_source_products
               (id, run_id, source_name, source_record_id, source_file_or_dataset, source_url,
                costco_item_number, title_raw, title_normalized, brand_raw, brand_normalized,
                upc, ean, gtin, manufacturer_part_number, costco_price, currency, costco_pack_raw,
                normalized_unit_count, normalized_unit_kind, size_or_weight_raw, availability_status,
                warehouse_or_location, observed_at, imported_at, freshness_status, evidence_class,
                identity_status, exclusion_reason, manual_review_required,
                eligible_for_costco_non_kirkland_workflow, disallowed_classes, raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 source_name=excluded.source_name, source_record_id=excluded.source_record_id,
                 source_file_or_dataset=excluded.source_file_or_dataset, source_url=excluded.source_url,
                 costco_item_number=excluded.costco_item_number, title_raw=excluded.title_raw,
                 title_normalized=excluded.title_normalized, brand_raw=excluded.brand_raw,
                 brand_normalized=excluded.brand_normalized, upc=excluded.upc, ean=excluded.ean,
                 gtin=excluded.gtin, manufacturer_part_number=excluded.manufacturer_part_number,
                 costco_price=excluded.costco_price, currency=excluded.currency,
                 costco_pack_raw=excluded.costco_pack_raw, normalized_unit_count=excluded.normalized_unit_count,
                 normalized_unit_kind=excluded.normalized_unit_kind, size_or_weight_raw=excluded.size_or_weight_raw,
                 availability_status=excluded.availability_status, warehouse_or_location=excluded.warehouse_or_location,
                 observed_at=excluded.observed_at, imported_at=excluded.imported_at,
                 freshness_status=excluded.freshness_status, evidence_class=excluded.evidence_class,
                 identity_status=excluded.identity_status, exclusion_reason=excluded.exclusion_reason,
                 manual_review_required=excluded.manual_review_required,
                 eligible_for_costco_non_kirkland_workflow=excluded.eligible_for_costco_non_kirkland_workflow,
                 disallowed_classes=excluded.disallowed_classes,
                 raw_json=excluded.raw_json""",
            (rid, run_id, rec.get("source_name"), rec.get("source_record_id"),
             rec.get("source_file_or_dataset"), rec.get("source_url"),
             rec.get("costco_item_number"), rec.get("title_raw"), rec.get("title_normalized"),
             rec.get("brand_raw"), rec.get("brand_normalized"), rec.get("upc"), rec.get("ean"),
             rec.get("gtin"), rec.get("manufacturer_part_number"), rec.get("costco_price"),
             rec.get("currency"), rec.get("costco_pack_raw"), rec.get("normalized_unit_count"),
             rec.get("normalized_unit_kind"), rec.get("size_or_weight_raw"), rec.get("availability_status"),
             rec.get("warehouse_or_location"), rec.get("observed_at"), rec.get("imported_at") or now,
             rec.get("freshness_status"), rec.get("evidence_class"), rec.get("identity_status"),
             rec.get("exclusion_reason"), 1 if rec.get("manual_review_required") else 0,
             1 if rec.get("eligible_for_costco_non_kirkland_workflow") else 0,
             ",".join(rec.get("disallowed_classes") or []),
             _json(rec.get("raw", rec))),
        )
        self._db.commit()
        rec["id"] = rid
        return rec

    def list_source_products(self, run_id: Optional[str] = None, eligible_only: bool = False,
                             excluded: bool = False, limit: int = 2000) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if run_id:
            clauses.append("run_id=?")
            params.append(run_id)
        if eligible_only:
            clauses.append("eligible_for_costco_non_kirkland_workflow=1")
        if excluded:
            clauses.append("exclusion_reason IS NOT NULL")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._db.execute(
            f"SELECT * FROM costco_source_products{where} ORDER BY imported_at DESC LIMIT ?",
            (*params, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            dcls = d.get("disallowed_classes")
            d["disallowed_classes"] = [x for x in (dcls or "").split(",") if x]
            out.append(d)
        return out

    def count_source_products(self, run_id: Optional[str] = None, eligible_only: bool = False) -> int:
        clauses, params = [], []
        if run_id:
            clauses.append("run_id=?")
            params.append(run_id)
        if eligible_only:
            clauses.append("eligible_for_costco_non_kirkland_workflow=1")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        row = self._db.execute(f"SELECT COUNT(*) AS n FROM costco_source_products{where}", tuple(params)).fetchone()
        return int(row["n"]) if row else 0

    def get_source_product(self, source_product_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT * FROM costco_source_products WHERE id=?",
                               (source_product_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        dcls = d.get("disallowed_classes")
        d["disallowed_classes"] = [x for x in (dcls or "").split(",") if x]
        return d

    # ---------------- match candidates ----------------
    def insert_match_candidate(self, cand: Dict[str, Any], run_id: Optional[str] = None) -> Dict[str, Any]:
        cid = _uid("amc")
        self._db.execute(
            """INSERT INTO amazon_match_candidates
               (id, run_id, costco_source_product_id, asin, marketplace, match_method, match_confidence,
                title_similarity, brand_match_status, pack_match_status, size_match_status,
                variation_match_status, identity_status, match_rationale, manual_review_required,
                created_at, amazon_title, amazon_brand)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, run_id, cand.get("costco_source_product_id"), cand.get("asin"),
             cand.get("marketplace", "US"), cand.get("match_method"), cand.get("match_confidence"),
             cand.get("title_similarity"), cand.get("brand_match_status"), cand.get("pack_match_status"),
             cand.get("size_match_status"), cand.get("variation_match_status"),
             cand.get("identity_status"), cand.get("match_rationale"),
             1 if cand.get("manual_review_required") else 0, _now(),
             cand.get("amazon_title"), cand.get("amazon_brand")),
        )
        self._db.commit()
        cand["id"] = cid
        return cand

    def list_match_candidates(self, run_id: Optional[str] = None, identity_status: Optional[str] = None,
                              limit: int = 2000) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if run_id:
            clauses.append("run_id=?")
            params.append(run_id)
        if identity_status:
            clauses.append("identity_status=?")
            params.append(identity_status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._db.execute(
            f"SELECT * FROM amazon_match_candidates{where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit)).fetchall()
        return [dict(r) for r in rows]

    # ---------------- evidence ----------------
    def add_evidence(self, run_id: Optional[str], candidate_id: Optional[str], ev: Dict[str, Any]) -> Dict[str, Any]:
        eid = _uid("ev")
        self._db.execute(
            """INSERT INTO costco_evidence
               (id, run_id, candidate_id, source, source_url, field_name, field_value,
                evidence_class, freshness_status, capture_status, captured_at, limitations, metadata_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (eid, run_id, candidate_id, ev.get("source"), ev.get("source_url"), ev.get("field_name"),
             ev.get("field_value"), ev.get("evidence_class"), ev.get("freshness_status"),
             ev.get("capture_status"), ev.get("captured_at") or _now(), ev.get("limitations"),
             _json(ev.get("metadata", {}))),
        )
        self._db.commit()
        ev["id"] = eid
        return ev

    def list_evidence(self, candidate_id: Optional[str] = None, run_id: Optional[str] = None,
                      limit: int = 2000) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if candidate_id:
            clauses.append("candidate_id=?")
            params.append(candidate_id)
        if run_id:
            clauses.append("run_id=?")
            params.append(run_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._db.execute(f"SELECT * FROM costco_evidence{where} ORDER BY captured_at DESC LIMIT ?",
                                (*params, limit)).fetchall()
        return [dict(r) for r in rows]

    # ---------------- enrichment manifests ----------------
    def create_manifest(self, run_id: str, provider: str, items: List[str],
                        max_items: int, spend_cap: Optional[float]) -> Dict[str, Any]:
        mid = _uid("man")
        now = _now()
        self._db.execute(
            """INSERT INTO costco_enrichment_manifests
               (manifest_id, run_id, provider, status, max_items, spend_cap, approved, created_at, items_json)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (mid, run_id, provider, "planned", max_items, spend_cap, 0, now, _json(items)),
        )
        self._db.commit()
        return {"manifest_id": mid, "run_id": run_id, "provider": provider, "status": "planned",
                "max_items": max_items, "spend_cap": spend_cap, "approved": 0, "created_at": now,
                "items": items}

    def get_manifest(self, manifest_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT * FROM costco_enrichment_manifests WHERE manifest_id=?",
                               (manifest_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["items"] = json.loads(out.get("items_json") or "[]")
        return out

    def update_manifest(self, manifest_id: str, **fields) -> None:
        allowed = ("status", "approved", "approval_token", "approved_at", "preflight_json")
        sets = [f"{k}=?" for k in fields if k in allowed]
        if not sets:
            return
        params = [fields[k] for k in fields if k in allowed] + [manifest_id]
        self._db.execute(f"UPDATE costco_enrichment_manifests SET {', '.join(sets)} WHERE manifest_id=?",
                         params)
        self._db.commit()

    # ---------------- confirmations (sign-in gate) ----------------
    def grant_confirmation(self, action_key: str, description: Optional[str] = None,
                           granted_by: str = "operator", expires_in_ms: int = 6 * 60 * 60 * 1000) -> Dict[str, Any]:
        cid = _uid("conf")
        expires = datetime.fromtimestamp((datetime.now().timestamp() + expires_in_ms / 1000.0),
                                         tz=timezone.utc).isoformat()
        self._db.execute(
            """INSERT OR REPLACE INTO costco_confirmations
               (confirmation_id, action_key, description, granted_at, granted_by, expires_at)
               VALUES (?,?,?,?,?,?)""",
            (cid, action_key, description, _now(), granted_by, expires),
        )
        self._db.commit()
        return {"confirmation_id": cid, "action_key": action_key, "description": description,
                "granted_by": granted_by, "granted_at": _now(), "expires_at": expires}

    def has_confirmation(self, action_key: str) -> bool:
        from datetime import datetime as _dt
        try:
            row = self._db.execute(
                "SELECT expires_at FROM costco_confirmations WHERE action_key=? ORDER BY granted_at DESC LIMIT 1",
                (action_key,)).fetchone()
        except Exception:
            return False
        if not row:
            return False
        expires = row["expires_at"]
        if not expires:
            return True
        try:
            return _dt.fromisoformat(expires).timestamp() > _dt.now().timestamp()
        except (ValueError, TypeError):
            return True

    # ---------------- GG scores ----------------
    def insert_gg_score(self, run_id: Optional[str], csp_id: Optional[str], amc_id: Optional[str],
                        score: Dict[str, Any]) -> Dict[str, Any]:
        sid = _uid("gg")
        now = _now()
        self._db.execute(
            """INSERT INTO costco_gg_scores
               (id, run_id, costco_source_product_id, amazon_match_candidate_id, score, score_version,
                score_components_json, positive_evidence_json, penalties_json, risk_flags_json,
                missing_evidence_json, confidence_level, recommendation_status,
                purchase_authorization_status, manual_review_required, evidence_summary, scored_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, run_id, csp_id, amc_id, score.get("score"), score.get("score_version"),
             _json(score.get("score_components", {})), _json(score.get("positive_evidence", [])),
             _json(score.get("penalties", [])), _json(score.get("risk_flags", [])),
             _json(score.get("missing_evidence", [])), score.get("confidence_level"),
             score.get("recommendation_status"), score.get("purchase_authorization_status") or PURCHASE_AUTHORIZATION_NOT_AUTHORIZED,
             1 if score.get("manual_review_required") else 0, score.get("evidence_summary"), now),
        )
        self._db.commit()
        score["id"] = sid
        return score

    def list_gg_scores(self, run_id: Optional[str] = None, limit: int = 2000) -> List[Dict[str, Any]]:
        if run_id:
            rows = self._db.execute(
                "SELECT * FROM costco_gg_scores WHERE run_id=? ORDER BY scored_at DESC LIMIT ?",
                (run_id, limit)).fetchall()
        else:
            rows = self._db.execute("SELECT * FROM costco_gg_scores ORDER BY scored_at DESC LIMIT ?",
                                    (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["score_components"] = json.loads(d.get("score_components_json") or "{}")
            for k in ("positive_evidence_json", "penalties_json", "risk_flags_json", "missing_evidence_json"):
                d[k] = json.loads(d.get(k) or "[]")
            out.append(d)
        return out


# ---------------- provider imports ----------------
    def record_import(self, provider: str, filename: str, sha256: str, parse_kind: str,
                      schema_version: str, rows_total: int, rows_imported: int,
                      row_status_counts: Dict[str, int]) -> str:
        import_id = _uid("imp")
        self._db.execute(
            """INSERT INTO costco_provider_imports
               (import_id, provider, filename, sha256, parse_kind, schema_version,
                rows_total, rows_imported, row_status_counts_json, imported_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (import_id, provider, filename, sha256, parse_kind, schema_version,
             rows_total, rows_imported, _json(row_status_counts), _now()),
        )
        self._db.commit()
        return import_id

    def has_imported_row(self, asin: Optional[str], sha256: Optional[str],
                         row_number: Optional[int]) -> bool:
        if not asin or not sha256 or row_number is None:
            return False
        row = self._db.execute(
            "SELECT 1 FROM costco_market_snapshots WHERE asin=? AND provider_export_sha256=? AND provider_row_number=? LIMIT 1",
            (asin, sha256, row_number)).fetchone()
        return row is not None

    # ---------------- market snapshots ----------------
    def persist_market_snapshot(self, snapshot: Dict[str, Any]) -> str:
        sid = _uid("mkt")
        fields = snapshot.get("fields", {})
        asin = snapshot.get("asin")
        first = fields.get("asin", {})
        self._db.execute(
            """INSERT INTO costco_market_snapshots
               (id, provider, asin, provider_export_filename, provider_export_sha256,
                provider_row_number, provider_record_id, provider_snapshot_id,
                observed_at, ingested_at, freshness_status,
                identity_json, marketplace_json, demand_json, fees_json, size_json, risk_json,
                fields_json, raw_source_reference)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, snapshot.get("provider"), asin,
             first.get("provider_export_filename"), first.get("provider_export_sha256"),
             first.get("provider_row_number"), first.get("provider_record_id"),
             first.get("provider_snapshot_id"), first.get("observed_at"), first.get("ingested_at"),
             first.get("freshness_status"),
             _json(snapshot.get("identity", {})), _json(snapshot.get("marketplace", {})),
             _json(snapshot.get("demand", {})), _json(snapshot.get("fees", {})),
             _json(snapshot.get("size", {})), _json(snapshot.get("risk", {})),
             _json(fields), first.get("raw_source_reference")),
        )
        self._db.commit()
        return sid

    def get_market_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT * FROM costco_market_snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if not row:
            return None
        return self._decode_snapshot(dict(row))

    def list_market_snapshots(self, provider: Optional[str] = None, asin: Optional[str] = None,
                              limit: int = 2000) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if provider:
            clauses.append("provider=?")
            params.append(provider)
        if asin:
            clauses.append("asin=?")
            params.append(asin)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._db.execute(
            f"SELECT * FROM costco_market_snapshots{where} ORDER BY ingested_at DESC LIMIT ?",
            (*params, limit)).fetchall()
        return [self._decode_snapshot(dict(r)) for r in rows]

    def _decode_snapshot(self, d: Dict[str, Any]) -> Dict[str, Any]:
        for k in ("identity_json", "marketplace_json", "demand_json", "fees_json",
                  "size_json", "risk_json", "fields_json"):
            d[k.replace("_json", "")] = json.loads(d.get(k) or "{}")
        return d

    # ---------------- candidate decisions ----------------
    def upsert_candidate_decision(self, cand: Dict[str, Any]) -> str:
        cid = cand.get("id") or _uid("dec")
        self._db.execute(
            """INSERT INTO costco_candidate_decisions
               (id, candidate_id, costco_source_product_id, asin, identity_state, split_pack_state,
                market_snapshot_id, provider, competition_state, economics_json, market_snapshot_json,
                mfn_score,
                mfn_score_version, recommendation_status, reason_codes_json, risk_flags_json,
                purchase_authorization_status, evidence_summary,
                source_name, source_sku, source_url, source_price, source_price_observed_at,
                source_pack_text, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 identity_state=excluded.identity_state, split_pack_state=excluded.split_pack_state,
                 market_snapshot_id=excluded.market_snapshot_id, provider=excluded.provider,
                 competition_state=excluded.competition_state, economics_json=excluded.economics_json,
                 market_snapshot_json=excluded.market_snapshot_json,
                 mfn_score=excluded.mfn_score, mfn_score_version=excluded.mfn_score_version,
                 recommendation_status=excluded.recommendation_status,
                 reason_codes_json=excluded.reason_codes_json, risk_flags_json=excluded.risk_flags_json,
                 purchase_authorization_status=excluded.purchase_authorization_status,
                 evidence_summary=excluded.evidence_summary,
                 source_name=excluded.source_name, source_sku=excluded.source_sku,
                 source_url=excluded.source_url, source_price=excluded.source_price,
                 source_price_observed_at=excluded.source_price_observed_at,
                 source_pack_text=excluded.source_pack_text,
                 updated_at=excluded.updated_at""",
            (cid, cand.get("candidate_id"), cand.get("costco_source_product_id"), cand.get("asin"),
             cand.get("identity_state"), cand.get("split_pack_state"), cand.get("market_snapshot_id"),
             cand.get("provider"), cand.get("competition_state"), _json(cand.get("economics") or {}),
             _json(cand.get("market_snapshot") or {}),
             cand.get("mfn_score"), cand.get("mfn_score_version"), cand.get("recommendation_status"),
             _json(cand.get("reason_codes") or []), _json(cand.get("risk_flags") or []),
             cand.get("purchase_authorization_status") or PURCHASE_AUTHORIZATION_NOT_AUTHORIZED,
             cand.get("evidence_summary"),
             cand.get("source_name"), cand.get("source_sku"), cand.get("source_url"),
             cand.get("source_price"), cand.get("source_price_observed_at"),
             cand.get("source_pack_text"), _now()),
        )
        self._db.commit()
        cand["id"] = cid
        return cid

    def list_candidate_decisions(self, candidate_id: Optional[str] = None,
                                 recommendation_status: Optional[str] = None,
                                 limit: int = 2000) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if candidate_id:
            clauses.append("candidate_id=?")
            params.append(candidate_id)
        if recommendation_status:
            clauses.append("recommendation_status=?")
            params.append(recommendation_status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._db.execute(
            f"SELECT * FROM costco_candidate_decisions{where} ORDER BY updated_at DESC LIMIT ?",
            (*params, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["economics"] = json.loads(d.get("economics_json") or "{}")
            d["market_snapshot"] = json.loads(d.get("market_snapshot_json") or "{}")
            d["reason_codes"] = json.loads(d.get("reason_codes_json") or "[]")
            d["risk_flags"] = json.loads(d.get("risk_flags_json") or "[]")
            out.append(d)
        return out

    # ---------------- approvals ----------------
    def create_approval(self, approval: Dict[str, Any]) -> Dict[str, Any]:
        aid = _uid("appr")
        now = _now()
        self._db.execute(
            """INSERT INTO costco_approvals
               (approval_id, candidate_id, costco_source_product_id, asin, source_name, source_sku,
                source_url, source_price, source_price_observed_at, source_pack_text, quantity,
                approved_by, state, granted_at, expires_at, revoked_at, revoke_reason,
                invalidated_at, invalidate_reason, economics_snapshot_json, market_snapshot_json,
                reason_codes_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, approval.get("candidate_id"), approval.get("costco_source_product_id"),
             approval.get("asin"), approval.get("source_name"), approval.get("source_sku"),
             approval.get("source_url"), approval.get("source_price"),
             approval.get("source_price_observed_at"), approval.get("source_pack_text"),
             approval.get("quantity"), approval.get("approved_by"),
             approval.get("state", "requested"), approval.get("granted_at"),
             approval.get("expires_at"), approval.get("revoked_at"), approval.get("revoke_reason"),
             approval.get("invalidated_at"), approval.get("invalidate_reason"),
             _json(approval.get("economics_snapshot") or {}),
             _json(approval.get("market_snapshot") or {}),
             _json(approval.get("reason_codes") or []), now, now),
        )
        self._db.commit()
        approval["approval_id"] = aid
        approval["created_at"] = now
        return approval

    def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT * FROM costco_approvals WHERE approval_id=?", (approval_id,)).fetchone()
        if not row:
            return None
        return self._decode_approval(dict(row))

    def update_approval(self, approval_id: str, **fields) -> None:
        allowed = ("state", "granted_at", "expires_at", "revoked_at", "revoke_reason",
                   "invalidated_at", "invalidate_reason", "approved_by", "quantity")
        sets = [f"{k}=?" for k in fields if k in allowed]
        if not sets:
            return
        params = [fields[k] for k in fields if k in allowed] + [_now(), approval_id]
        self._db.execute(f"UPDATE costco_approvals SET {', '.join(sets)}, updated_at=? WHERE approval_id=?",
                         params)
        self._db.commit()

    def list_approvals(self, state: Optional[str] = None, limit: int = 2000) -> List[Dict[str, Any]]:
        if state:
            rows = self._db.execute(
                "SELECT * FROM costco_approvals WHERE state=? ORDER BY created_at DESC LIMIT ?",
                (state, limit)).fetchall()
        else:
            rows = self._db.execute("SELECT * FROM costco_approvals ORDER BY created_at DESC LIMIT ?",
                                    (limit,)).fetchall()
        return [self._decode_approval(dict(r)) for r in rows]

    def _decode_approval(self, d: Dict[str, Any]) -> Dict[str, Any]:
        d["economics_snapshot"] = json.loads(d.get("economics_snapshot_json") or "{}")
        d["market_snapshot"] = json.loads(d.get("market_snapshot_json") or "{}")
        d["reason_codes"] = json.loads(d.get("reason_codes_json") or "[]")
        return d

    # ---------------- identity enrichment ----------------
    def upsert_enrichment_record(self, rec: Dict[str, Any]) -> str:
        eid = rec.get("id") or _uid("enr")
        self._db.execute(
            """INSERT INTO costco_identity_enrichment
               (id, costco_item_number, source_record_id, source_product_id, provider_name,
                provider_snapshot_id, snapshot_sha256, brand, manufacturer, title, description,
                category_path, upc, ean, gtin, mpn, manufacturer_model, identifier_type,
                identifier_value, identifier_source, identifier_capture_status, net_weight,
                shipping_weight, package_length, package_width, package_height, outer_pack_count,
                inner_unit_count, unit_count, unit_measure, split_pack_status, captured_at,
                ingested_at, freshness_status, contract_json, field_capture_status_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 upc=excluded.upc, ean=excluded.ean, gtin=excluded.gtin, mpn=excluded.mpn,
                 manufacturer_model=excluded.manufacturer_model, identifier_type=excluded.identifier_type,
                 identifier_value=excluded.identifier_value, identifier_source=excluded.identifier_source,
                 identifier_capture_status=excluded.identifier_capture_status, net_weight=excluded.net_weight,
                 shipping_weight=excluded.shipping_weight, package_length=excluded.package_length,
                 package_width=excluded.package_width, package_height=excluded.package_height,
                 outer_pack_count=excluded.outer_pack_count, inner_unit_count=excluded.inner_unit_count,
                 unit_count=excluded.unit_count, unit_measure=excluded.unit_measure,
                 split_pack_status=excluded.split_pack_status, freshness_status=excluded.freshness_status,
                 contract_json=excluded.contract_json, field_capture_status_json=excluded.field_capture_status_json""",
            (eid, rec.get("costco_item_number"), rec.get("source_record_id"), rec.get("source_product_id"),
             rec.get("provider_name"), rec.get("provider_snapshot_id"), rec.get("snapshot_sha256"),
             rec.get("brand"), rec.get("manufacturer"), rec.get("title"), rec.get("description"),
             rec.get("category_path"), rec.get("upc"), rec.get("ean"), rec.get("gtin"), rec.get("mpn"),
             rec.get("manufacturer_model"), rec.get("identifier_type"), rec.get("identifier_value"),
             rec.get("identifier_source"), rec.get("identifier_capture_status"), rec.get("net_weight"),
             rec.get("shipping_weight"), rec.get("package_length"), rec.get("package_width"),
             rec.get("package_height"), rec.get("outer_pack_count"), rec.get("inner_unit_count"),
             rec.get("unit_count"), rec.get("unit_measure"), rec.get("split_pack_status"),
             rec.get("captured_at"), rec.get("ingested_at") or _now(), rec.get("freshness_status"),
             _json(rec.get("contract", rec)), _json(rec.get("field_capture_status", {}))),
        )
        self._db.commit()
        rec["id"] = eid
        return eid

    def get_enrichment_record(self, costco_item_number: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute(
            "SELECT * FROM costco_identity_enrichment WHERE costco_item_number=? ORDER BY ingested_at DESC LIMIT 1",
            (costco_item_number,)).fetchone()
        return dict(row) if row else None

    def list_enrichment_records(self, limit: int = 2000) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._db.execute(
            "SELECT * FROM costco_identity_enrichment ORDER BY ingested_at DESC LIMIT ?", (limit,)).fetchall()]

    def has_enrichment_snapshot(self, sha256: str) -> bool:
        if not sha256:
            return False
        return self._db.execute("SELECT 1 FROM costco_identity_enrichment WHERE snapshot_sha256=? LIMIT 1",
                                (sha256,)).fetchone() is not None

    def add_identifier_resolution(self, entry: Dict[str, Any]) -> str:
        rid = _uid("idr")
        self._db.execute(
            """INSERT INTO costco_identifier_resolution_queue
               (id, run_id, source_product_id, costco_item_number, missing_identity_fields,
                missing_physical_fields, possible_next_source, title_only_insufficient,
                physical_pack_missing, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (rid, entry.get("run_id"), entry.get("source_product_id"), entry.get("costco_item_number"),
             ",".join(entry.get("missing_identity_fields") or []),
             ",".join(entry.get("missing_physical_fields") or []),
             entry.get("possible_next_source"), 1 if entry.get("title_only_insufficient", True) else 0,
             1 if entry.get("physical_pack_missing", True) else 0, _now()),
        )
        self._db.commit()
        return rid

    def list_identifier_resolution(self, run_id: Optional[str] = None, limit: int = 2000) -> List[Dict[str, Any]]:
        if run_id:
            rows = self._db.execute(
                "SELECT * FROM costco_identifier_resolution_queue WHERE run_id=? ORDER BY created_at DESC LIMIT ?",
                (run_id, limit)).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM costco_identifier_resolution_queue ORDER BY created_at DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_pipeline_store(db=None) -> PipelineStore:
    return PipelineStore(db)