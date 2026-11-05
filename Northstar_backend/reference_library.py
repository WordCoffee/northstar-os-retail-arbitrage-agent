"""A stored-reference library: the picture Ty made yesterday is an input today.

`generate_reference` only ever took bytes the caller already had. That made the
second and third picture of a product a manual operation: someone had to find
the right PNG, read it, and paste it in. A seller does this dozens of times per
product, so the missing piece was never the model - it was the shelf.

What this adds:

  * a content-addressed store under ``renders/references/<brand>/<product>/``
    (same bytes are stored once, keyed by SHA-256);
  * a SQLite index beside the other local stores, with the prompt that produced
    each reference, its perceptual hash, and its dimensions;
  * retrieval three ways: by (brand, product, kind), by perceptual similarity,
    and by semantic search on the local embedding lane;
  * ``resolve`` returns bytes, so it plugs straight into
    ``studio_generation.generate_reference``.

Honesty rules: an unavailable embedding lane is reported, never faked with a
zero vector; a row whose file has been deleted on disk is reported as missing
rather than returned as if it were usable.

    python -m reference_library --list --brand mogra
    python -m reference_library --find --brand mogra --product lions_mane --kind product_photo
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
STORE_ROOT = ROOT / "renders" / "references"
DB_PATH = ROOT / "Northstar_backend" / "data" / "references.db"
EMBED_ENDPOINT = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434") + "/api/embeddings"
EMBED_MODEL = os.environ.get("NORTHSTAR_EMBED_MODEL", "qwen3-embedding:0.6b")

KINDS = ("product_photo", "style_reference", "logo", "packaging", "generated", "upload")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS refs (
  id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL,
  path TEXT NOT NULL,
  brand TEXT NOT NULL DEFAULT '',
  product TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'generated',
  prompt TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  width INTEGER,
  height INTEGER,
  phash TEXT,
  embedding BLOB,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS refs_product ON refs(brand, product, kind);
CREATE UNIQUE INDEX IF NOT EXISTS refs_sha ON refs(sha256);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str, fallback: str = "unfiled") -> str:
    clean = "".join(ch.lower() if ch.isalnum() or ch in "-_" else "_"
                    for ch in str(value or "").strip())
    return clean.strip("_")[:60] or fallback


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _dimensions(data: bytes) -> tuple[Optional[int], Optional[int]]:
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(data)) as im:
            return im.width, im.height
    except Exception:  # noqa: BLE001 - a non-image is still storable, just unsized
        return None, None


def _phash(data: bytes) -> Optional[str]:
    try:
        from io import BytesIO

        from PIL import Image

        import ship_gate

        with Image.open(BytesIO(data)) as im:
            return str(ship_gate.phash(im.convert("RGB")))
    except Exception:  # noqa: BLE001
        return None


def embed(text: str, *, timeout: float = 20.0) -> Optional[List[float]]:
    """The local embedding lane, or None. Never a fabricated vector."""
    if not text.strip():
        return None
    body = json.dumps({"model": EMBED_MODEL, "prompt": text[:4000]}).encode("utf-8")
    request = urllib.request.Request(EMBED_ENDPOINT, data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    vector = payload.get("embedding")
    if not isinstance(vector, list) or not vector:
        return None
    return [float(v) for v in vector]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def save(data: bytes, *, brand: str = "", product: str = "", kind: str = "generated",
         prompt: str = "", source: str = "", db_path: Optional[Path] = None,
         store_root: Optional[Path] = None, embed_text: Optional[str] = None,
         embedder=None) -> Dict[str, Any]:
    """Store one reference. Idempotent on identical bytes."""
    if not data:
        raise ValueError("a reference needs bytes")
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")
    digest = hashlib.sha256(data).hexdigest()
    root = Path(store_root) if store_root else STORE_ROOT
    folder = root / _slug(brand) / _slug(product)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest[:16]}.png"
    conn = connect(db_path)
    try:
        existing = conn.execute("SELECT * FROM refs WHERE sha256=?", (digest,)).fetchone()
        if existing:
            return {"ok": True, "deduplicated": True, **dict(existing)}
        if not path.is_file():
            path.write_bytes(data)
        width, height = _dimensions(data)
        try:
            stored = str(path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            # An explicit store_root outside the repo (tests, an external shelf)
            # is recorded absolutely rather than silently mangled.
            stored = str(path).replace("\\", "/")
        vector = (embedder or embed)(embed_text if embed_text is not None else
                                     f"{brand} {product} {kind} {prompt}")
        conn.execute(
            "INSERT INTO refs (id, sha256, path, brand, product, kind, prompt, source,"
            " width, height, phash, embedding, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (digest[:16], digest, stored,
             _slug(brand, ""), _slug(product, ""), kind, str(prompt or "")[:2000],
             str(source or "")[:400], width, height, _phash(data),
             json.dumps(vector).encode("utf-8") if vector else None, _now()))
        conn.commit()
        row = conn.execute("SELECT * FROM refs WHERE sha256=?", (digest,)).fetchone()
        return {"ok": True, "deduplicated": False, **dict(row)}
    finally:
        conn.close()


def find(*, brand: str = "", product: str = "", kind: Optional[str] = None,
         limit: int = 20, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    clauses, params = [], []
    if brand:
        clauses.append("brand=?")
        params.append(_slug(brand, ""))
    if product:
        clauses.append("product=?")
        params.append(_slug(product, ""))
    if kind:
        clauses.append("kind=?")
        params.append(kind)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT * FROM refs{where} ORDER BY created_at DESC LIMIT ?",
            (*params, max(1, int(limit)))).fetchall()
    finally:
        conn.close()
    return [{k: r[k] for k in r.keys() if k != "embedding"} for r in rows]


def resolve(ref_id: str, *, db_path: Optional[Path] = None) -> Optional[bytes]:
    """Bytes for one stored reference, or None when the row or its file is gone."""
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT path FROM refs WHERE id=? OR sha256 LIKE ?",
                           (ref_id, ref_id + "%")).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    path = ROOT / row["path"]
    return path.read_bytes() if path.is_file() else None


def nearest(data: bytes, *, brand: str = "", product: str = "", limit: int = 5,
            db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Perceptual nearest references, by Hamming distance on the 64-bit pHash."""
    target = _phash(data)
    if target is None:
        return []
    clause, params = "", []
    if brand or product:
        parts = []
        if brand:
            parts.append("brand=?")
            params.append(_slug(brand, ""))
        if product:
            parts.append("product=?")
            params.append(_slug(product, ""))
        clause = " WHERE " + " AND ".join(parts)
    conn = connect(db_path)
    try:
        rows = conn.execute(f"SELECT * FROM refs{clause}", params).fetchall()
    finally:
        conn.close()
    scored = []
    for r in rows:
        if not r["phash"]:
            continue
        distance = bin(int(target) ^ int(r["phash"])).count("1")
        scored.append((distance, {k: r[k] for k in r.keys() if k != "embedding"}))
    scored.sort(key=lambda kv: kv[0])
    return [{"distance": d, **row} for d, row in scored[:max(1, limit)]]


def search(query: str, *, limit: int = 5, db_path: Optional[Path] = None,
           embedder=None) -> Dict[str, Any]:
    """Semantic lookup with a keyword fallback that says it is the fallback."""
    vector = (embedder or embed)(query)
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM refs").fetchall()
    finally:
        conn.close()
    if not rows:
        return {"available": True, "mode": "empty", "matches": []}
    if vector:
        scored = []
        for r in rows:
            raw = r["embedding"]
            if not raw:
                continue
            try:
                other = [float(x) for x in json.loads(raw.decode("utf-8"))]
            except (ValueError, UnicodeDecodeError):
                continue
            scored.append((_cosine(vector, other),
                           {k: r[k] for k in r.keys() if k != "embedding"}))
        if scored:
            scored.sort(key=lambda kv: -kv[0])
            return {"available": True, "mode": "embedding",
                    "matches": [{"score": round(s, 4), **row}
                                for s, row in scored[:max(1, limit)]]}
    terms = [t for t in query.lower().split() if len(t) > 2]
    matches = []
    for r in rows:
        hay = f"{r['brand']} {r['product']} {r['kind']} {r['prompt']}".lower()
        score = sum(1 for t in terms if t in hay)
        if score:
            matches.append((score, {k: r[k] for k in r.keys() if k != "embedding"}))
    matches.sort(key=lambda kv: -kv[0])
    return {"available": True, "mode": "keyword_fallback",
            "note": "the embedding lane was unavailable; ranking is keyword only",
            "matches": [{"score": s, **row} for s, row in matches[:max(1, limit)]]}


def stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    conn = connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM refs").fetchone()["n"]
        with_vec = conn.execute(
            "SELECT COUNT(*) AS n FROM refs WHERE embedding IS NOT NULL").fetchone()["n"]
        brands = [r["brand"] for r in conn.execute(
            "SELECT DISTINCT brand FROM refs WHERE brand<>'' ORDER BY brand").fetchall()]
    finally:
        conn.close()
    return {"total": total, "with_embedding": with_vec, "brands": brands,
            "store": str(STORE_ROOT.relative_to(ROOT)).replace("\\", "/")}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Stored reference library.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--brand", default="")
    parser.add_argument("--product", default="")
    parser.add_argument("--kind", default=None)
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int, default=10)
    ns = parser.parse_args(argv)

    if ns.stats:
        print(json.dumps(stats(), indent=2))
        return 0
    if ns.query:
        print(json.dumps(search(ns.query, limit=ns.limit), indent=2, default=str))
        return 0
    rows = find(brand=ns.brand, product=ns.product, kind=ns.kind, limit=ns.limit)
    print(json.dumps({"count": len(rows), "rows": rows}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
