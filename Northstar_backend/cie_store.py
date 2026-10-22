"""Continuous Improvement Engine (CIE) — storage and stop switch.

Isolated by design: all CIE state lives under ``state/improvement`` in its own
SQLite database, so the engine can be snapshotted, rolled back, or deleted
without touching the product database.

Set ``NORTHSTAR_CIE_ROOT`` to point the whole engine at another directory
(tests use a temp dir; nothing leaks into the repo).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1


def root() -> Path:
    return Path(os.environ.get("NORTHSTAR_CIE_ROOT") or REPO_ROOT)


def state_dir() -> Path:
    p = root() / "state" / "improvement"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return state_dir() / "cie.db"


def stop_path() -> Path:
    return state_dir() / "STOP"


def report_dir() -> Path:
    p = root() / "reports" / "improvement" / "cycles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def new_cycle_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


# ── stop switch ─────────────────────────────────────────────────────────────

def is_stopped() -> bool:
    return stop_path().exists()


def set_stopped(stopped: bool, reason: str = "") -> Dict[str, Any]:
    p = stop_path()
    if stopped:
        p.write_text(json.dumps({"stopped_at": now(), "reason": reason}), encoding="utf-8")
    elif p.exists():
        p.unlink()
    return {"stopped": is_stopped(), "reason": reason}


# ── database ────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    message_id TEXT,
    session_id TEXT,
    verdict TEXT NOT NULL CHECK (verdict IN ('up','down','corrected')),
    note TEXT DEFAULT '',
    mode TEXT DEFAULT '',
    pack_version TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS gaps (
    gap_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    question TEXT NOT NULL,
    evidence TEXT DEFAULT '[]',
    frequency INTEGER DEFAULT 0,
    score REAL DEFAULT 0,
    status TEXT DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cycles (
    cycle_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    base_commit TEXT DEFAULT '',
    snapshot TEXT DEFAULT '',
    gaps INTEGER DEFAULT 0,
    researched INTEGER DEFAULT 0,
    authored INTEGER DEFAULT 0,
    promoted INTEGER DEFAULT 0,
    discarded INTEGER DEFAULT 0,
    report_path TEXT DEFAULT '',
    rollback_cmd TEXT DEFAULT '',
    detail TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS evals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT,
    suite TEXT NOT NULL,
    score REAL NOT NULL,
    detail TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS canary (
    turn_id TEXT PRIMARY KEY,
    pack_version TEXT NOT NULL,
    bucket TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gaps_status ON gaps(status, score DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(_SCHEMA)
        conn.execute("PRAGMA user_version=%d" % SCHEMA_VERSION)
        conn.commit()
    finally:
        conn.close()


# ── feedback ────────────────────────────────────────────────────────────────

def add_feedback(*, verdict: str, message_id: str = "", session_id: str = "",
                 note: str = "", mode: str = "", pack_version: str = "") -> int:
    if verdict not in ("up", "down", "corrected"):
        raise ValueError("verdict must be up|down|corrected")
    init_db()
    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO feedback(created_at,message_id,session_id,verdict,note,mode,pack_version)"
            " VALUES(?,?,?,?,?,?,?)",
            (now(), message_id, session_id, verdict, note[:2000], mode, pack_version))
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_feedback(limit: int = 100) -> List[Dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def negative_feedback(since: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        q = ("SELECT * FROM feedback WHERE verdict IN ('down','corrected')"
             + (" AND created_at >= ?" if since else "")
             + " ORDER BY id DESC LIMIT ?")
        args = (since, int(limit)) if since else (int(limit),)
        return [dict(r) for r in conn.execute(q, args).fetchall()]
    finally:
        conn.close()


# ── gaps ────────────────────────────────────────────────────────────────────

def upsert_gap(*, gap_id: str, domain: str, question: str,
               evidence: Optional[Iterable[Any]] = None,
               frequency: int = 1, score: float = 0.0) -> None:
    init_db()
    ts = now()
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO gaps(gap_id,domain,question,evidence,frequency,score,status,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,'open',?,?)"
            " ON CONFLICT(gap_id) DO UPDATE SET"
            " frequency=frequency+excluded.frequency,"
            " score=MAX(score,excluded.score), updated_at=excluded.updated_at",
            (gap_id, domain, question[:2000],
             json.dumps(list(evidence or []), ensure_ascii=False)[:4000],
             int(frequency), float(score), ts, ts))
        conn.commit()
    finally:
        conn.close()


def list_gaps(status: str = "open", limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM gaps WHERE status=? ORDER BY score DESC, frequency DESC"
            " LIMIT ?", (status, int(limit))).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["evidence"] = json.loads(d.get("evidence") or "[]")
            except ValueError:
                d["evidence"] = []
            out.append(d)
        return out
    finally:
        conn.close()


def close_gap(gap_id: str, status: str = "resolved") -> None:
    init_db()
    conn = connect()
    try:
        conn.execute("UPDATE gaps SET status=?, updated_at=? WHERE gap_id=?",
                     (status, now(), gap_id))
        conn.commit()
    finally:
        conn.close()


# ── cycles ──────────────────────────────────────────────────────────────────

def start_cycle(cycle_id: str, base_commit: str = "", snapshot: str = "") -> None:
    init_db()
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO cycles(cycle_id,started_at,status,base_commit,snapshot)"
            " VALUES(?,?,'running',?,?)",
            (cycle_id, now(), base_commit, snapshot))
        conn.commit()
    finally:
        conn.close()


def finish_cycle(cycle_id: str, **fields: Any) -> None:
    init_db()
    allowed = {"status", "gaps", "researched", "authored", "promoted", "discarded",
               "report_path", "rollback_cmd", "detail"}
    sets, args = ["finished_at=?"], [now()]
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "detail" and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        sets.append(f"{key}=?")
        args.append(value)
    args.append(cycle_id)
    conn = connect()
    try:
        conn.execute(f"UPDATE cycles SET {', '.join(sets)} WHERE cycle_id=?", args)
        conn.commit()
    finally:
        conn.close()


def list_cycles(limit: int = 20) -> List[Dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM cycles ORDER BY started_at DESC LIMIT ?", (int(limit),)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["detail"] = json.loads(d.get("detail") or "{}")
            except ValueError:
                d["detail"] = {}
            out.append(d)
        return out
    finally:
        conn.close()


def get_cycle(cycle_id: str) -> Optional[Dict[str, Any]]:
    for c in list_cycles(500):
        if c["cycle_id"] == cycle_id:
            return c
    return None


# ── evals ───────────────────────────────────────────────────────────────────

def add_eval(cycle_id: str, suite: str, score: float, detail: Any = None) -> None:
    init_db()
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO evals(cycle_id,suite,score,detail,created_at) VALUES(?,?,?,?,?)",
            (cycle_id, suite, float(score),
             json.dumps(detail or {}, ensure_ascii=False)[:20000], now()))
        conn.commit()
    finally:
        conn.close()


def list_evals(limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM evals ORDER BY id DESC LIMIT ?",
                            (int(limit),)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def status() -> Dict[str, Any]:
    init_db()
    cycles = list_cycles(5)
    gaps = list_gaps("open", 1000)
    return {
        "stopped": is_stopped(),
        "cycle_count": len(list_cycles(1000)),
        "open_gaps": len(gaps),
        "last_cycle": cycles[0] if cycles else None,
        "recent_cycles": cycles,
        "db": str(db_path()),
    }
