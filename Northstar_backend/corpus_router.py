"""Curated corpus router (V3 S8) — retrieval over the operator's own local index.

Read-only search + stats, plus an ingest that reads LOCAL files only (no
scraping, no network, no paid services) and is idempotent. The ingest surface
accepts a known source NAME, never a raw path — there is no path-traversal
surface here.

Honesty boundaries:
  • Results are third-party metadata with the license AS REPORTED by the source
    sweep — the response says so; it never asserts a licence is safe to use.
  • Search is deterministic (LIKE + a light relevance rank); it is not a semantic
    vector search. That upgrade is documented, not implied.
  • Ingest writes to local SQLite only; it arms no live/paid action.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import corpus_ingest  # noqa: E402
from data_layer import get_northstar_db  # noqa: E402
from design_studio_api import studio_account  # noqa: E402

router = APIRouter(prefix="/api/corpus", tags=["corpus"])

_SEARCH_CAVEATS = [
    "Third-party metadata from local index files; licence is as reported by the source sweep.",
    "Deterministic keyword search — not a semantic/vector lookup.",
]


class IngestIn(BaseModel):
    source: str = Field(..., min_length=1, max_length=40)


@router.get("/search")
def search(q: str, limit: int = 20, source: Optional[str] = None,
           acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not str(q or "").strip():
        return {"query": q, "count": 0, "matches": [], "caveats": _SEARCH_CAVEATS}
    rows = db.corpus.search(q, limit=min(max(int(limit), 1), 100), source=source)
    return {"query": q, "count": len(rows), "matches": rows, "caveats": _SEARCH_CAVEATS}


@router.get("/stats")
def stats(acct: str = Depends(studio_account)):
    db = get_northstar_db()
    out = db.corpus.stats()
    out["sources"] = sorted(corpus_ingest.SOURCES)
    return out


@router.get("/runs")
def runs(limit: int = 20, acct: str = Depends(studio_account)):
    return {"runs": get_northstar_db().corpus.list_runs(limit=min(max(int(limit), 1), 100))}


@router.post("/ingest")
def ingest(body: IngestIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if body.source == "all":
        return {"results": corpus_ingest.ingest_all(db)}
    try:
        return corpus_ingest.ingest_source(db, body.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
