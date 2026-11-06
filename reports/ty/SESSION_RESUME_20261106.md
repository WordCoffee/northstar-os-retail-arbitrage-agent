# Session resume — 2026-11-06 (handoff #2, after the three security units)

A fresh session can continue from this file alone. Nothing here needs the previous chat.

## What landed this session (verified, committed)

Three W9 security units, one commit each, rollback tag before each:

| unit | commit | rollback tag | files |
|---|---|---|---|
| `T0-callback-ssrf` | `7570b18e` | `autonomy-cycle-32-pre` | `Northstar_backend/design_studio_async.py`, `test_design_studio_async.py`, `test_design_studio_openapi.py` |
| `T0-egress-hook` (remainder) | `ab2e26b0` | `autonomy-cycle-33-pre` | `Northstar_backend/main.py`, `test_egress_hook_startup.py` |
| `T1-dataforseo-host` | `96b5d83c` | `autonomy-cycle-34-pre` | `Northstar_backend/dataforseo_adapter.py`, `test_dataforseo_adapter.py` |

Verification (real output, not a claim):

```
python -m pytest -q test_design_studio_async.py test_design_studio_openapi.py \
  test_egress_guard.py test_egress_hook_startup.py test_live_posture_guard.py \
  test_dataforseo_adapter.py
-> 153 passed, 1 warning in 6.11s
```

What each one actually does:

1. **callback_url is now an SSRF-checked field.** `validate_callback_url()` refuses, with a
   named reason, anything that is not http(s) on a named host: Amazon hosts (via
   `tools/egress_guard.py`), IP literals (v4/v6, and the decimal/hex spellings such as
   `2130706433` and `127.1`), loopback names, link-local, private, unspecified. It runs twice —
   at submit, which returns **422 `callback_url_refused` with no job row created**, and again
   inside `deliver_webhook` before a `Request` object exists. A refused callback is recorded on
   the job's params (`webhook.refused: true`) and never fails a finished job.
   Optional operator controls: `DESIGN_CALLBACK_ALLOWED_HOSTS` (comma-separated suffixes) and
   `DESIGN_CALLBACK_ALLOW_LOOPBACK=1` (loopback only; link-local stays refused).
   **Reconciliation to know about:** `test_design_studio_openapi.py`'s two real delivery tests
   posted to `http://127.0.0.1:<port>`, which the new policy must refuse. They now opt in with
   `DESIGN_CALLBACK_ALLOW_LOOPBACK=1` — the only place in the repo that does, and the test
   proves opt-in still delivers.
2. **The service installs the egress guard at startup.** `main.install_egress_guard()` is the
   first statement in `lifespan()`, before the Ollama probe (the startup path's first outbound
   request). It fails **closed**: if `tools/egress_guard.py` cannot install, boot raises
   `EGRESS GUARD VIOLATION`. `test_egress_hook_startup.py` proves a call site that never mentions
   Amazon still refuses it with **0 transport calls**, and that the startup path installs the
   guard before the first HTTP call.
3. **`classify_endpoint` checks the host.** `DATAFORSEO_HOST = "api.dataforseo.com"`; https only,
   `parsed.hostname` compared exactly, checked *before* the path allowlist. Amazon, IP literals,
   lookalikes (`api.dataforseo.com.evil.test`) and host-less URLs are refused with the host named.

## The loop is STOPPED — read this before restarting it

`STOP` exists at the repo root (written by `python tools/tys_runner.py stop` at
2026-11-06T14:33:51Z). The watchdog exited cleanly (`STOP file present; watchdog exiting`).

Why: the launcher was reverting committed work. Cycle 35 (`T0-egress-hook`) failed and its
rollback restored its declared `write_paths` to a captured pre-state, which **deleted
`tools/egress_guard.py` — a file already committed at HEAD**. It did it twice; it also reverted
`Northstar_backend/main.py` mid-edit. Cycle 37 then took the lease on `T0-callback-ssrf`, the item
this session had just committed, so the loop was about to fight a completed unit.

**Before removing `STOP`:** fix `tools/tys_runner.py` (or wherever the cycle revert lives) so a
rollback restores tracked bytes with `git checkout -- <path>` and only deletes files it actually
created. Until then the loop can destroy committed work, and every session that starts while it
runs will keep re-doing the same unit. A lesson recording this is in `autonomy_queue.json`.

## Where things stand (verified, not claimed)

- The three W9 items above are `done` in `reports/ty/autonomy_queue.json` with their commits and
  verification lines.
- `tools/egress_guard.py` (14 tests) is present and installed by the service.
- Everything else from handoff #1 still holds: full suite green by name at the last full run
  (6,453 ids), watchdog/launcher built, write behaviour restores declared paths.
- **Not run this session:** the full suite (another lane held the box). Only targeted files were
  run, as instructed.

## Immediately next (queue order)

1. **Fix the revert-deletes-committed-files bug** (see above) before restarting the loop. This is
   now the highest-value item in the whole queue: it is the mechanism by which finished work
   disappears.
2. `S1-cancel-race` — cooperative-cancel ordering bug; needs the worker lane
   (`opencode run --agent tys --format json`), which was still returning no captured output.
3. `W0-c1` author/evaluator — most queue items still declare no `acceptance_commands`, so the
   launcher refuses them as `needs_author`. Build order: baseline restore (done) → pre-run red
   gate (done) → `tools/tys_evaluator.py` (G1/G2/G3/G3b) → per-candidate artifacts → rejection
   ledger → scope deriver → contract writer.
4. Small follow-up found this session, not started: `design_studio_api.GenerateIn` has **no**
   `callback_url` field, so the documented "submissions accept callback_url" contract is true only
   for `/assemble-async`. Adding the field is a one-line change plus a test; it was left out
   because it is outside the declared `write_paths`.

## How to verify anything here

```
python -m pytest -q test_design_studio_async.py test_egress_hook_startup.py   # run from Northstar_backend
python tools\egress_guard.py --check https://www.amazon.com/dp/X              # expect refused
python tools\tys_runner.py status                                             # expects "stop": true
git log --oneline -3                                                          # 96b5d83c, ab2e26b0, 7570b18e
```

## Rules that still bind

Amazon and spend are the only two gates needing fresh approval. `AGENTS.md` is append-only.
Rollback tag before every unit. Verification is command output, never a claim. Parallel lanes:
read-only always, writers only on disjoint `write_paths`, verification serialised, max 4.
