# 1.5 — BOJO INFRASTRUCTURE & API INTEGRATION
## Phase 2 research deliverable — REA program

**Date:** 2026-10-28
**Scope:** what is actually load-bearing in the orchestration substrate, where
two jobs can collide, and the smallest set of additions that removes operator
friction — sized to a single 16 GB laptop, not to a cloud.
**Method:** code trace + three local measurements + recorded system telemetry.
**Spend:** 0. **Amazon contact:** 0. **New services installed:** 0.

Instrument: `tools/rea_bojo_probe.py` → `reports/rea_probe/bojo_probe.json`

---

## 1. The job path, traced from code

```
browser (simple mode / studio UI)
  │  HTTP
  ▼
FastAPI (Northstar_backend/main.py)
  │
  ├── design_studio_async.py:87   _EXECUTOR = ThreadPoolExecutor(max_workers=2)
  │        └── job row in ds_jobs: status queued → running → done
  │            credits: reserve → commit | release  (credit_ledger.py)
  │
  ▼
studio_generation.generate_image()            (:618)
  ├── media_live_armed() gate                  (:620)
  ├── unload_brain()  → Ollama /api/ps, evicts EVERY resident model  (:622)
  ├── _fit_box(w,h)   → one scale factor into the 1216 px engine box  (:628)
  └── ComfyUI HTTP 127.0.0.1:8188 (COMFYUI_URL override)
        under _CrossProcessRenderLock         (:1274) — thread lock + file lock
  │
  ▼
PNG on disk → asset record (ds_assets) → tool result → chat part → UI card
```

Two structural facts fall out of the trace:

1. **The GPU is protected by a cross-process render lock**, not by a queue with
   visibility. Concurrency is therefore *serialised and invisible*: the second
   job waits, and nothing tells the operator it is waiting.
2. **`unload_brain()` runs inside the render call**, so a render mutates the
   *other* lane (the text model) as a side effect. That is a real coupling:
   render and chat cannot run concurrently, by construction.

---

## 2. Measurements

### 2.1 Host at probe time (2026-10-28)

| | Value |
|---|---|
| RAM total | 16.56 GB |
| RAM available | **4.92 GB** (70.3 % used) |
| VRAM total | 16,303 MB |
| VRAM free | **15,417 MB** |
| GPU util | 0 % |
| Listening | backend :8000, ComfyUI :8188, Ollama :11434 |

The binding constraint is confirmed as **RAM, not VRAM** — consistent with the
2026-10-22 finding that forced `--cache-none`.

### 2.2 Lane latency from the system's own telemetry (`lane_telemetry`, 52 rows)

| Lane / class | n | p50 | p95 | max | mean |
|---|---|---|---|---|---|
| `chat:default` / create | 43 | **35.3 s** | **268.0 s** | **2,039.7 s** | 117.6 s |
| `chat:default` / auto | 6 | 19.8 s | 38.3 s | 179.5 s | 43.3 s |
| `chat:default` / grow | 2 | 45.5 s | 29.3 s | 61.7 s | 45.5 s |
| `chat:default` / (none) | 1 | 8.2 s | — | — | 8.2 s |

**This is the most important number in the report.** Median create is 35 s, but
p95 is 268 s and the worst recorded turn took **34 minutes**. A user who hits
the p95 is not "waiting a bit longer" — they are in a different product. Tail
latency, not throughput, is what the substrate is failing at, and a message
broker does nothing for a single slow render.

Successful rows: 37 of 52 (71 %).

### 2.3 SQLite concurrent writers (disposable WAL database, 4 writers × 60 rows)

| `busy_timeout` | Attempted | Committed | Errors | Elapsed |
|---|---|---|---|---|
| **0 ms** | 240 | 60 | **180** (`database is locked`) | 0.30 s |
| **5000 ms** (the configured value) | 240 | **240** | **0** | 0.88 s |

**This refutes a hypothesis in the research plan.** SQLite write contention is
not a real risk *at the configured timeout*: with `busy_timeout=5000` (which
`Northstar_backend/data/northstar.db` actually reports) four concurrent writers
lose nothing and take under a second. The failure mode only exists if someone
sets the timeout to 0.

Consequence for the build plan: **Redis and RabbitMQ are not justified by
contention.** They would be justified by (a) durability across a process crash
and (b) queue visibility — and only (b) matches the measured problem (§2.2).

---

## 3. Collision risk register (ranked by measured impact)

| # | Risk | Likelihood | Blast radius | Existing mitigation | Gap |
|---|---|---|---|---|---|
| 1 | **Tail-latency hang** — one job runs 30+ min with no progress surface | **observed** (2,039 s) | operator abandons the session | async job row + polling | no per-stage progress, no stuck-job timeout, no "still working because X" |
| 2 | **Render evicts the text model** (`unload_brain`) | every render | chat stalls while the brain reloads | deliberate, to free VRAM | no announcement; the operator sees a slow reply, not a cause |
| 3 | **Invisible serialisation** via render lock | every concurrent render | second job waits with no ETA | cross-process lock | no queue depth, no wait time exposed |
| 4 | RAM spike killing ComfyUI with no traceback | when `--cache-none` is missed | render dies silently | canonicalised start script + docs | nothing checks the flag at call time |
| 5 | Disk below 10 GB pauses GPU work | periodic | whole creative lane stops | documented operational rule | not surfaced in the studio status |
| 6 | SQLite write contention | **refuted** at 5 s timeout (§2.3) | none measured | `busy_timeout=5000` | none |

The register is deliberately short. Six risks, one refuted, one observed — most
"infrastructure" work here would be solving #6, which measurement says is not
happening.

---

## 4. Provider limits: the design we already have is the right one

`quota_tracker.py:1-6` states the policy: counters are updated **only from a
403/429/quota header seen this run, or an operator drain** — i.e. the system does
not hardcode a guessed limit, it records what the provider said. `rate_limiter.py`
is the *edge* limiter (per-plan token bucket, with a startup assertion that
refuses to run with the harness opt-out in staging/production).

That is the correct posture, and it means the per-provider "limit matrix" from
the research plan is **documentation, not code**: there is nothing to change in
the retry path unless a provider's own header contradicts what we do.

`UNVERIFIED / DEBT`: the vendor docs for Unwrangle, DataForSEO, Bright Data,
Rainforest and RapidAPI were **not** fetched in this run, so the "documented vs
enforced" comparison is not done. Method when it is: read each provider's rate
policy, then replay the header values recorded in `quota_tracker.json` and flag
any provider where our backoff finishes before their reset window.

---

## 5. Asset metadata schema (kills the "everything is `asset`" class of bug)

The 2026-10-23 repair added `asset_meta` to tool parts. That fixed the *display*.
It did not fix the *store*, which is why the plan asked for a schema.

Proposed columns on `ds_assets` (additive; migrate via `foundation_migrate.py`):

| Column | Type | Why |
|---|---|---|
| `kind` | TEXT | `render` / `label_mockup` / `dieline` / `panel` / `video` / `audio` / `export` |
| `name` | TEXT | operator-facing name, not a uuid |
| `brand_id` | TEXT | findability by brand |
| `product_id` | TEXT | findability by product |
| `lane` | TEXT | which engine produced it |
| `brief_id` | TEXT | the turn/job that asked for it |
| `parent_asset_id` | TEXT | lineage: plate → label → mockup |
| `licence` | TEXT | `own` / `local-bench-only` / `unknown` |
| `width`,`height`,`bytes` | INTEGER | already implied; make it queryable |
| `geom_residual_px` | REAL | the label fit residual from 1.1 §5 — the single number that says whether a composite is trustworthy |

Index: `(brand_id, product_id, kind)`, `(brief_id)`, `(parent_asset_id)`.

The `geom_residual_px` column is the one that changes behaviour: it lets the UI
show "fit: 0.4 px" or "fit: 3.1 px — review" instead of "completed".

---

## 6. Monitoring spec, mapped to the four recorded failure classes

Each row is a failure that has actually happened here (`00_STATE.json`), so the
monitor is not speculative.

| Recorded failure | What to watch | Threshold | Where it would have fired |
|---|---|---|---|
| bare-uvicorn env loss (login 503, health green) | credential-login probe, not `/health` | 1 failed login probe | would have caught it in < 1 min |
| VRAM eviction false-positive | Ollama `/api/ps` re-read *after* eviction | any resident model | would have caught the qwen2.5vl leak |
| RAM kill with no traceback | ComfyUI process alive + last log line age | process gone mid-job | would have caught the edit-lane death |
| disk < 10 GB | free space on C: | < 10 GB warn, < 6 GB pause | would have caught the 5.83 GB day |
| **tail-latency hang** (new, measured) | job runtime vs p95 | > 2× p95 (≈ 9 min) → mark `stalled` | nothing today |

---

## 7. What we are NOT building, and why

| Candidate | Verdict | Reason |
|---|---|---|
| **Redis** | **no** | §2.3: contention refuted. Nothing measured needs an out-of-process cache. |
| **RabbitMQ** | **no** for now | the queue is not losing work; it is slow and opaque. Fix visibility first (a progress field + stall detector), then re-measure. |
| **PostgreSQL** | **no** | single writer on one laptop; WAL + 5 s timeout handles 4 concurrent writers with zero loss. |
| **Azure/AWS storage** | **no** | explicit no-cloud constraint; local disk is not the bottleneck (GPU/RAM is). |
| **Kubernetes / container orchestration** | **no** | one box, one GPU, one operator. |

The honest test that would change these answers: if jobs start *failing* under
concurrency (not merely waiting), or if a crash loses committed work, then a
durable broker earns its place. Neither is observed today.

---

## 8. BUILD CANDIDATES

| id | component | change | evidence (report §) | effort | risk | gate |
|---|---|---|---|---|---|---|
| B1 | `design_studio_async` | per-stage progress + `stalled` state when runtime > 2× p95 | §2.2: p95 268 s, max 2,039 s | 3 h | low | none |
| B2 | `ds_jobs` / assets | add the §5 metadata columns + indexes via `foundation_migrate` | §5 | 4 h | medium; migration on a live DB | none |
| B3 | `studio_generation` | assert ComfyUI was started with `--cache-none` before a heavy lane; refuse with the real reason | §3 risk 4 | 1 h | low | none |
| B4 | ops status | announce "brain evicted for render" so the chat stall has a cause | §3 risk 2 | 1 h | low | none |
| B5 | ops status | expose render-lock wait time / queue depth | §3 risk 3 | 2 h | low | none |
| B6 | monitoring | the five probes in §6, one scheduler tick | §6 | 3 h | low | none |
| B7 | provider parity | fetch the five vendors' rate policies and diff against recorded headers | §4 debt | 2 h | low | none |

**Rejected:** Redis, RabbitMQ, Postgres, any cloud store (§7), and any change to
`unload_brain`'s eviction behaviour — it is doing the job the GPU needs.

## 9. UNVERIFIED

- Provider rate-limit matrix (§4) — vendor docs not fetched.
- No instrumented render was fired at the live GPU lane; the probe deliberately
  avoided disturbing a serving stack, so *peak* RAM/VRAM per lane is not
  measured in this run. Lane latency (§2.2) is real recorded data; peak memory
  would need a quiet window.
- The 71 % success rate in `lane_telemetry` is not decomposed by failure cause;
  the table records `ok` only.
- Whether the 2,039 s outlier was one slow job or a stuck job: the schema has no
  stage timestamps, which is exactly what B1 adds.
