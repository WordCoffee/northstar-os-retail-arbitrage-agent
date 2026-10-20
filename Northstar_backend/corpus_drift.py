"""Embeddings drift engine (V4.1 §5.4) — a local-only semantic lane over the corpus.

Upgrades the V3 S8 curated corpus from deterministic keyword search to a real
vector lane, entirely on the operator's own machine:

  • Embeddings come from the LOCAL Ollama runner (`qwen3-embedding:0.6b`, 1024-d).
    No network beyond localhost, no paid service, no scraping.
  • Vectors live in a `sqlite-vec` `vec0` virtual table stored beside the corpus
    index; search is cosine nearest-neighbour.
  • Drift is MEASURED, never predicted: the engine reports the cosine distance
    between the current corpus embedding centroid and the centroid of historical
    SQP query embeddings, and records a snapshot history. It never claims a trend,
    a forecast, or a cause.

Honesty boundaries (do not loosen these):
  • Vector search is an ADDITIONAL mode. The keyword search in the corpus router
    is unchanged and stays the deterministic default.
  • If the Ollama embedding lane is unavailable for ANY reason, every
    embedding-dependent surface degrades to an explicit ``available: False`` with
    the real reason. A vector is NEVER fabricated and never zero-filled.
  • ``sqlite-vec`` is SQLite-only. On the Postgres backend this lane is simply
    absent; the caller is told so rather than handed an empty success.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import struct
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

EMBED_MODEL = "qwen3-embedding:0.6b"
EMBED_DIM = 1024
OLLAMA_EMBED_URL = os.environ.get(
    "NORTHSTAR_EMBED_URL", "http://127.0.0.1:11434/api/embeddings")
_EMBED_TIMEOUT = float(os.environ.get("NORTHSTAR_EMBED_TIMEOUT", "120"))
_EMBED_TEXT_MAX = int(os.environ.get("NORTHSTAR_EMBED_TEXT_MAX", "2000"))
# Measured on this box: left to its own devices Ollama loaded the 0.6B embed
# model at its 32k default, holding 5.8 GB of the 16 GB card and (with
# OLLAMA_MAX_LOADED_MODELS=1) evicting the 27B brain, so the next chat turn paid
# a ~7 s cold reload. The lane only ever sends _EMBED_TEXT_MAX chars, so a small
# window keeps it around 0.5 GB, and a short keep_alive lets it go on its own.
_EMBED_NUM_CTX = int(os.environ.get("NORTHSTAR_EMBED_NUM_CTX", "2048"))
_EMBED_KEEP_ALIVE = os.environ.get("NORTHSTAR_EMBED_KEEP_ALIVE", "2m")

VEC_TABLE = "corpus_vec"
META_TABLE = "corpus_vector_meta"
SNAP_TABLE = "corpus_drift_snapshots"

# Vector-space "sources": the curated corpus itself and historical SQP queries.
SRC_CORPUS = "corpus"
SRC_SQP = "sqp"


class EmbeddingUnavailable(RuntimeError):
    """The local embedding lane could not produce a vector. Never faked."""


# ---------------------------------------------------------------------------
# float32 vector <-> blob (the sqlite-vec storage format)
# ---------------------------------------------------------------------------

def _pack(vec: Sequence[float]) -> bytes:
    return struct.pack("<%df" % len(vec), *[float(x) for x in vec])


def _unpack(blob: bytes) -> List[float]:
    n = len(blob) // 4
    return list(struct.unpack("<%df" % n, blob))


# ---------------------------------------------------------------------------
# Embedding lane (local Ollama)
# ---------------------------------------------------------------------------

class EmbeddingLane:
    """Thin, honest wrapper over the local Ollama embeddings endpoint.

    Raises :class:`EmbeddingUnavailable` on every failure mode (HTTP error,
    connection refused, timeout, malformed body, empty vector). It never returns
    a fabricated or zero vector.
    """

    def __init__(self, url: str = OLLAMA_EMBED_URL, model: str = EMBED_MODEL,
                 timeout: float = _EMBED_TIMEOUT):
        self.url = url
        self.model = model
        self.timeout = float(timeout)
        self.dim = EMBED_DIM

    def embed(self, text: str) -> List[float]:
        prompt = str(text or "").strip()
        if not prompt:
            raise EmbeddingUnavailable("cannot embed empty text")
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt[:_EMBED_TEXT_MAX],
            "keep_alive": _EMBED_KEEP_ALIVE,
            "options": {"num_ctx": _EMBED_NUM_CTX},
        }).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:  # noqa: PERF203
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except Exception:  # noqa: BLE001
                pass
            raise EmbeddingUnavailable(
                f"embedding lane HTTP {exc.code}{(': ' + detail) if detail else ''}") from exc
        except Exception as exc:  # noqa: BLE001 — refused/timeout/DNS/…
            raise EmbeddingUnavailable(f"embedding lane unreachable: {exc}") from exc

        vec = body.get("embedding") if isinstance(body, dict) else None
        if not isinstance(vec, list) or not vec:
            raise EmbeddingUnavailable("embedding lane returned no vector")
        out = [float(x) for x in vec]
        self.dim = len(out)
        return out

    def available(self) -> bool:
        try:
            self.embed("ping")
            return True
        except EmbeddingUnavailable:
            return False


# ---------------------------------------------------------------------------
# Vector store (sqlite-vec)
# ---------------------------------------------------------------------------

class VectorStore:
    """sqlite-vec-backed store: float32 vectors + a rowid→record mapping.

    The ``vec0`` table holds embeddings; ``corpus_vector_meta`` maps each vector
    rowid to a logical record (``record_id``/``source``/``source_id``). Upserts are
    keyed by ``record_id`` and replace the previous vector atomically.
    """

    def __init__(self, conn: sqlite3.Connection, dim: int = EMBED_DIM):
        self.conn = conn
        self.dim = int(dim)
        self._loaded = False
        self.ensure()

    # -- schema -------------------------------------------------------------
    def _load_extension(self) -> None:
        try:
            import sqlite_vec  # noqa: F401
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError("sqlite-vec is not installed in this environment") from exc
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self._loaded = True

    def ensure(self) -> None:
        if not self._loaded:
            self._load_extension()
        self.conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {VEC_TABLE} "
            f"USING vec0(embedding float[{self.dim}] distance_metric=cosine)")
        self.conn.execute(
            f"CREATE TABLE IF NOT EXISTS {META_TABLE} ("
            "  vec_rowid INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  record_id TEXT NOT NULL,"
            "  source TEXT NOT NULL,"
            "  source_id TEXT NOT NULL,"
            "  model TEXT,"
            "  created_at TEXT DEFAULT (datetime('now')))")
        self.conn.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{META_TABLE}_record "
            f"ON {META_TABLE}(record_id)")
        self.conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{META_TABLE}_source "
            f"ON {META_TABLE}(source)")
        self.conn.execute(
            f"CREATE TABLE IF NOT EXISTS {SNAP_TABLE} ("
            "  id TEXT PRIMARY KEY,"
            "  metric TEXT NOT NULL,"
            "  drift REAL NOT NULL,"
            "  similarity REAL,"
            "  n_current INTEGER,"
            "  n_historical INTEGER,"
            "  model TEXT,"
            "  created_at TEXT DEFAULT (datetime('now')))")
        self.conn.commit()

    # -- writes -------------------------------------------------------------
    def upsert(self, record_id: str, source: str, source_id: str,
               embedding: Sequence[float], model: str = EMBED_MODEL) -> int:
        rid = str(record_id or "").strip()
        if not rid:
            raise ValueError("record_id is required")
        vec = [float(x) for x in embedding]
        if len(vec) != self.dim:
            raise ValueError(f"embedding has dim {len(vec)}, expected {self.dim}")
        blob = _pack(vec)
        row = self.conn.execute(
            f"SELECT vec_rowid FROM {META_TABLE} WHERE record_id = ?", (rid,)).fetchone()
        if row:
            vec_rowid = row[0]
            self.conn.execute(f"DELETE FROM {VEC_TABLE} WHERE rowid = ?", (vec_rowid,))
            self.conn.execute(
                f"INSERT INTO {VEC_TABLE}(rowid, embedding) VALUES (?, ?)",
                (vec_rowid, blob))
            self.conn.execute(
                f"UPDATE {META_TABLE} SET source = ?, source_id = ?, model = ? "
                "WHERE vec_rowid = ?", (source, source_id, model, vec_rowid))
        else:
            cur = self.conn.execute(
                f"INSERT INTO {META_TABLE}(record_id, source, source_id, model) "
                "VALUES (?, ?, ?, ?)", (rid, source, source_id, model))
            vec_rowid = int(cur.lastrowid)
            self.conn.execute(
                f"INSERT INTO {VEC_TABLE}(rowid, embedding) VALUES (?, ?)",
                (vec_rowid, blob))
        self.conn.commit()
        return vec_rowid

    def delete(self, record_id: str) -> bool:
        row = self.conn.execute(
            f"SELECT vec_rowid FROM {META_TABLE} WHERE record_id = ?", (record_id,)).fetchone()
        if not row:
            return False
        self.conn.execute(f"DELETE FROM {VEC_TABLE} WHERE rowid = ?", (row[0],))
        self.conn.execute(f"DELETE FROM {META_TABLE} WHERE vec_rowid = ?", (row[0],))
        self.conn.commit()
        return True

    # -- reads --------------------------------------------------------------
    def search(self, embedding: Sequence[float], *, limit: int = 10,
               threshold: Optional[float] = None,
               source: Optional[str] = None) -> List[Dict[str, Any]]:
        vec = [float(x) for x in embedding]
        if len(vec) != self.dim:
            raise ValueError(f"query has dim {len(vec)}, expected {self.dim}")
        rows = self.conn.execute(
            f"SELECT rowid, distance FROM {VEC_TABLE} "
            "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (_pack(vec), max(int(limit), 1))).fetchall()
        out: List[Dict[str, Any]] = []
        for rowid, distance in rows:
            meta = self.conn.execute(
                f"SELECT record_id, source, source_id, model FROM {META_TABLE} "
                "WHERE vec_rowid = ?", (rowid,)).fetchone()
            if not meta:
                continue
            if source and meta[1] != source:
                continue
            dist = float(distance)
            if threshold is not None and dist > float(threshold):
                continue
            out.append({
                "record_id": meta[0], "source": meta[1], "source_id": meta[2],
                "model": meta[3], "distance": round(dist, 6),
                "similarity": round(1.0 - dist, 6),
            })
        return out

    def has(self, record_id: str) -> bool:
        return self.conn.execute(
            f"SELECT 1 FROM {META_TABLE} WHERE record_id = ?", (record_id,)).fetchone() is not None

    def count(self, source: Optional[str] = None) -> int:
        if source:
            return int(self.conn.execute(
                f"SELECT COUNT(*) FROM {META_TABLE} WHERE source = ?", (source,)).fetchone()[0])
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {META_TABLE}").fetchone()[0])

    def vectors_by_source(self, source: str, limit: int = 2000) -> List[List[float]]:
        rows = self.conn.execute(
            f"SELECT v.embedding FROM {META_TABLE} m "
            f"JOIN {VEC_TABLE} v ON v.rowid = m.vec_rowid "
            "WHERE m.source = ? LIMIT ?", (source, max(int(limit), 1))).fetchall()
        return [_unpack(bytes(r[0])) for r in rows]

    def stats(self) -> Dict[str, Any]:
        by_source = {r[0]: r[1] for r in self.conn.execute(
            f"SELECT source, COUNT(*) FROM {META_TABLE} GROUP BY source").fetchall()}
        return {"total": self.count(), "dim": self.dim, "by_source": by_source,
                "model": EMBED_MODEL, "metric": "cosine"}

    # -- snapshot history ---------------------------------------------------
    def record_snapshot(self, report: Dict[str, Any]) -> str:
        sid = str(uuid.uuid4())
        self.conn.execute(
            f"INSERT INTO {SNAP_TABLE}(id, metric, drift, similarity, n_current, "
            "n_historical, model) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, str(report.get("metric") or "cosine-centroid"),
             float(report.get("drift") or 0.0),
             report.get("similarity"),
             int(report.get("n_current") or 0),
             int(report.get("n_historical") or 0),
             EMBED_MODEL))
        self.conn.commit()
        return sid

    def list_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            f"SELECT id, metric, drift, similarity, n_current, n_historical, model, "
            f"created_at FROM {SNAP_TABLE} ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (max(int(limit), 1),)).fetchall()
        return [dict(r) if isinstance(r, sqlite3.Row) else {
            "id": r[0], "metric": r[1], "drift": r[2], "similarity": r[3],
            "n_current": r[4], "n_historical": r[5], "model": r[6], "created_at": r[7],
        } for r in rows]


# ---------------------------------------------------------------------------
# Drift math (pure — no I/O, unit-testable with deterministic vectors)
# ---------------------------------------------------------------------------

def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    return 1.0 - cosine_similarity(a, b)


def centroid(vectors: Sequence[Sequence[float]]) -> List[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    acc = [0.0] * dim
    for v in vectors:
        for i, x in enumerate(v):
            acc[i] += float(x)
    n = float(len(vectors))
    return [x / n for x in acc]


def compute_drift(current: Sequence[Sequence[float]],
                  historical: Sequence[Sequence[float]]) -> Dict[str, Any]:
    """Cosine distance between the two centroids. Measured, never predicted."""
    if not current or not historical:
        return {
            "available": False,
            "metric": "cosine-centroid",
            "reason": "insufficient data — need both corpus and historical SQP vectors",
            "n_current": len(current), "n_historical": len(historical),
        }
    dist = cosine_distance(centroid(current), centroid(historical))
    return {
        "available": True,
        "metric": "cosine-centroid",
        "drift": round(dist, 6),
        "similarity": round(1.0 - dist, 6),
        "n_current": len(current),
        "n_historical": len(historical),
    }


# ---------------------------------------------------------------------------
# Store factory + embedding of records
# ---------------------------------------------------------------------------

def _sqlite_path() -> str:
    try:
        import data_layer  # local import: avoids an import cycle at module load
        return str(getattr(data_layer, "_SQLITE_PATH", "") or "")
    except Exception:  # noqa: BLE001
        return ""


def open_vector_store(db_path: Optional[str] = None) -> Optional[VectorStore]:
    """Open the vector store on the local SQLite corpus index. None if unavailable."""
    path = db_path or _sqlite_path()
    if not path or not os.path.exists(path):
        return None
    try:
        conn = sqlite3.connect(path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:  # noqa: BLE001
            pass
        return VectorStore(conn, dim=EMBED_DIM)
    except Exception:  # noqa: BLE001 — sqlite-vec missing / locked / corrupt
        return None


def _corpus_text(record: Dict[str, Any]) -> str:
    parts = [str(record.get("title") or ""), str(record.get("summary") or "")]
    content = str(record.get("content") or "")
    if content:
        parts.append(content)
    return " — ".join(p for p in parts if p).strip()


def _sqp_key(query: str) -> str:
    return "sqp:" + hashlib.sha256(str(query or "").strip().lower().encode("utf-8")).hexdigest()[:24]


def embed_pending_corpus(store: VectorStore, lane: EmbeddingLane, *, limit: int = 50) -> Dict[str, Any]:
    """Embed up to `limit` corpus records that have no vector yet. Honest counts."""
    rows = store.conn.execute(
        f"SELECT r.id, r.source, r.source_id, r.title, r.summary, r.content "
        f"FROM corpus_records r LEFT JOIN {META_TABLE} m ON m.record_id = r.id "
        "WHERE m.record_id IS NULL ORDER BY r.ingested_at DESC LIMIT ?",
        (max(int(limit), 1),)).fetchall()
    done = errored = 0
    errors: List[str] = []
    for r in rows:
        rec = dict(r) if isinstance(r, sqlite3.Row) else {
            "id": r[0], "source": r[1], "source_id": r[2],
            "title": r[3], "summary": r[4], "content": r[5]}
        text = _corpus_text(rec)
        if not text:
            continue
        try:
            vec = lane.embed(text)
            store.upsert(rec["id"], SRC_CORPUS, rec["source_id"], vec)
            done += 1
        except EmbeddingUnavailable as exc:
            errors.append(str(exc))
            break  # lane is down; stop rather than hammer it
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{rec.get('source_id')}: {exc}"[:200])
            errored += 1
    return {"available": True, "embedded": done, "errored": errored,
            "pending_seen": len(rows), "errors": errors[:10]}


def embed_pending_sqp(store: VectorStore, lane: EmbeddingLane, *, limit: int = 100) -> Dict[str, Any]:
    """Embed up to `limit` historical SQP queries that have no vector yet."""
    try:
        rows = store.conn.execute(
            "SELECT DISTINCT query FROM search_query_performance "
            "WHERE query IS NOT NULL AND query <> '' LIMIT ?",
            (max(int(limit) * 4, 200),)).fetchall()
    except Exception:  # noqa: BLE001 — table absent on this install
        return {"available": True, "embedded": 0, "errored": 0, "pending_seen": 0,
                "errors": ["search_query_performance table not present"]}
    done = errored = 0
    errors: List[str] = []
    for r in rows:
        if done >= max(int(limit), 1):
            break
        query = r[0] if not isinstance(r, sqlite3.Row) else r["query"]
        key = _sqp_key(query)
        if store.has(key):
            continue
        try:
            vec = lane.embed(str(query))
            store.upsert(key, SRC_SQP, str(query)[:80], vec)
            done += 1
        except EmbeddingUnavailable as exc:
            errors.append(str(exc))
            break
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc)[:200])
            errored += 1
    return {"available": True, "embedded": done, "errored": errored,
            "pending_seen": len(rows), "errors": errors[:10]}


# ---------------------------------------------------------------------------
# High-level surfaces used by the router + tools
# ---------------------------------------------------------------------------

_VECTOR_CAVEATS = [
    "Semantic vector search via the local qwen3-embedding:0.6b lane (sqlite-vec, cosine).",
    "An ADDITIONAL mode — deterministic keyword search remains available and unchanged.",
    "Third-party metadata; licence is as reported by the source sweep.",
]

_DRIFT_CAVEATS = [
    "Drift is a MEASURED cosine distance between embedding centroids — not a trend, forecast or cause.",
    "Compare against your own imported Search Query Performance history; no network is used.",
    "Local-only: qwen3-embedding:0.6b via Ollama + sqlite-vec; nothing leaves this machine.",
]


def vector_search(query: str, *, limit: int = 8, threshold: Optional[float] = None,
                  source: Optional[str] = None, store: Optional[VectorStore] = None,
                  lane: Optional[EmbeddingLane] = None) -> Dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        return {"available": False, "reason": "query is required", "matches": [],
                "caveats": _VECTOR_CAVEATS}
    store = store or open_vector_store()
    if store is None:
        return {"available": False, "reason": "vector store unavailable (local SQLite index only)",
                "matches": [], "caveats": _VECTOR_CAVEATS}
    lane = lane or EmbeddingLane()
    try:
        qv = lane.embed(q)
    except EmbeddingUnavailable as exc:
        return {"available": False, "reason": str(exc), "matches": [],
                "caveats": _VECTOR_CAVEATS}
    matches = store.search(qv, limit=limit, threshold=threshold, source=source)
    # enrich with the record's human fields (best-effort, same DB)
    for m in matches:
        try:
            row = store.conn.execute(
                "SELECT title, url, license, summary, kind FROM corpus_records WHERE id = ?",
                (m["record_id"],)).fetchone()
            if row:
                d = dict(row) if isinstance(row, sqlite3.Row) else {
                    "title": row[0], "url": row[1], "license": row[2],
                    "summary": row[3], "kind": row[4]}
                m.update({k: d.get(k) for k in ("title", "url", "license", "summary", "kind")})
        except Exception:  # noqa: BLE001
            pass
    return {"available": True, "query": q, "count": len(matches),
            "matches": matches, "caveats": _VECTOR_CAVEATS}


def drift_report(*, store: Optional[VectorStore] = None, persist: bool = True) -> Dict[str, Any]:
    store = store or open_vector_store()
    if store is None:
        return {"available": False, "reason": "vector store unavailable (local SQLite index only)",
                "caveats": _DRIFT_CAVEATS}
    current = store.vectors_by_source(SRC_CORPUS)
    historical = store.vectors_by_source(SRC_SQP)
    report = compute_drift(current, historical)
    report["model"] = EMBED_MODEL
    if report.get("available") and persist:
        try:
            report["snapshot_id"] = store.record_snapshot(report)
            report["history"] = store.list_snapshots(limit=10)
        except Exception:  # noqa: BLE001
            pass
    report["caveats"] = _DRIFT_CAVEATS
    return report


def embed_now(store: Optional[VectorStore] = None, lane: Optional[EmbeddingLane] = None,
              *, limit: int = 50, include_sqp: bool = True) -> Dict[str, Any]:
    store = store or open_vector_store()
    if store is None:
        return {"available": False, "reason": "vector store unavailable (local SQLite index only)"}
    lane = lane or EmbeddingLane()
    out: Dict[str, Any] = {"available": True}
    out["corpus"] = embed_pending_corpus(store, lane, limit=limit)
    if include_sqp:
        out["sqp"] = embed_pending_sqp(store, lane, limit=limit)
    out["stats"] = store.stats()
    return out
