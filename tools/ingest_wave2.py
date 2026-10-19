"""Ingest Research Wave 2 outputs into the local corpus index.

Runs the registered wave-2 sources through corpus_ingest (provenance + license
per record, content-hash idempotent) and prints honest per-source counts.

Usage: python tools/ingest_wave2.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import corpus_ingest  # noqa: E402
from data_layer import get_northstar_db  # noqa: E402

WAVE2 = [name for name in corpus_ingest.SOURCES if name.startswith("wave2_")]


def main() -> int:
    db = get_northstar_db()
    results = []
    for name in WAVE2:
        try:
            res = corpus_ingest.ingest_source(db, name, repo_root=str(ROOT))
        except Exception as exc:  # noqa: BLE001 - one bad source must not stop the rest
            res = {"source": name, "status": "error", "counts": {}, "errors": [str(exc)[:200]]}
        results.append(res)
        print(json.dumps({"source": name, "status": res.get("status"),
                          "counts": res.get("counts"),
                          "errors": (res.get("errors") or [])[:2]}), flush=True)
    try:
        stats = db.corpus.stats()
    except Exception as exc:  # noqa: BLE001
        stats = {"error": str(exc)[:200]}
    print(json.dumps({"corpus_stats": stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
