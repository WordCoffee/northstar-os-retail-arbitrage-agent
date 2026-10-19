"""Lane telemetry (Thorn v5.0 §Dynamic Model Routing — the measurement half).

The plan asks for latency/entropy-based routing that "dynamically balances compute
costs and task complexity". A routing policy cannot be reasoned into existence: it
has to be measured. This module is the measurement half, and it deliberately
refuses to emit a policy before it has data.

    record(db, lane, ...)                 one measured run
    summary(db, lane=...)                 p50 / p95 / success rate + sample count
    recommend(db, candidates, ...)        a lane choice, ONLY when measured enough

Honesty contract
----------------
* Percentiles are nearest-rank over the actual recorded rows — not modelled.
* `recommend()` returns `available: False` with a reason until every candidate has
  at least MIN_SAMPLES runs. "No policy before data" is enforced in code, not in a
  comment.
* A lane that has never run is reported as `no_data`, never as fast.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

MIN_SAMPLES = 30
WINDOW_DEFAULT = 500

DDL = """
CREATE TABLE IF NOT EXISTS lane_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lane TEXT NOT NULL,
    task_class TEXT,
    latency_ms REAL NOT NULL,
    tokens INTEGER,
    tool_calls INTEGER DEFAULT 0,
    ok INTEGER NOT NULL,
    critique TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lane_telemetry_lane ON lane_telemetry(lane);
"""


def _db():
    import os
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from data_layer import get_db
    return get_db()


def _handle(db):
    """Normalise the three database-handle shapes this repository uses.

      * a raw sqlite3 connection   -> execute/executemany/commit (+ executescript)
      * data_layer.DataLayer       -> execute/executemany/commit (NO executescript)
      * data_layer.NorthstarDB     -> a container of table repositories; the real
        layer lives on ._layer

    Found by exercising the live turn path: `db.execute(...)` raised
    AttributeError on the NorthstarDB the chat router passes, which the caller's
    error handling turned into a silently dead producer.
    """
    if db is None:
        return None
    if hasattr(db, "execute"):
        return db
    layer = getattr(db, "_layer", None)
    if layer is not None and hasattr(layer, "execute"):
        return layer
    return None


def _statements(ddl: str) -> List[str]:
    return [s.strip() for s in ddl.split(";") if s.strip()]


def ensure_table(db) -> bool:
    """Create the table on any supported handle. False when the handle is unusable."""
    h = _handle(db)
    if h is None:
        return False
    fn = getattr(h, "executescript", None)
    if callable(fn):
        fn(DDL)
    else:
        for stmt in _statements(DDL):
            h.execute(stmt)
    h.commit()
    return True


def _query(db, sql: str, params: tuple) -> List[Dict[str, Any]]:
    """Rows as dicts, whatever the driver returns (sqlite3.Row, dict or tuple)."""
    cur = db.execute(sql, params)
    rows = cur.fetchall()
    desc = getattr(cur, "description", None)
    cols = [d[0] for d in desc] if desc else None
    out: List[Dict[str, Any]] = []
    for r in rows:
        if isinstance(r, dict):
            out.append(dict(r))
            continue
        try:
            out.append(dict(r))
        except Exception:  # noqa: BLE001 - a plain tuple row
            out.append({c: v for c, v in zip(cols or (), r)} if cols else {"value": r})
    return out


def _percentile(sorted_values: Sequence[float], pct: float) -> Optional[float]:
    """Nearest-rank percentile over already-sorted values."""
    if not sorted_values:
        return None
    k = max(1, min(len(sorted_values), int(round(pct / 100.0 * len(sorted_values) + 0.5))))
    return float(sorted_values[k - 1])


def record(db, lane: str, *, latency_ms: float, ok: bool = True,
           tokens: Optional[int] = None, tool_calls: int = 0,
           task_class: Optional[str] = None, critique: Optional[str] = None) -> Dict[str, Any]:
    """Record one measured run on one lane."""
    if not lane:
        return {"ok": False, "error": "a lane name is required"}
    if latency_ms is None or latency_ms < 0:
        return {"ok": False, "error": "latency_ms must be a non-negative measurement"}
    h = _handle(db)
    if h is None:
        return {"ok": False,
                "error": (f"unsupported db handle ({type(db).__name__}): expected "
                          "execute()/commit() or a NorthstarDB container")}
    ensure_table(h)
    h.execute(
        "INSERT INTO lane_telemetry (lane, task_class, latency_ms, tokens, tool_calls, ok, critique, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (lane, task_class, float(latency_ms), tokens, int(tool_calls), 1 if ok else 0,
         critique, datetime.now(timezone.utc).isoformat()),
    )
    h.commit()
    return {"ok": True, "lane": lane}


def summary(db, *, lane: Optional[str] = None, window: int = WINDOW_DEFAULT) -> Dict[str, Any]:
    """Measured aggregates for one lane, or for every lane."""
    h = _handle(db)
    if h is None:
        return {"lanes": {}, "window": window, "min_samples": MIN_SAMPLES,
                "error": f"unsupported db handle ({type(db).__name__})",
                "summary": "no usable database handle; nothing was measured"}
    ensure_table(h)
    sql = "SELECT lane, latency_ms, ok FROM lane_telemetry"
    params: List[Any] = []
    if lane:
        sql += " WHERE lane = ?"
        params.append(lane)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, window))
    rows = _query(h, sql, tuple(params))

    lanes: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        lanes.setdefault(r["lane"], []).append(r)

    out: Dict[str, Any] = {}
    for name, rs in sorted(lanes.items()):
        lats = sorted(float(r["latency_ms"]) for r in rs)
        okc = sum(1 for r in rs if r["ok"])
        out[name] = {
            "samples": len(rs),
            "p50_latency_ms": _percentile(lats, 50),
            "p95_latency_ms": _percentile(lats, 95),
            "success_rate": round(okc / len(rs), 4) if rs else None,
            "measured": len(rs) >= MIN_SAMPLES,
        }
    return {
        "lanes": out,
        "window": window,
        "min_samples": MIN_SAMPLES,
        "summary": (f"{len(out)} lane(s) with recorded runs"
                    + ("" if lane else f"; {sum(v['samples'] for v in out.values())} run(s) measured")),
        "note": "Percentiles are nearest-rank over recorded rows; no modelling, no projection.",
    }


def recommend(db, candidates: Iterable[str], *, task_class: Optional[str] = None,
              min_samples: int = MIN_SAMPLES) -> Dict[str, Any]:
    """Choose a lane from MEASURED evidence only. Refuses before there is evidence."""
    cands = [c for c in candidates if c]
    if not cands:
        return {"available": False, "reason": "no candidate lanes were supplied", "lanes": {}}
    stats = summary(db)["lanes"]
    have = {c: stats.get(c) for c in cands}
    missing = [c for c in cands if not have.get(c)]
    thin = [c for c, s in have.items() if s and s["samples"] < min_samples]

    if missing or thin:
        detail = []
        if missing:
            detail.append("never run: " + ", ".join(missing))
        if thin:
            detail.append("too few samples (<%d): %s" % (
                min_samples, ", ".join(f"{c}={have[c]['samples']}" for c in thin)))
        return {
            "available": False,
            "reason": ("No routing policy is emitted before there is evidence — " + "; ".join(detail)),
            "lanes": {k: v for k, v in have.items()},
            "min_samples": min_samples,
        }

    ranked = sorted(
        cands,
        key=lambda c: (
            -(have[c]["success_rate"] or 0.0),
            have[c]["p95_latency_ms"] if have[c]["p95_latency_ms"] is not None else float("inf"),
        ),
    )
    return {
        "available": True,
        "chosen": ranked[0],
        "ranked": ranked,
        "basis": ("measured success rate first, then measured p95 latency; "
                  + (f"task_class filter '{task_class}' is recorded but not yet used to "
                     "select — that needs per-class samples." if task_class else
                     "no task_class filter applied.")),
        "lanes": {k: have[k] for k in cands},
        "min_samples": min_samples,
    }
