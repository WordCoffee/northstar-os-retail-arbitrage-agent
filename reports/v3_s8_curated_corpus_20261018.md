# V3 S8 — Curated corpus + retrieval (local index, honest provenance)

**Date:** 2026-10-18 · **Branch:** `feature/v3-simple-view` · **Status:** BUILT, tests green, local commit.

## What this closes

The plan's S8: ingest pre-aggregated local indices into a local SQLite index with
license + provenance per record — resumable, honest counts, no scraping, no paid
services — and make them retrievable from the shell. This was **greenfield**: the
repo had no corpus/index/embedding/FTS code, and the Memory Bank (§8) is a
separate per-account store.

## Design rules honoured

- **Local files only.** The ingest reads the operator's own `research/**` tree and
  sweep files. No network, no scraping, no paid service.
- **Provenance + licence, as reported.** Every record stores its `source`, the
  `license` **as reported by the source sweep** (a `null` stays `null`), and a
  `provenance` blob (query, stars, byte counts, origin file). The engine never
  upgrades an unknown licence.
- **Resumable + honest counts.** Ingest is idempotent by `(source, source_id)` +
  a content hash — a re-run reports `skipped`, not re-inserts. Each run records
  `inserted/updated/skipped/errors` and up to 20 per-record errors; a missing path
  is an honest `error`, never a silent success.
- **No raw paths.** The ingest surface accepts a **known source name** (or `all`),
  never a filesystem path — there is no path-traversal surface.
- **Honest about search.** Search is deterministic keyword matching (LIKE + a
  light relevance rank). It is **not** semantic/vector; that is the documented
  upgrade, not a claimed feature.

## Pieces

| Piece | Where | What |
|---|---|---|
| Schema | `corpus_schema.py` | `corpus_records` (shared/global) + `corpus_ingest_runs`; unique `(source, source_id)`. Additive only. |
| Store | `data_layer.py` `CorpusDB` (`NorthstarDB.corpus`) | Idempotent `upsert`; `search` (LIKE + rank); `stats`; `list_records`; run lifecycle. |
| Ingest | `corpus_ingest.py` | Tolerant loaders + `ingest_source` / `ingest_records` / `ingest_all`. |
| Service | `corpus_router.py` `/api/corpus/*` | `search` · `stats` · `runs` · `ingest`. |
| Shell hook | `chat_tools.py` `corpus_search` (Research + Grow) | Top matches with source + licence; honest when empty. |

## Evidence

```
python -m py_compile corpus_schema.py corpus_ingest.py corpus_router.py data_layer.py chat_tools.py shell_focus.py  → PY OK
python -m py_compile main.py                                                                                       → MAIN PY OK
python -m pytest test_corpus.py                                                                                    → 21 passed
python -m pytest test_corpus test_seo_ops test_seo_learning test_seo_listing test_seo_profiles \
                  test_shell_modes test_chat_plan test_chat_core test_chat_fork test_chat_tools \
                  test_tool_gateway test_voicestudio_adapter                                                        → 189 passed
corpus_router.routes → /api/corpus/{search,stats,runs,ingest}                                                       → all present
```

`test_corpus.py` (21) covers: the GitHub sweep loader (UTF-8 BOM, `items` as dict,
malformed line skipped, `null` licence preserved, pipe/mojibake cleaning); the CSV
and HF loaders; the docs loader (heading → title); idempotent upsert
(inserted/skipped/updated) and the required-key check; search ranking, source
filter, empty query; stats; run lifecycle; the ingest driver's counts + error cap;
unknown-source `ValueError`; missing-path honest error; a real end-to-end HF
ingest; the `corpus_search` tool (registration + focus, matches, empty, needs-a-
query); and the router (`search`/`stats`, ingest unknown-source → 400).

## Honest limits / next

- **Counts:** raw pre-aggregated records are well under 20,000 (the sweeps total
  ~8k unique, plus docs). 20,000 is aspirational and would come from **doc
  chunking**, not from scraping. No number is inflated.
- **No local MCP registry file exists** — MCP data lives only as rows inside the
  sweeps. The ingest says so rather than inventing an index.
- **Next:** the vector index (`qwen3-embedding:0.6b` + sqlite-vec) and automatic
  retrieval injection into the Master Brain's context (today retrieval is an
  explicit `corpus_search` tool + `/api/corpus/search`).
- Nothing was pushed; all work is local on `feature/v3-simple-view`.
