# V4.1 §5.4 — Embeddings Drift Engine (local semantic lane)

**Date:** 2026-10-18
**Branch:** `feature/v4.1-mesh` (V3 baseline tagged `v3-final-stable` at `5c3022f`)
**Scope:** Step 2 of the V4.1 Cloud-Local Hybrid Mesh plan — local embeddings lane +
`sqlite-vec` + automatic drift detection against historical SQP data.

All work is local-only. Nothing was pushed. No credential was read, printed or
committed. No real-money action was taken.

---

## 1. What was built

A local semantic lane over the V3 S8 curated corpus, entirely on this machine.

| File | Change |
|---|---|
| `Northstar_backend/corpus_drift.py` | **NEW** — the drift engine: `EmbeddingLane`, `VectorStore`, pure drift math, high-level `vector_search` / `drift_report` / `embed_now`. |
| `Northstar_backend/corpus_router.py` | Added `GET /api/corpus/search/vector`, `GET /api/corpus/drift`, `POST /api/corpus/embed`. Existing `/search`, `/stats`, `/runs`, `/ingest` untouched. |
| `Northstar_backend/chat_tools.py` | Added tools `corpus_vector_search` + `corpus_drift` (AG-UI cards). |
| `Northstar_backend/shell_focus.py` | Added both tools to the **Grow** and **Research** focus subsets. |
| `Northstar_backend/test_corpus_drift.py` | **NEW** — 35 offline tests (fake lane, in-memory sqlite-vec). |
| `Northstar_backend/requirements.txt` | Added `sqlite-vec>=0.1.9` (SQLite-only vector lane). |
| `NORTHSTAR_V3_MASTER_PLAN.md` | §5.4 marked BUILT (embeddings drift); §6 + roadmap updated. |
| `00_STATE.json` | `current_phase` entry prepended. |

### Components

- **`EmbeddingLane`** — wraps the local Ollama embeddings endpoint
  (`http://127.0.0.1:11434/api/embeddings`, model `qwen3-embedding:0.6b`, 1024-d).
  Raises `EmbeddingUnavailable` on **every** failure mode (HTTP error, connection
  refused, timeout, malformed body, empty text, empty vector). It never returns a
  fabricated or zero-filled vector.
- **`VectorStore`** — `sqlite-vec` `vec0` virtual table (`float[1024]`,
  `distance_metric=cosine`) plus `corpus_vector_meta` (rowid → `record_id`/`source`/
  `source_id`) and `corpus_drift_snapshots`. `upsert` is keyed by `record_id` and
  replaces the previous vector atomically; `search` supports `limit`, `threshold`
  and `source` filtering.
- **Drift math** (pure, no I/O): `cosine_similarity`, `cosine_distance`, `centroid`,
  `compute_drift`. `compute_drift` reports the cosine distance between the corpus
  centroid and the historical **SQP-query** centroid. It is a *measured* value — the
  code and the API caveats say so explicitly: **not a trend, forecast or cause.**

## 2. Version pinning / environment

- `sqlite-vec` was installed via `pip install sqlite-vec` → **0.1.9** (already pinned
  into `requirements.txt`).
- `qwen3-embedding:0.6b` was **pulled** locally (`ollama pull`, 639 MB, free/local —
  not a paid action). Correcting an earlier misread: at first the model was *not*
  present (a truncated `ollama list` had been misread); it is present now.
- The lane loads **alongside** the resident `northstaros-qwen3.8:27b` model.

## 3. Evidence (real, reproducible)

| Check | Result |
|---|---|
| `sqlite-vec` cosine sanity | identical vectors → distance `0.0`; orthogonal → `1.0` |
| `python -m pytest test_corpus_drift.py -q` | **35 passed, 0 failed** |
| Combined chat/shell/seo/corpus suites | **222 passed, 0 failed** |
| Full backend (excl. pre-broken `costco_non_kirkland`) | **3668 passed / 11 failed / 65 skipped** — all 11 failures **pre-existing and unrelated** |
| Real end-to-end via the live lane | see below |

### Real end-to-end run (temp DB, live Ollama lane)

```
lane available : True
embed corpus   : {'available': True, 'embedded': 3, 'errored': 0, 'pending_seen': 3}
embed sqp      : {'available': True, 'embedded': 3, 'errored': 0, 'pending_seen': 3}
stats          : {'total': 6, 'dim': 1024, 'by_source': {'corpus': 3, 'sqp': 3},
                  'model': 'qwen3-embedding:0.6b', 'metric': 'cosine'}
vector search  : True [('mushroom supplement', 0.082208), ('d1', 0.206196),
                       ("lion's mane powder", 0.285477)]
drift          : {'available': True, 'metric': 'cosine-centroid', 'drift': 0.20121,
                  'similarity': 0.79879, 'n_current': 3, 'n_historical': 3}
```

The query `mushroom supplement sourcing` ranked the SQP query `mushroom supplement`
first (0.082), then the Lion's Mane sourcing doc (0.206) — semantically sensible with
**real 1024-d vectors**, not fixtures.

## 4. Regression honesty

The full backend suite reports 11 failures. Every one was shown to be **pre-existing**
by running the backend-runnable failures (9 of the 11) with and without these changes
staged (`git stash`), obtaining the **identical** failing set both times. The remaining
two (`foundation/tests/test_frontend_gate.py::test_v3_shell_invariants` asserting an
`App.jsx` route count; `test_owner_test_mode_non_bypass.py::test_frozen_file_boundary_is_a_static_rule`)
are UI/static-file assertions that these changes do not touch. `test_ui_route_contract.py`
only fails on *missing* paths; this change only **adds** routes.

Pre-existing repo issue, **not** introduced here: `costco_non_kirkland/tests` has 3
collection errors (`brightdata_costco_enrichment.py` no longer exports
`build_enrichment_manifest` / `is_costco_product_url`; last touched by unrelated commit
`a2238ec`). These were excluded from the run above; they do not involve this change.

## 5. Honesty boundaries carried forward

- Vector search is an **additional** mode. Deterministic keyword search is unchanged
  and remains the default.
- `sqlite-vec` is **SQLite-only**; on the Postgres backend the lane is simply absent
  and the API says so.
- Every embedding-dependent surface returns `available: false` + the real reason when
  the lane is down — never a fabricated match or a zero vector.
- Drift is a measured cosine distance; no trend, forecast or causal claim is made.

## 6. Still open / next

- **S8 auto-injection**: retrieval into the Master Brain context is still an explicit
  tool call (`corpus_search` / `corpus_vector_search`) + `/api/corpus/*`; automatic
  injection remains the documented next step.
- Populating the **production** vector store (`POST /api/corpus/embed`) over the real
  corpus + the operator's imported SQP history is an operator-window step.
- Step 3 (operator-window REA capture harness, Packify) and Step 4 (verification /
  build + shell harness) of the V4.1 plan follow.
