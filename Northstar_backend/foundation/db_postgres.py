"""PostgreSQL backend for the foundation store (Phase 1C-02 validation).

Additive: the SQLite ``FoundationDB`` remains the local-dev/default engine; this
backend is used only when ``FOUNDATION_DB_URL`` is configured (e.g. for the
ephemeral PostgreSQL validation, or a future staging database).

The backend exposes the SAME method surface the repositories use
(insert/get/upsert/list/count/close) plus a ``.conn`` whose ``execute`` accepts
the repositories' ``?``-placeholders and translates them to psycopg ``%s``.

Read normalization: JSONB -> JSON string, TIMESTAMPTZ -> ISO string, so the
repositories observe SQLite-equivalent Python types regardless of backend.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Optional


def _ser_pg(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, datetime):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return value


class _Conn:
    """Adapter exposing the subset of the sqlite3 connection used by repos."""

    def __init__(self, raw) -> None:
        self._raw = raw

    def execute(self, sql: str, params: Iterable = ()):
        cur = self._raw.cursor()
        try:
            cur.execute(sql.replace("?", "%s"), tuple(params))
            return cur
        except Exception:
            self._raw.rollback()
            raise

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()


class PostgresFoundationDB:
    backend = "postgresql"

    def __init__(self, dsn: str, *, schema: bool = False) -> None:
        import psycopg
        from psycopg.rows import dict_row
        self.dsn = dsn
        self._raw = psycopg.connect(dsn, row_factory=dict_row, autocommit=False)
        self.conn = _Conn(self._raw)
        self.path = dsn  # semantics: repositories never treat this as a file

    # -- introspection (used by the validation harness / dialect assertions) --
    def dialect(self) -> str:
        cur = self._raw.cursor()
        cur.execute("SELECT version()")
        return "postgresql"

    def server_info(self) -> dict:
        cur = self._raw.cursor()
        cur.execute("SELECT version() AS v, current_database() AS db, "
                    "inet_server_addr()::text AS host, current_user AS usr, "
                    "current_setting('server_version_num') AS num")
        r = cur.fetchone()
        return {"version": r["v"], "database": r["db"], "server_addr": r["host"],
                "user": r["usr"], "server_version_num": r["num"]}

    # -- normalization --------------------------------------------------------
    @staticmethod
    def _normalize(row: Optional[dict]) -> Optional[dict]:
        if row is None:
            return None
        out = {}
        for k, v in row.items():
            if isinstance(v, (dict, list)):
                out[k] = json.dumps(v, default=str)
            elif isinstance(v, datetime):
                out[k] = v.isoformat()
            else:
                out[k] = v
        return out

    # -- generic helpers (mirror FoundationDB) --------------------------------
    def insert(self, table: str, row: dict) -> None:
        cols = list(row.keys())
        ph = ",".join(["%s"] * len(cols))
        try:
            self._raw.execute(
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph})",
                [_ser_pg(row[c]) for c in cols])
            self._raw.commit()
        except Exception:
            # A failed statement aborts the transaction; roll back so the
            # connection stays usable (SQLite semantics parity).
            self._raw.rollback()
            raise

    def insert_ignore(self, table: str, row: dict, conflict_cols: Iterable[str] = ("id",)) -> bool:
        """Idempotent insert: no-op on PK conflict (ON CONFLICT DO NOTHING)."""
        cols = list(row.keys())
        ph = ",".join(["%s"] * len(cols))
        conflict = ", ".join(conflict_cols)
        try:
            cur = self._raw.execute(
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph}) "
                f"ON CONFLICT ({conflict}) DO NOTHING RETURNING 1",
                [_ser_pg(row[c]) for c in cols])
            self._raw.commit()
            return cur.fetchone() is not None
        except Exception:
            self._raw.rollback()
            raise

    def insert_no_commit(self, table: str, row: dict) -> None:
        """INSERT inside the caller's transaction (no commit). The caller owns
        commit/rollback — used for atomic multi-write operations."""
        cols = list(row.keys())
        ph = ",".join(["%s"] * len(cols))
        self._raw.execute(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph})",
            [_ser_pg(row[c]) for c in cols])

    def upsert(self, table: str, row: dict, pk_cols: Iterable[str]) -> None:
        pk = list(pk_cols)
        existing = self.get(table, {p: row[p] for p in pk})
        if existing:
            sets = [c for c in row.keys() if c not in pk]
            if sets:
                set_sql = ",".join(f"{c}=%s" for c in sets)
                where = " AND ".join(f"{p}=%s" for p in pk)
                try:
                    self._raw.execute(
                        f"UPDATE {table} SET {set_sql} WHERE {where}",
                        [_ser_pg(row[c]) for c in sets] + [_ser_pg(row[p]) for p in pk])
                    self._raw.commit()
                except Exception:
                    self._raw.rollback()
                    raise
        else:
            self.insert(table, row)

    def get(self, table: str, where: dict) -> Optional[dict]:
        clause = " AND ".join(f"{k}=%s" for k in where)
        try:
            cur = self._raw.execute(
                f"SELECT * FROM {table} WHERE {clause}",
                [_ser_pg(v) for v in where.values()])
            return self._normalize(cur.fetchone())
        except Exception:
            self._raw.rollback()
            raise

    def list(self, table: str, where: Optional[dict] = None, order_by: Optional[str] = None,
             limit: Optional[int] = None, offset: int = 0) -> list[dict]:
        sql = f"SELECT * FROM {table}"
        params: list[Any] = []
        if where:
            sql += " WHERE " + " AND ".join(f"{k}=%s" for k in where)
            params += [_ser_pg(v) for v in where.values()]
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params += [limit, offset]
        try:
            cur = self._raw.execute(sql, params)
            return [self._normalize(r) for r in cur.fetchall()]
        except Exception:
            self._raw.rollback()
            raise

    def count(self, table: str) -> int:
        try:
            cur = self._raw.execute(f"SELECT COUNT(*) AS c FROM {table}")
            return int(cur.fetchone()["c"])
        except Exception:
            self._raw.rollback()
            raise

    def table_counts(self) -> dict:
        cur = self._raw.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1")
        return {r["table_name"]: self.count(r["table_name"]) for r in cur.fetchall()}

    # -- migration application / introspection ---------------------------------

    def apply_sql(self, sql: str) -> dict:
        """Execute a multi-statement SQL script inside one transaction.

        Safe for the disposable validation harness. Never points at
        staging/production (guardrails live in the caller).
        """
        self._raw.execute("BEGIN")
        try:
            self._raw.execute(sql)
            self._raw.commit()
        except Exception:
            self._raw.rollback()
            raise
        return {"applied": True}

    def apply_sql_file(self, path: str) -> dict:
        with open(path, encoding="utf-8") as fh:
            return self.apply_sql(fh.read())

    def drop_all_foundation_tables(self, tables: Iterable[str]) -> None:
        """Drop ONLY the given tables (caller supplies the foundation list)."""
        self._raw.execute("BEGIN")
        try:
            for t in tables:
                self._raw.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')
            self._raw.commit()
        except Exception:
            self._raw.rollback()
            raise

    def tables_columns(self) -> dict[str, list[str]]:
        cur = self._raw.execute(
            "SELECT c.table_name, c.column_name "
            "FROM information_schema.columns c "
            "JOIN information_schema.tables t "
            "  ON t.table_schema = c.table_schema AND t.table_name = c.table_name "
            "WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE' "
            "ORDER BY c.table_name, c.column_name")
        out: dict[str, list[str]] = {}
        for r in cur.fetchall():
            out.setdefault(r["table_name"], []).append(r["column_name"])
        return out

    def constraints(self) -> dict[str, list[str]]:
        cur = self._raw.execute(
            "SELECT conrelid::regclass::text AS tbl, conname, contype "
            "FROM pg_constraint "
            "WHERE connamespace = 'public'::regnamespace "
            "ORDER BY tbl, conname")
        out: dict[str, list[str]] = {}
        for r in cur.fetchall():
            out.setdefault(r["tbl"], []).append(f"{r['contype']}:{r['conname']}")
        return out

    def indexes(self) -> dict[str, list[str]]:
        cur = self._raw.execute(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' ORDER BY tablename, indexname")
        out: dict[str, list[str]] = {}
        for r in cur.fetchall():
            out.setdefault(r["tablename"], []).append(r["indexname"])
        return out

    def schema_fingerprint(self) -> dict:
        """Deterministic fingerprint of the current schema for migration
        apply/rollback/reapply comparison."""
        import hashlib

        def _digest(payload: dict) -> str:
            return hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

        tables = self.tables_columns()
        constraints = self.constraints()
        indexes = self.indexes()
        return {
            "tables_columns_hash": _digest(tables),
            "constraints_hash": _digest(constraints),
            "indexes_hash": _digest(indexes),
            "table_count": len(tables),
            "column_count": sum(len(c) for c in tables.values()),
            "tables": tables,
            "constraints": constraints,
            "indexes": indexes,
        }

    # -- atomic claim (1C-04/B05) ------------------------------------------
    # PostgreSQL: SELECT ... FOR UPDATE SKIP LOCKED inside a CTE feeding an
    # UPDATE ... RETURNING — one atomic statement, no race window. The claimed
    # row's state change is the lock: exactly one worker observes queued->leased.
    def atomic_claim_job(self, *, worker_id: str, organization_id: str,
                         lease_seconds: int, now_iso: str, limit: int = 1) -> list[dict]:
        sql = (
            "WITH candidate AS ("
            "  SELECT jr.id FROM job_runs jr "
            "  JOIN job_requests jq ON jq.id = jr.job_request_id "
            "  WHERE jr.state = 'queued' AND jq.organization_id = %s "
            "  AND (jr.scheduled_time IS NULL OR jr.scheduled_time <= (%s)::timestamptz) "
            "  ORDER BY jr.priority ASC, jr.created_at ASC LIMIT %s "
            "  FOR UPDATE SKIP LOCKED"
            ") "
            "UPDATE job_runs SET state='leased', lease_owner=%s, "
            "lease_expiration=(%s)::timestamptz "
            "FROM candidate WHERE job_runs.id = candidate.id "
            "RETURNING job_runs.*"
        )
        from datetime import datetime, timedelta, timezone
        exp = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        cur = self._raw.execute(sql, [organization_id, now_iso, limit,
                                      worker_id, exp])
        self._raw.commit()
        rows = [self._normalize(r) for r in cur.fetchall()]
        for row in rows:
            row["state"] = "leased"
            row["lease_owner"] = worker_id
            row["lease_expiration"] = exp
        return rows

    def release_lease(self, run_id: str, worker_id: str,
                      new_state: str = "queued", now_iso: Optional[str] = None) -> int:
        cur = self._raw.execute(
            "UPDATE job_runs SET state=%s, lease_owner=NULL, lease_expiration=NULL "
            "WHERE id=%s AND lease_owner=%s",
            [new_state, run_id, worker_id])
        self._raw.commit()
        return cur.rowcount

    def expire_stale_leases(self, now_iso: str) -> int:
        cur = self._raw.execute(
            "UPDATE job_runs SET state='expired' WHERE state='leased' "
            "AND lease_expiration IS NOT NULL AND lease_expiration < (%s)::timestamptz",
            [now_iso])
        self._raw.commit()
        return cur.rowcount

    def close(self) -> None:
        self._raw.close()