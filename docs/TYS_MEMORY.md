# Tys memory — semantic index and API

Long-term memory is a SQLite file with two retrieval paths:

* **hashed (default, model-free):** 256-dim bag-of-words, exact cosine, works when
  the GPU/worker is stopped;
* **semantic (opt-in):** 1024-dim embeddings from the **local** Ollama runner
  (`qwen3-embedding:0.6b`) stored in a `sqlite-vec` `vec0` table with cosine
  distance. If the embedder or extension fails, the index disables semantic mode
  for the process and falls back to hashed — a search never fails because a model
  is down.

## API (admin-gated, `/api/admin/tys`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/memory/stats?account=` | chunks, tokens, live facts, `semantic` flag/reason |
| POST | `/memory/text` | `{account, text, source}` → chunk ids |
| GET | `/memory/search?q=&account=&k=` | top-k hits with score and `semantic` |
| POST | `/memory/facts` | `{account, subject, predicate, value, confidence, source}` |
| GET | `/memory/facts?account=&include_superseded=` | live/superseded facts |

The service opens `Northstar_backend/data/tys_memory.db` with `semantic=True`.
Chunks written before semantic mode was enabled are backfilled lazily (32 per
search) so an old index does not silently disappear from results.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `NORTHSTAR_MEMORY_SEMANTIC` | `0` | default for a bare `MemoryIndex`; the API passes `semantic=True` explicitly |
| `NORTHSTAR_EMBED_MODEL` | `qwen3-embedding:0.6b` | local Ollama embedding model |
| `NORTHSTAR_EMBED_URL` | `http://127.0.0.1:11434/api/embeddings` | local runner endpoint |
| `NORTHSTAR_EMBED_TIMEOUT` | `30` | seconds before fallback |

## Live check (2026-11-04)

```
POST /api/admin/tys/memory/text   -> {"chunks":1,"semantic":true}
GET  /api/admin/tys/memory/search -> score 0.6629, semantic true
GET  /api/admin/tys/memory/stats  -> {"semantic":true,"semantic_reason":""}
```

The service was started with `ENVIRONMENT=development` on `127.0.0.1:8000` and the
dev identity shim (`X-User-Id: demo-t2`, `X-Role: operator`) for the check.
