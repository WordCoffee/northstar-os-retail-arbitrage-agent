"""Local screen memory — a searchable, local record of what was on screen.

The point is the question "what was that error an hour ago?" without a cloud
service: every sampled frame's OCR text (already redacted by `local_screen`) is
written to a local SQLite file with its timestamp, the active window and, when a
look was taken, the vision model's scene note.

Rules:

* **Local file only.** Default database lives beside the backend in
  `data/local_screen/memory.db`; the path is overridable with LOCAL_SCREEN_DB.
* **Consecutive duplicates collapse.** The same frame hash twice in a row is one
  row with `seen_count` incremented - idle time does not fill the file.
* **Search is FTS5 when available**, with a LIKE fallback that is honest about
  being a substring match. A query that finds nothing says zero, it never
  guesses.
* **Purge is explicit.** `purge(all=True)` or `purge(before=...)` only; nothing
  ages out silently.

    python Northstar_backend/local_screen_memory.py --stats
    python Northstar_backend/local_screen_memory.py --search "stack trace"
    python Northstar_backend/local_screen_memory.py --recent 10
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

DEFAULT_DB = Path(__file__).resolve().parent / "data" / "local_screen" / "memory.db"
#: Words that FTS5 treats as syntax; a raw user query must not become a parse error.
_QUERY_NOISE = re.compile(r'["\*\^:\-\(\)]')


def db_path() -> Path:
    env = os.environ.get("LOCAL_SCREEN_DB")
    return Path(env) if env else DEFAULT_DB


def _connect(path: Optional[Path] = None) -> sqlite3.Connection:
    target = Path(path or db_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _migrate(conn)
    return conn


@contextmanager
def _session(path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """A short-lived connection that is always closed.

    `with sqlite3.connect(...)` commits but does not close, which leaks handles in
    a watcher that samples every few seconds. This wrapper closes.
    """
    conn = _connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS frames (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at  REAL    NOT NULL,
            sha1         TEXT    NOT NULL,
            process      TEXT    DEFAULT '',
            title        TEXT    DEFAULT '',
            text         TEXT    DEFAULT '',
            line_count   INTEGER DEFAULT 0,
            ocr_seconds  REAL,
            scene        TEXT    DEFAULT '',
            seen_count   INTEGER DEFAULT 1,
            thumb        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_frames_time ON frames(captured_at);
        CREATE INDEX IF NOT EXISTS idx_frames_sha  ON frames(sha1);
        """
    )
    try:
        conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS frames_fts USING fts5(
                text, title, process, content='frames', content_rowid='id'
            );
            CREATE TRIGGER IF NOT EXISTS frames_ai AFTER INSERT ON frames BEGIN
                INSERT INTO frames_fts(rowid, text, title, process)
                VALUES (new.id, new.text, new.title, new.process);
            END;
            CREATE TRIGGER IF NOT EXISTS frames_ad AFTER DELETE ON frames BEGIN
                INSERT INTO frames_fts(frames_fts, rowid, text, title, process)
                VALUES ('delete', old.id, old.text, old.title, old.process);
            END;
            CREATE TRIGGER IF NOT EXISTS frames_au AFTER UPDATE ON frames BEGIN
                INSERT INTO frames_fts(frames_fts, rowid, text, title, process)
                VALUES ('delete', old.id, old.text, old.title, old.process);
                INSERT INTO frames_fts(rowid, text, title, process)
                VALUES (new.id, new.text, new.title, new.process);
            END;
            """
        )
        conn.execute("INSERT INTO frames_fts(frames_fts) VALUES('rebuild')")
        conn.commit()
    except sqlite3.OperationalError:  # noqa: BLE001 - a missing FTS5 table is reported by stats, and search falls back to LIKE
        # FTS5 absent: search falls back to LIKE. Recorded in stats, not hidden.
        conn.execute("PRAGMA user_version = 1")
        conn.commit()


def fts_available(path: Optional[Path] = None) -> bool:
    with _session(path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='frames_fts'"
        ).fetchone()
        return bool(row)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    if data.get("captured_at"):
        data["at"] = time.strftime("%Y-%m-%d %H:%M:%S",
                                   time.localtime(float(data["captured_at"])))
    data.pop("thumb", None)  # a thumbnail path is served, not inlined in lists
    return data


def record(*, captured_at: Optional[float] = None, sha1: str, text: str = "",
           process: str = "", title: str = "", line_count: int = 0,
           ocr_seconds: Optional[float] = None, scene: str = "",
           thumb: Optional[str] = None, path: Optional[Path] = None) -> Dict[str, Any]:
    """Store one frame. A repeat of the newest frame hash collapses into it."""
    if not sha1:
        raise ValueError("sha1 is required")
    now = float(captured_at if captured_at is not None else time.time())
    with _session(path) as conn:
        latest = conn.execute(
            "SELECT id, sha1, seen_count FROM frames ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest and latest["sha1"] == sha1:
            conn.execute(
                "UPDATE frames SET seen_count = seen_count + 1, captured_at = ? "
                "WHERE id = ?", (now, latest["id"]),
            )
            conn.commit()
            return {"id": int(latest["id"]), "duplicate": True,
                    "seen_count": int(latest["seen_count"]) + 1}
        cur = conn.execute(
            "INSERT INTO frames (captured_at, sha1, process, title, text, line_count,"
            " ocr_seconds, scene, seen_count, thumb) VALUES (?,?,?,?,?,?,?,?,1,?)",
            (now, sha1, process or "", title or "", text or "", int(line_count or 0),
             ocr_seconds, scene or "", thumb),
        )
        conn.commit()
        return {"id": int(cur.lastrowid), "duplicate": False, "seen_count": 1}


def _fts_query(raw: str) -> str:
    """Turn a phrase into a safe FTS5 AND-of-terms query."""
    terms = [t for t in _QUERY_NOISE.sub(" ", raw or "").split() if t]
    return " AND ".join(f'"{t}"' for t in terms[:12])


def search(query: str, *, limit: int = 20, since_minutes: Optional[float] = None,
           path: Optional[Path] = None) -> Dict[str, Any]:
    """Find frames whose text/title/process contains every term of `query`."""
    limit = max(1, min(int(limit), 200))
    since = time.time() - float(since_minutes) * 60 if since_minutes else None
    with _session(path) as conn:
        rows: List[sqlite3.Row] = []
        mode = "fts5"
        if query and query.strip():
            try:
                sql = ("SELECT f.* FROM frames_fts JOIN frames f ON f.id = frames_fts.rowid "
                       "WHERE frames_fts MATCH ?")
                params: List[Any] = [_fts_query(query)]
                if since:
                    sql += " AND f.captured_at >= ?"
                    params.append(since)
                sql += " ORDER BY f.captured_at DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError:  # noqa: BLE001 - an FTS parse failure falls back to LIKE and labels the mode
                mode = "like"
                sql = ("SELECT * FROM frames WHERE (text LIKE ? OR title LIKE ? OR process LIKE ?)")
                like = f"%{query.strip()}%"
                params = [like, like, like]
                if since:
                    sql += " AND captured_at >= ?"
                    params.append(since)
                sql += " ORDER BY captured_at DESC LIMIT ?"
                params.append(limit)
                rows = list(conn.execute(sql, params).fetchall())
        else:
            mode = "recent"
            sql = "SELECT * FROM frames"
            params = []
            if since:
                sql += " WHERE captured_at >= ?"
                params.append(since)
            sql += " ORDER BY captured_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
    return {"ok": True, "mode": mode, "query": query, "count": len(rows),
            "results": [_row_to_dict(r) for r in rows]}


def recent(*, limit: int = 20, since_minutes: Optional[float] = None,
           path: Optional[Path] = None) -> Dict[str, Any]:
    return search("", limit=limit, since_minutes=since_minutes, path=path)


def latest_meaningful(*, max_age_minutes: float = 10.0,
                      path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Newest frame with any text, if it is recent enough to answer from."""
    cutoff = time.time() - float(max_age_minutes) * 60
    with _session(path) as conn:
        row = conn.execute(
            "SELECT * FROM frames WHERE captured_at >= ? AND length(text) > 0 "
            "ORDER BY id DESC LIMIT 1", (cutoff,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def stats(path: Optional[Path] = None) -> Dict[str, Any]:
    target = Path(path or db_path())
    with _session(target) as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM frames").fetchone()["n"]
        span = conn.execute(
            "SELECT MIN(captured_at) AS first, MAX(captured_at) AS last, "
            "SUM(seen_count) AS samples FROM frames"
        ).fetchone()
        thumbs = conn.execute(
            "SELECT COUNT(*) AS n FROM frames WHERE thumb IS NOT NULL"
        ).fetchone()["n"]
        fts = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='frames_fts'"
        ).fetchone()
    size = target.stat().st_size if target.is_file() else 0
    return {
        "ok": True,
        "db": str(target),
        "bytes": size,
        "frames": int(total or 0),
        "samples": int(span["samples"] or 0) if span else 0,
        "first_at": (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(span["first"]))
                     if span and span["first"] else None),
        "last_at": (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(span["last"]))
                    if span and span["last"] else None),
        "thumbs": int(thumbs or 0),
        "search": "fts5" if fts else "like",
    }


def purge(*, before: Optional[float] = None, all: bool = False,
          path: Optional[Path] = None) -> Dict[str, Any]:
    """Delete stored frames. Requires an explicit scope - never a default."""
    if not all and before is None:
        raise ValueError("purge needs all=True or an explicit before= timestamp")
    with _session(path) as conn:
        if all:
            ids = [r["id"] for r in conn.execute("SELECT id FROM frames").fetchall()]
            conn.execute("DELETE FROM frames")
        else:
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM frames WHERE captured_at < ?", (float(before),)).fetchall()]
            conn.execute("DELETE FROM frames WHERE captured_at < ?", (float(before),))
        conn.commit()
        try:
            conn.execute("INSERT INTO frames_fts(frames_fts) VALUES('optimize')")
            conn.commit()
        except sqlite3.OperationalError:  # noqa: BLE001 - an FTS optimize failure does not undo a completed purge
            pass
    return {"ok": True, "deleted": len(ids)}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Local screen memory")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--recent", type=int, default=None)
    ap.add_argument("--search", default=None)
    ap.add_argument("--minutes", type=float, default=None)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--purge-all", action="store_true")
    ap.add_argument("--purge-hours", type=float, default=None)
    args = ap.parse_args(argv)

    if args.stats:
        print(json.dumps(stats(), indent=2))
        return 0
    if args.purge_all or args.purge_hours is not None:
        before = time.time() - args.purge_hours * 3600 if args.purge_hours else None
        print(json.dumps(purge(all=args.purge_all, before=before), indent=2))
        return 0
    if args.search is not None:
        out = search(args.search, limit=args.limit, since_minutes=args.minutes)
    elif args.recent is not None:
        out = recent(limit=args.recent or args.limit, since_minutes=args.minutes)
    else:
        ap.print_help()
        return 0
    print(json.dumps({**out, "results": out["results"]}, indent=2, ensure_ascii=False)[:8000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
