"""Long-term memory: context index, compression, retrieval, epistemic facts.

The default path is local and model-free: a SQLite file, a deterministic hashed
embedding (256 dims), no network. That is deliberate — memory must work when the
GPU is busy with a render or the 27B worker is stopped.

An **opt-in semantic path** adds real embeddings from the local Ollama runner
(`qwen3-embedding:0.6b`, 1024 dims) and a `sqlite-vec` KNN index beside the
hashed one. It is off by default (`semantic=None` reads
`NORTHSTAR_MEMORY_SEMANTIC`, default `0`), and any failure disables it for the
rest of the process and falls back to the hashed index — memory never becomes
unavailable because a model is.

Three layers
------------
**Context index**   chunked text; hashed bag-of-words by default, semantic
                    vectors when enabled. Hashed search is exact and cheap.
**Compression**     extractive, query-aware, budgeted in tokens. It never
                    invents a sentence; it selects and orders real ones.
**Epistemic facts** subject/predicate/value with confidence, source and a
                    supersession chain, so "unlearn" is an auditable status
                    change rather than a delete, and a contradiction is
                    visible instead of silently overwritten.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Iterable, List, Optional

DIM = 256
SEMANTIC_DIM = 1024
EMBED_MODEL = os.environ.get("NORTHSTAR_EMBED_MODEL", "qwen3-embedding:0.6b")
EMBED_URL = os.environ.get("NORTHSTAR_EMBED_URL", "http://127.0.0.1:11434/api/embeddings")
EMBED_TIMEOUT_S = float(os.environ.get("NORTHSTAR_EMBED_TIMEOUT", "30"))
_WORD_RE = re.compile(r"[a-z0-9']+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    account TEXT NOT NULL,
    session_id TEXT,
    text TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    vec BLOB NOT NULL,
    source TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_account ON chunks(account, created_at);
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    account TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT,
    status TEXT NOT NULL,
    supersedes TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_live ON facts(account, subject, predicate, status);
"""


def token_estimate(text: str) -> int:
    """~1.3 tokens per whitespace word; good enough for budgeting, stated as such."""
    return max(1, int(round(len((text or "").split()) * 1.3)))


def embed(text: str, dim: int = DIM) -> List[float]:
    """Deterministic hashed embedding. Same text, same vector, every process."""
    vector = [0.0] * dim
    words = _WORD_RE.findall((text or "").lower())
    if not words:
        return vector
    counts: Dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    for word, count in counts.items():
        digest = hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


def _pack(vector: Iterable[float]) -> bytes:
    return json.dumps([round(v, 6) for v in vector],
                      separators=(",", ":")).encode("utf-8")


def _pack_semantic(vector: List[float]) -> bytes:
    """float32 little-endian, the layout sqlite-vec expects."""
    import struct
    return struct.pack(f"<{len(vector)}f", *[float(v) for v in vector])


def _unpack(blob: bytes) -> List[float]:
    return json.loads(blob.decode("utf-8"))


def _cosine(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def semantic_enabled_default() -> bool:
    return os.environ.get("NORTHSTAR_MEMORY_SEMANTIC", "0").strip() == "1"


class EmbeddingError(RuntimeError):
    """The local embedding runner did not answer or returned a bad vector."""


def embed_semantic(text: str, *, timeout: float = EMBED_TIMEOUT_S) -> List[float]:
    """One 1024-d vector from the local Ollama runner. No cloud fallback."""
    payload = json.dumps({"model": EMBED_MODEL, "prompt": str(text or "")}).encode("utf-8")
    req = urllib.request.Request(EMBED_URL, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EmbeddingError(f"embedding_unavailable: {exc}") from exc
    vector = data.get("embedding")
    if not isinstance(vector, list) or len(vector) != SEMANTIC_DIM:
        raise EmbeddingError(
            f"embedding_bad_shape: expected {SEMANTIC_DIM}, got "
            f"{len(vector) if isinstance(vector, list) else type(vector).__name__}")
    return [float(v) for v in vector]


def chunk_text(text: str, *, max_tokens: int = 220) -> List[str]:
    """Paragraph first, then sentence packing, so chunks stay cohesive."""
    text = (text or "").strip()
    if not text:
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    chunks: List[str] = []
    for block in blocks:
        if token_estimate(block) <= max_tokens:
            chunks.append(block)
            continue
        current: List[str] = []
        size = 0
        for sentence in _SENTENCE_SPLIT.split(block):
            piece = sentence.strip()
            if not piece:
                continue
            cost = token_estimate(piece)
            if current and size + cost > max_tokens:
                chunks.append(" ".join(current))
                current, size = [], 0
            current.append(piece)
            size += cost
        if current:
            chunks.append(" ".join(current))
    return chunks


def compress(text: str, max_tokens: int, query: str = "") -> Dict[str, Any]:
    """Extractive compression with a hard token budget. Selects, never writes."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text or "")
                 if s.strip()]
    if not sentences:
        return {"text": "", "tokens": 0, "kept": 0, "of": 0,
                "mode": "extractive"}
    if token_estimate(text) <= max_tokens:
        return {"text": text.strip(), "tokens": token_estimate(text),
                "kept": len(sentences), "of": len(sentences),
                "mode": "extractive"}

    query_terms = set(_WORD_RE.findall((query or "").lower()))
    chosen: List[int] = []
    seen_terms: set = set()
    used = 0
    order = sorted(range(len(sentences)), key=lambda i: -_score(
        sentences[i], query_terms, i, len(sentences)))
    for index in order:
        sentence = sentences[index]
        cost = token_estimate(sentence)
        if used + cost > max_tokens:
            continue
        terms = set(_WORD_RE.findall(sentence.lower()))
        redundancy = len(terms & seen_terms) / max(1, len(terms))
        if redundancy > 0.8 and chosen:
            continue
        chosen.append(index)
        seen_terms |= terms
        used += cost
        if used >= max_tokens - 4:
            break

    chosen.sort()
    kept = " ".join(sentences[i] for i in chosen)
    return {"text": kept, "tokens": used, "kept": len(chosen),
            "of": len(sentences), "mode": "extractive"}


def _score(sentence: str, query_terms: set, index: int, total: int) -> float:
    terms = set(_WORD_RE.findall(sentence.lower()))
    overlap = len(terms & query_terms) / max(1, len(query_terms)) if query_terms else 0.0
    position = 1.0 - (index / max(1, total))
    length_bonus = min(1.0, len(sentence) / 120.0)
    return overlap * 2.0 + position * 0.5 + length_bonus * 0.3


class MemoryIndex:
    """SQLite-backed context + fact store. One lock, one connection.

    ``semantic=True`` enables the local embedding path (qwen3-embedding +
    sqlite-vec). A failure disables it for the process and falls back to the
    hashed index; it never raises from a search because a model is down.
    """

    def __init__(self, path: str, *, semantic: Optional[bool] = None):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.semantic = semantic_enabled_default() if semantic is None else bool(semantic)
        self.semantic_reason = "" if self.semantic else "disabled"
        with self._lock:
            self._conn.executescript(_SCHEMA)
            if self.semantic:
                try:
                    import sqlite_vec
                    self._conn.enable_load_extension(True)
                    sqlite_vec.load(self._conn)
                    self._conn.execute(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vec USING vec0("
                        "chunk_id TEXT PRIMARY KEY, embedding float[1024] "
                        "distance_metric=cosine)")
                except Exception as exc:  # noqa: BLE001 - fallback is the contract
                    self.semantic = False
                    self.semantic_reason = f"sqlite_vec_unavailable: {exc}"
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- context index -----------------------------------------------------

    def remember_text(self, account: str, text: str, *, session_id: str = "",
                      source: str = "", max_tokens: int = 220,
                      now: Optional[float] = None) -> Dict[str, Any]:
        stamp = time.time() if now is None else now
        pieces = chunk_text(text, max_tokens=max_tokens)
        ids: List[str] = []
        with self._lock:
            for piece in pieces:
                chunk_id = "c_" + uuid.uuid4().hex[:12]
                self._conn.execute(
                    "INSERT INTO chunks (id, account, session_id, text, tokens, vec,"
                    " source, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (chunk_id, account, session_id, piece, token_estimate(piece),
                     _pack(embed(piece)), source, stamp))
                if self.semantic:
                    try:
                        self._conn.execute(
                            "INSERT OR REPLACE INTO chunk_vec (chunk_id, embedding)"
                            " VALUES (?, ?)",
                            (chunk_id, _pack_semantic(embed_semantic(piece))))
                    except Exception as exc:  # noqa: BLE001 - fall back, never fail the write
                        self.semantic = False
                        self.semantic_reason = str(exc)[:300]
                ids.append(chunk_id)
            self._conn.commit()
        return {"chunks": len(ids), "ids": ids, "semantic": self.semantic}

    def _backfill_semantic(self, account: str, limit: int = 32) -> int:
        """Embed chunks written before semantic mode was enabled, bounded per call."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT c.id, c.text FROM chunks c WHERE c.account=? AND NOT EXISTS"
                " (SELECT 1 FROM chunk_vec v WHERE v.chunk_id = c.id) LIMIT ?",
                (account, int(limit))).fetchall()
        added = 0
        for row in rows:
            vector = embed_semantic(row["text"])
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO chunk_vec (chunk_id, embedding) VALUES (?, ?)",
                    (row["id"], _pack_semantic(vector)))
                self._conn.commit()
            added += 1
        return added

    def _search_semantic(self, account: str, vector: List[float], k: int,
                         min_score: float) -> List[Dict[str, Any]]:
        fetch = max(int(k) * 8, 32)
        with self._lock:
            rows = self._conn.execute(
                "SELECT v.chunk_id, v.distance, c.text, c.tokens, c.source,"
                " c.created_at, c.account FROM chunk_vec v"
                " JOIN chunks c ON c.id = v.chunk_id"
                f" WHERE v.embedding MATCH ? AND v.k = {fetch}",
                (_pack_semantic(vector),)).fetchall()
        scored = []
        for row in rows:
            if row["account"] != account:
                continue
            score = max(0.0, 1.0 - float(row["distance"]))
            if score >= min_score:
                scored.append({"id": row["chunk_id"], "text": row["text"],
                               "tokens": row["tokens"], "source": row["source"],
                               "created_at": row["created_at"],
                               "score": round(score, 4), "semantic": True})
        scored.sort(key=lambda item: -item["score"])
        return scored[:k]

    def search(self, account: str, query: str, *, k: int = 5,
               min_score: float = 0.05) -> List[Dict[str, Any]]:
        if self.semantic:
            try:
                self._backfill_semantic(account)
                return self._search_semantic(account, embed_semantic(query), k,
                                             min_score)
            except Exception as exc:  # noqa: BLE001 - fallback is the contract
                self.semantic = False
                self.semantic_reason = str(exc)[:300]
        target = embed(query)
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, text, tokens, source, created_at, vec FROM chunks"
                " WHERE account=? ORDER BY created_at DESC LIMIT 2000",
                (account,)).fetchall()
        scored = []
        for row in rows:
            score = _cosine(target, _unpack(row["vec"]))
            if score >= min_score:
                scored.append({"id": row["id"], "text": row["text"],
                               "tokens": row["tokens"], "source": row["source"],
                               "created_at": row["created_at"],
                               "score": round(score, 4), "semantic": False})
        scored.sort(key=lambda item: -item["score"])
        return scored[:k]

    def context(self, account: str, query: str, *, budget_tokens: int = 700,
                k: int = 8) -> Dict[str, Any]:
        """Retrieve + compress into a prompt-sized block with a real budget."""
        hits = self.search(account, query, k=k)
        merged = "\n\n".join(hit["text"] for hit in hits)
        packed = compress(merged, budget_tokens, query=query)
        return {
            "query": query,
            "hits": len(hits),
            "budget_tokens": budget_tokens,
            "used_tokens": packed["tokens"],
            "text": packed["text"],
            "sources": sorted({str(h["source"] or "") for h in hits} - {""}),
        }

    # -- epistemic facts ---------------------------------------------------

    def assert_fact(self, account: str, subject: str, predicate: str, value: str,
                    *, confidence: float = 0.7, source: str = "",
                    now: Optional[float] = None) -> Dict[str, Any]:
        stamp = time.time() if now is None else now
        if not (0.0 <= float(confidence) <= 1.0):
            raise ValueError("confidence must be within [0, 1]")
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, value, confidence FROM facts WHERE account=? AND"
                " subject=? AND predicate=? AND status='live'",
                (account, subject, predicate)).fetchall()
            contradiction = None
            for row in rows:
                if row["value"] != value:
                    contradiction = {"previous": row["value"],
                                     "previous_confidence": row["confidence"],
                                     "previous_id": row["id"]}
                self._conn.execute(
                    "UPDATE facts SET status='superseded' WHERE id=?", (row["id"],))
            fact_id = "f_" + uuid.uuid4().hex[:12]
            self._conn.execute(
                "INSERT INTO facts (id, account, subject, predicate, value,"
                " confidence, source, status, supersedes, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (fact_id, account, subject, predicate, value, float(confidence),
                 source, "live",
                 contradiction["previous_id"] if contradiction else None, stamp))
            self._conn.commit()
        return {"id": fact_id, "status": "live", "contradiction": contradiction}

    def facts(self, account: str, *, include_superseded: bool = False,
              limit: int = 200) -> List[Dict[str, Any]]:
        query = ("SELECT id, subject, predicate, value, confidence, source, status,"
                 " supersedes, created_at FROM facts WHERE account=?")
        params: List[Any] = [account]
        if not include_superseded:
            query += " AND status='live'"
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def recall_fact(self, account: str, subject: str,
                    predicate: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = ("SELECT id, subject, predicate, value, confidence, source,"
                 " created_at FROM facts WHERE account=? AND subject=?"
                 " AND status='live'")
        params: List[Any] = [account, subject]
        if predicate:
            query += " AND predicate=?"
            params.append(predicate)
        query += " ORDER BY created_at DESC LIMIT 1"
        with self._lock:
            row = self._conn.execute(query, params).fetchone()
        return dict(row) if row else None

    def conflicts(self, account: str) -> List[Dict[str, Any]]:
        """Supersession chains where the value actually changed."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT old.subject, old.predicate, old.value AS old_value,"
                " old.confidence AS old_confidence, new.value AS new_value,"
                " new.confidence AS new_confidence, new.id AS current_id"
                " FROM facts old JOIN facts new ON new.supersedes = old.id"
                " WHERE old.account=? AND old.status='superseded'"
                " AND old.value != new.value",
                (account,)).fetchall()
        return [dict(row) for row in rows]

    def unlearn(self, fact_id: str) -> Dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, status FROM facts WHERE id=?", (fact_id,)).fetchone()
            if not row:
                return {"status": "not_found", "id": fact_id}
            self._conn.execute(
                "UPDATE facts SET status='unlearned' WHERE id=?", (fact_id,))
            self._conn.commit()
        return {"status": "unlearned", "id": fact_id, "previous": row["status"]}

    def stats(self, account: str) -> Dict[str, Any]:
        with self._lock:
            chunks = self._conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(tokens),0) AS t FROM chunks"
                " WHERE account=?", (account,)).fetchone()
            live = self._conn.execute(
                "SELECT COUNT(*) AS n FROM facts WHERE account=? AND status='live'",
                (account,)).fetchone()
        return {"account": account, "chunks": chunks["n"], "chunk_tokens": chunks["t"],
                "live_facts": live["n"], "semantic": self.semantic,
                "semantic_reason": self.semantic_reason}
