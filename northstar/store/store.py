"""Snapshot store + data-access layer (Phase 4).

- New, additive SQLite tables only (``snapshots``, ``retail_gates``) — no
  existing database is touched.
- Null-first: unknown values are stored as NULL / ``UNKNOWN`` (+ a reason),
  never coerced to 0 or an estimate. ``confidence`` stays NULL unless known.
- SIMULATED outputs can never be written (policy guard reused).
- Tenant isolation is enforced IN the data-access layer: every read and write
  requires a tenant id and filters on it.
- Retail gates: economics alone can never mark a row purchase-authorized —
  ``purchase_authorized`` is always 0 on insert and there is no setter here.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any, Optional

from northstar.policy.approvals import assert_snapshot_writable
from northstar.policy.errors import PolicyDenied

DATA_CLASSES = (
    "user-entered",
    "hypothetical",
    "historical",
    "cached",
    "provider-observation",
    "live-verified",
    "verified-doc",
)
FRESHNESS_STATES = ("OBSERVED", "CACHED", "UNKNOWN")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    freshness_status TEXT NOT NULL,
    unknown_reason TEXT,
    parser_version TEXT,
    content_hash TEXT,
    limitations TEXT,
    confidence REAL,
    data_class TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_tenant ON snapshots(tenant_id);
CREATE TABLE IF NOT EXISTS retail_gates (
    snapshot_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    resale_eligibility TEXT,
    exact_pack_match TEXT,
    cost_fee_basis TEXT,
    invoice_path TEXT,
    operator_approval TEXT,
    purchase_authorized INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id)
);
"""


class StoreError(RuntimeError):
    """Base store error."""


class StoreValidationError(StoreError):
    """Invalid input (rejected before any write)."""


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StoreValidationError(f"{field} is required")
    return value.strip()


class SnapshotStore:
    def __init__(self, db_path: str = ":memory:", *, clock=time.time) -> None:
        self.db_path = db_path
        self.clock = clock
        self._connection = sqlite3.connect(db_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(_SCHEMA)
        self._connection.commit()

    # -- snapshots -----------------------------------------------------------
    def put_snapshot(
        self,
        *,
        tenant_id: str,
        source: str,
        url: str,
        observed_at: str,
        data_class: str,
        snapshot_id: Optional[str] = None,
        freshness_status: str = "UNKNOWN",
        unknown_reason: Optional[str] = None,
        parser_version: Optional[str] = None,
        content_hash: Optional[str] = None,
        limitations: Optional[list] = None,
        confidence: Optional[float] = None,
    ) -> str:
        assert_snapshot_writable(data_class)  # SIMULATED → PolicyDenied
        if data_class not in DATA_CLASSES:
            raise StoreValidationError(f"unknown data_class: {data_class!r}")
        tenant_id = _require_text(tenant_id, "tenant_id")
        source = _require_text(source, "source")
        url = _require_text(url, "url")
        observed_at = _require_text(observed_at, "observed_at")
        if freshness_status not in FRESHNESS_STATES:
            raise StoreValidationError(f"unknown freshness_status: {freshness_status!r}")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError) as exc:
                raise StoreValidationError("confidence must be numeric or None") from exc
            if not 0.0 <= confidence <= 1.0:
                raise StoreValidationError("confidence must be within [0, 1] or None")
        if limitations is not None and not (
            isinstance(limitations, list) and all(isinstance(x, str) for x in limitations)
        ):
            raise StoreValidationError("limitations must be a list of strings or None")

        snap_id = snapshot_id or f"snap-{uuid.uuid4().hex[:12]}"
        self._connection.execute(
            "INSERT INTO snapshots (snapshot_id, tenant_id, source, url, observed_at,"
            " freshness_status, unknown_reason, parser_version, content_hash,"
            " limitations, confidence, data_class)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snap_id,
                tenant_id,
                source,
                url,
                observed_at,
                freshness_status,
                unknown_reason,
                parser_version,
                content_hash,
                json.dumps(limitations) if limitations is not None else None,
                confidence,
                data_class,
            ),
        )
        self._connection.commit()
        return snap_id

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        record = dict(row)
        if record.get("limitations") is not None:
            record["limitations"] = json.loads(record["limitations"])
        return record

    def get_snapshot(self, snapshot_id: str, *, tenant_id: str) -> Optional[dict]:
        row = self._connection.execute(
            "SELECT * FROM snapshots WHERE snapshot_id = ? AND tenant_id = ?",
            (snapshot_id, _require_text(tenant_id, "tenant_id")),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_snapshots(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        rows = self._connection.execute(
            "SELECT * FROM snapshots WHERE tenant_id = ?"
            " ORDER BY observed_at DESC, snapshot_id LIMIT ?",
            (_require_text(tenant_id, "tenant_id"), int(limit)),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # -- retail gates --------------------------------------------------------
    _GATE_FIELDS = (
        "resale_eligibility",
        "exact_pack_match",
        "cost_fee_basis",
        "invoice_path",
        "operator_approval",
    )

    def put_retail_gates(
        self, snapshot_id: str, *, tenant_id: str, **fields
    ) -> Optional[dict]:
        unknown = set(fields) - set(self._GATE_FIELDS)
        if unknown:
            raise StoreValidationError(f"unknown gate field(s): {sorted(unknown)}")
        # Tenant isolation: only the owning tenant may attach gates.
        if self.get_snapshot(snapshot_id, tenant_id=tenant_id) is None:
            return None
        values = {name: fields.get(name) for name in self._GATE_FIELDS}
        self._connection.execute(
            "INSERT OR REPLACE INTO retail_gates (snapshot_id, tenant_id,"
            " resale_eligibility, exact_pack_match, cost_fee_basis, invoice_path,"
            " operator_approval, purchase_authorized)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (
                snapshot_id,
                tenant_id,
                values["resale_eligibility"],
                values["exact_pack_match"],
                values["cost_fee_basis"],
                values["invoice_path"],
                values["operator_approval"],
            ),
        )
        self._connection.commit()
        return self.get_retail_gates(snapshot_id, tenant_id=tenant_id)

    def get_retail_gates(self, snapshot_id: str, *, tenant_id: str) -> Optional[dict]:
        row = self._connection.execute(
            "SELECT * FROM retail_gates WHERE snapshot_id = ? AND tenant_id = ?",
            (snapshot_id, _require_text(tenant_id, "tenant_id")),
        ).fetchone()
        return dict(row) if row else None

    def assert_not_purchase_authorized(self, snapshot_id: str, *, tenant_id: str) -> None:
        """Phase-4 guarantee: nothing is purchase-authorized from economics.

        There is intentionally NO code path that sets ``purchase_authorized``
        to a non-zero value in Phase 4 (operator approval only). This helper
        raises only if that invariant is somehow broken.
        """
        gates = self.get_retail_gates(snapshot_id, tenant_id=tenant_id)
        if gates is not None and int(gates.get("purchase_authorized", 0)) != 0:
            raise PolicyDenied(
                "purchase_authorization_not_available",
                "Phase 4 has no purchase-authorization path (operator approval only)",
            )

    def close(self) -> None:
        self._connection.close()
