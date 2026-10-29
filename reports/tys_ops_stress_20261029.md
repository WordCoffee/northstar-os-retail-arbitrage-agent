# Tys Assistant — operations layer + exhaustive stress run

**Date:** 2026-10-29
**Branch:** `feature/chrome-connect-3.0`
**Commit:** `59cec0bf` (layer + API + tests + docs), `482e8bda` (JSON-repair fix)
**Machine report:** `reports/master_execution_stress_test_report.json`
**Tests:** `python -m pytest test_tys_ops.py test_tys_assistant.py test_chat_core.py test_rate_limit_posture.py test_chromeconnect_api.py -q` → **145 passed**

---

## 1. What was built

| Module | Responsibility | Key behaviour |
|---|---|---|
| `tys_ops/storage.py` | local-master media ledger | free 1 GB images / **zero** video retention; paid 10 GB tier; prunes **unprotected** media only; refuses with `over_quota` + byte deficit; session-end purge; 100-profile cap |
| `tys_ops/bridge.py` | cloud sync edge | HMAC tokens (TTL, scopes, revocation, 60 s skew); offline queue with idempotency, bounded backoff, dead letters; monotonic sync envelopes; https-only gateway |
| `tys_ops/validators.py` | structural + semantic checks | headings, sentence floor, placeholder markers, unchanged-from-seed, JSON keys, hunk arithmetic (`agent_kernel` first), workspace acceptance that outranks self-report |
| `tys_ops/memory.py` | long-term context | hashed 256-dim index, cosine retrieval, extractive budgeted compression, epistemic facts with supersession / conflict audit / unlearn |
| `tys_ops/budgets.py` | throttling | per-task and per-day token caps (fail-closed), VRAM reservation that refuses, UCB1 tuner, feedback router |
| `tys_ops/selfheal.py` | resilience | read-only diagnostics, safe pid liveness (no signalling), stale locks, atomic write with verified rollback, conservative JSON repair |
| `tys_ops/ui.py` | adaptive UI | validated `tys.ui.v1` tree, personalisation by usage, degraded render never drops a region |
| `tys_ops/stress.py` | harness | 100-profile load on the real queue, storage thresholds, fault injection, convergence, live gateway burst |

API additions: `GET /api/admin/tys/state?fresh=1` (3 s snapshot by default),
`GET /api/admin/tys/ui`, `GET /api/admin/tys/storage`.

## 2. Defects found and fixed during the run

1. **State endpoint serialised every lane probe.** 100 concurrent
   `GET /state` calls produced **92 client timeouts** at ~26 s p50; each request
   re-probed Chrome Connect (~1.5 s) on a single-worker event loop.
   Fixed with `TysAssistant.cached_state(ttl=3 s)` plus an explicit `?fresh=1`.
   Result: 100/100 served, p95 ≈ 113 ms once warm; the cold snapshot still
   costs ~1.5 s and is reported separately (`cold_ms`).
2. **Per-kind quota ignored the total cap.** A 10 GB paid profile accepted a
   2 GB image while 3 GB of retained video was already stored. Image admission
   now uses `min(image_quota, total_quota − retained_video)`. The stress phase
   now reproduces the refusal: `over_quota`, deficit 1 GB.
3. **JSON repair rewrote smart quotes.** Turning `“`/`”` into `"` terminates a
   JSON string, so repairing a document containing curly quotes *corrupted* it.
   Repair is now BOM + trailing-comma only; a smart quote inside a string is
   preserved verbatim. Covered by a test.
4. **Gateway rate limiting engaged under a burst.** In an earlier 100-request
   burst, 3 calls returned `429`. This is the gateway working, not a routing
   failure: the throttled calls succeed after a 2 s backoff, and the offline
   queue already retries with bounded exponential backoff. The final sustained
   run recorded 0 throttles (100/100 served). Reported either way, never hidden.

## 3. Measurements (sustained run)

**Concurrent load — 100 profiles, 2 tasks each, 50 rounds over ~9 minutes**

| | |
|---|---|
| work orders submitted | **10,000** |
| completed `done` | **10,000** |
| failures / lock errors | **0** |
| throughput | ~22 tasks/s steady (round 1 = 22.18, round 50 = 22.47) |
| task latency p50 | 4.55 s (round 1) → 4.27 s (round 50) |
| task latency p95 | 4.89 s → 4.47 s |
| queue rows after every round | 200 for the round, isolated temp SQLite |

The run lasted 557.9 s (50 rounds). Latency is dominated by deliberate
serialisation on the single-writer queue (`TysStore` holds one locked
connection by design) and by the simultaneous barrier start; adding workers
would not make the queue faster, it would only move the wait.

**Live gateway burst — 100 concurrent `GET /api/admin/tys/state`**

| | |
|---|---|
| served | 100 / 100 |
| p50 / p95 | 71 ms / 118 ms |
| throughput | ~693 req/s |
| cold snapshot recorded at phase start | 76 ms in this run |

Earlier standalone probes measured the cold snapshot at 1.5–1.6 s while the
Chrome Connect CLI was cold, and 92/100 requests timed out before
`cached_state` existed. Both numbers belong to the record: the fix is what
turned a serialised 1.5 s probe per request into a served burst, and the cache
still expires after 3 s on purpose.

**Storage thresholds**

* 100 profiles registered; the 101st refused with `profile_cap_reached`.
* 110 × 12 MB images (1.32 GB attempted) into a 1 GB free profile → all
  admitted, 25 prune events, final usage 1,069,547,520 B < 1 GB, zero refusals.
* Downloaded media is never evicted: second 600 MB image refused with a
  176 MB deficit while the protected 600 MB item stayed active.
* Free-tier video → `not_stored`, `retention_seconds=0`, `must_download=true`,
  prompt returned at session end.
* Paid 10 GB: 6 GB image + 3 GB video stored; a further 2 GB image refused
  (`over_quota`, deficit 1 GB, binding cap 7 GB); video expired after 31 days.
* Real file written for the purge test: present before session end, removed
  after; purge count 1.

**Bridge**

* Token: verified, expired, revoked, tampered and scope-denied paths all
  produce stable codes.
* Offline queue: 10 operations, transport failing with `TimeoutError`, all 10
  delivered after backoff — **no loss**; a permanently failing queue produces
  dead letters, not silent drops.
* Dedupe by idempotency key returns `duplicate`; replayed sync envelope returns
  `replay_ignored`; plaintext HTTP on a public host is refused.

**Fault injection and self-healing**

* Bad hunk header (`-1,5 +2,9` over a 2/2 body) detected by
  `agent_kernel.content.validate_patch` with the exact arithmetic message;
  after correcting the header the patch validates.
* Missing heading + placeholder + sentence floor all flagged; repaired text
  passes.
* Missing artifact and a failing command both beat a `"done"` self-report
  (`self_report_outranked = true`).
* Atomic write with a rejecting verifier → `rolled_back`, file restored
  byte-identical; clean write → `written` with a backup.
* Dead-pid lock (999999) flagged `stale_lock`; the process is never signalled.

**Convergence, tuning, UI, memory**

* Three 20-brief passes: **20/20, 20/20, 20/20**, max 1 repair iteration.
* UCB1 tuner: 240 trials, tail of 60 shows a stable dominant arm per bucket
  (65% share, two arms still explored) — converged, not frozen.
* Adaptive UI: 40 renders, 0 degraded, 0 dropped regions, 13 distinct versions,
  component whitelist respected, malformed state still yields a complete tree.
* Memory: retrieval hit contains the queried term; compression 30 tokens inside
  a 60-token budget; supersession contradiction detected, conflict audited,
  unlearn recorded.

## 4. What this run did **not** do

1. **Not multi-hour.** The sustained phase ran ~9 minutes (50 rounds, 10,000
   tasks). `python -m tys_ops.stress --minutes 180` runs the same loop for
   longer; the duration in the JSON is always the run's own.
2. **No model lanes.** The 27B coding worker and the Bojo planner were not
   started; every order carried explicit steps. Coding quality is covered by
   the existing kernel benchmarks, not by this harness.
3. **Volumes are accounted, not materialised.** Gigabytes are bytes in a real
   ledger; only the purge test writes a real file.
4. **Dynamic DNS is described, not registered.** The bridge returns the record
   the operator's DNS client should publish.
5. **The adaptive UI is a spec, not a browser render.** The SPA consumes
   `tys.ui.v1`; no visual regression test was run.
6. **`00_STATE.json` was not written.** The fragment
   `state/fragments/20261029_tys_ops.json` validates (`--check` → would add
   `tys_ops_20261029`) and awaits the operator's `--apply`, per the registry's
   own rule.

## 5. Reproduce

```powershell
cd Northstar_backend
python -m pytest test_tys_ops.py test_tys_assistant.py -q
python -m tys_ops.stress --profiles 100 --tasks-per-profile 2
python -m tys_ops.stress --minutes 10
```

Two owner gates were never approached: no spend, no Amazon request. The only
network call in the harness is the optional loopback probe against the already
running backend.
