# Lane A report — `block5-production-hardening`

Queue rank 11. Branch `staging`, worktree `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`.
No `git add`, no `git commit`, no push. Everything below is left in the tree.

**Verdict: unit complete.** The repository can now prove it is production-shaped
with one command (`python Northstar_backend/production_assert.py`), and that
command is itself tested, including negative controls. 12/12 checks pass, 0
fail, 10 advisories, exit 0.

---

## 0. Incident: an unauthorised autonomous lane reverted this work

At `2026-11-11T16:11:59Z` the scheduled `tys` watchdog (`tools/tys_launcher.py`,
PID 14804) judged an unrelated item (`sel-05-dieline`) and called
`_revert_candidate()`, which reverts **every path that changed after its
dispatch snapshot**. My three new modules and my edits to `main.py` /
`rate_limiter.py` were in that set:

```
{"event": "reverted_bytes", "item": "sel-05-dieline",
 "paths": ["Northstar_backend/data/northstar.db", "Northstar_backend/main.py",
           "Northstar_backend/rate_limiter.py", "Northstar_backend/test_seller_deterministic.py",
           "tools/seller_tester/deterministic.py", "Northstar_backend/production_assert.py",
           "Northstar_backend/production_health.py", "Northstar_backend/sqlite_backup.py",
           "reports/ty/verify_20261111.md"]}
                                      -- state/tys_runner/launcher.jsonl
```

What I did, in order:

1. Diagnosed it from `state/tys_runner/launcher.jsonl` and
   `tools/tys_launcher.py:651` (`_restore`) / `:770` (`_revert_candidate`), not by
   guessing.
2. Re-created all five files from scratch inside the manifest, and from then on
   kept a mirror in `%TEMP%\opencode\block5\` (the approved temp root) so a
   second revert could not cost the unit again.
3. Verified no data loss: `Northstar_backend/data/northstar.db` is **tracked** in
   git, so the revert restored it from HEAD rather than deleting it; all six
   SQLite stores pass `PRAGMA quick_check` (`ok`).
4. Recorded it here. The director has since stopped that lane and added a lease
   guard (`a12d6511`), so it cannot start while this session holds the lease.
   A byte-identical copy of every file this lane produced is kept at
   `%TEMP%\opencode\block5\` (manifest paths preserved), so one `Copy-Item`
   restores the unit if the tree is reverted again before the director commits.

The revert also revealed a real defect in my own first draft: `backup_store()`
opened the live store read-write, which is why `northstar.db` appeared as a
changed path at all. The module now opens every source **read-only**
(`Northstar_backend/sqlite_backup.py:241`) and a test asserts the source bytes
and mtime are untouched by a backup.

---

## 1. What changed (file:line)

### New — the assertion script

`Northstar_backend/production_assert.py` (1,313 lines)

| Line | What |
|---|---|
| `:70` | `REGISTERED_SECRET_GAPS` — four secrets the app reads that `.env.example` does not document |
| `:88` | `REGISTERED_SECRET_FALSE_POSITIVES` — the one scanner pattern that fires on shipped code, with its reason |
| `:120` | `REGISTERED_HOSTED_KEY_GAPS` — three hosted keys missing from `.env.example` |
| `:138` | `INNERHTML_ALLOWLIST` + the "bare variable" rule |
| `:229` | `ui.dist_production_shaped` — hashed assets, no source maps, hashed refs |
| `:278` | `ui.served_bundle_clean` — runs `tools/check-prod-bundle.cjs` |
| `:296` | `ui.no_untrusted_innerhtml` — expression/allowlist/derivation guard |
| `:466` | `secrets.repo_clean` — scans tracked source/config, classifies findings, fails on shipped-code findings |
| `:577` | `config.env_example_covers_secrets` — parses the real import graph from `main.py`, compares with `.env.example` |
| `:631` | `config.env_example_covers_hosted` — `deploy/hosted.env.example` vs `.env.example` + compose |
| `:684` | `config.dev_bypass_guarded` — functional: `production`/`staging` refuse the shim, `development` needs loopback + header; AST check that the gate is `environment() == "development"` |
| `:788` | `redaction.enforced` — logs a fake key/bearer/JWT through the real handler, asserts `[REDACTED]`, asserts filter + formatter wiring |
| `:892` | `health.endpoints_answer` — boots `main:app` in a subprocess and probes four endpoints |
| `:928` | `backup.restore_drill` — backup → verify → restore → integrity + row counts, in a temp dir |
| `:1003` | `rate_limits.enforced` — 30 allowed, 1 throttled, headers, prod opt-out refused |
| `:1139` | `docs.checklist_commands` — the doc cannot drift from the code |
| `:1220` | `run()` / `:1283` `main()` — `--json`, `--only`, `--strict`, `--root`, `--list`; exit 0/1/2 |

### New — readiness for the API process

- `Northstar_backend/production_health.py` (`:169` `readiness_snapshot()`,
  `:50`-`:165` the six checks, `:195` `probe_local()`). Local, side-effect free:
  rate-limit posture, redaction wiring, writable data dir, UI build (critical in
  production-like envs), Foundation store (`PRAGMA quick_check`), live posture.
- `Northstar_backend/main.py:990-1012` — `GET /readyz` **and** `GET
  /health/readyz` (the second one is inside Caddy's existing `handle /health*`
  rule, so no root-file change was needed). 200 when ready, **503** with
  `failed_checks` when not.

### New — SQLite backup / verify / restore

`Northstar_backend/sqlite_backup.py` (530 lines)

| Line | What |
|---|---|
| `:57` | `STORE_INVENTORY` — six stores, each with its existing env override and purpose |
| `:166` | `_load_optional_extensions()` — loads `sqlite_vec` when present so `chunk_vec` can be counted |
| `:194` | `inspect_database()` — `integrity_check`, `user_version`, per-table counts, unreadable virtual tables |
| `:236` | `backup_store()` — `VACUUM INTO` from a **read-only** connection + manifest (SHA-256, size, counts, extensions) |
| `:346` | `verify_backup()` — size/hash first (a changed file is never read as SQLite), then integrity + counts |
| `:394` | `restore_backup()` — refuses an existing target without `force`, restores via a temp file, re-verifies, writes a receipt |
| `:458` | CLI — `inventory` / `backup` / `verify` / `restore`, `--json`, `--receipt` |

### Changed

- `Northstar_backend/rate_limiter.py:177` — the four probe paths
  (`/health`, `/health/detailed`, `/health/readyz`, `/readyz`) are exempt from
  the bucket, so a readiness probe can never be answered with a 429.

### New — docs and tests

- `docs/PRODUCTION_READINESS.md` — the checklist: 30 rows, each with a command,
  every one of the 12 check ids cited, the seven config gaps named with the exact
  lines to add, and a "what this lane did not do" section.
- `Northstar_backend/test_production_assert.py` (32 tests) — asset hashing,
  innerHTML negative controls, doc/code drift, the real-repo integration claims,
  JSON shape, a crashing check reported as a failure, and the full end-to-end run.
- `Northstar_backend/test_production_health.py` (11 tests) — snapshot, critical
  vs non-critical, UI-build criticality by environment, sqlite vs postgres store,
  200/503 routes, rate-limit exemption, a live `probe_local` against a real
  loopback server.
- `Northstar_backend/test_production_sqlite_backup.py` (18 tests) — manifest
  contents (no row data), source never written, tampered byte, count drift,
  unknown schema, missing file, round-trip equality, refuse-without-force,
  force replace, receipt, CLI paths and exit codes.
- `Northstar_backend/test_production_rate_limits.py` (7 tests) — limits, throttle
  + headers, probe exemption, real app mounts the limiter, opt-out refused in
  production/staging.

`Northstar_backend/test_production_readiness_scan.py` is **not** mine: it dates
from 2026-11-05 and tests the unrelated `tools/production_readiness_scan.py`.
It was not modified.

---

## 2. Exact commands and their real output

All run from the repo root, Windows, Python 3.14.5 / SQLite 3.50.4.

```text
python Northstar_backend/production_assert.py
  PRODUCTION-SHAPED: 12 passed, 0 failed, 0 skipped, 10 advisories
  exit 0

python Northstar_backend/production_assert.py --strict --only secrets.repo_clean
  NOT PRODUCTION-SHAPED: 1 passed, 0 failed, 0 skipped, 2 advisories
  --strict: advisories are treated as failures
  exit 1

python -m pytest Northstar_backend/test_production_sqlite_backup.py \
                  Northstar_backend/test_production_health.py \
                  Northstar_backend/test_production_assert.py \
                  Northstar_backend/test_production_rate_limits.py \
                  -q -p no:cacheprovider --basetemp "$env:TEMP\opencode\block5\pt7"
  68 passed, 1 warning in 25.68s

python -m pytest Northstar_backend/test_rate_limit_posture.py \
                  Northstar_backend/test_rate_limit_dev_shim.py \
                  Northstar_backend/test_ui_route_contract.py \
                  Northstar_backend/test_live_posture_guard.py \
                  Northstar_backend/test_live_containment.py \
                  Northstar_backend/test_silent_failures.py \
                  Northstar_backend/test_jwt_secret_posture.py \
                  Northstar_backend/test_alpha_gate.py tests/security \
                  -q -p no:cacheprovider --basetemp "$env:TEMP\opencode\block5\pt8"
  218 passed, 1 warning, 19 subtests passed in 12.56s
```

Per-check wall time on the recorded run (measured, not estimated):

```text
ui.dist_production_shaped                  0.0s pass
ui.served_bundle_clean                     0.2s pass
ui.no_untrusted_innerhtml                  0.1s pass
secrets.repo_clean                         9.5s pass
config.env_example_covers_secrets          2.6s pass
config.env_example_covers_hosted           0.0s pass
config.dev_bypass_guarded                  0.4s pass
redaction.enforced                         0.0s pass
health.endpoints_answer                    1.6s pass
backup.restore_drill                       1.3s pass
rate_limits.enforced                       0.1s pass
docs.checklist_commands                    0.0s pass
```

The `--json` report (schema `northstar.production_assert.v1`) is the machine
artefact: `{"ok": true, "summary": {"pass": 12, "fail": 0, "skip": 0,
"advisory": 10}, "checks": [...]}` with per-check `evidence`.

---

## 3. Checklist status, row by row

| # | Claim | Check id | Status | Evidence from the run |
|---|---|---|---|---|
| 1 | UI build is production-shaped | `ui.dist_production_shaped` | PASS | 78 content-hashed assets (4.38 MB), 0 source maps, `index.html` references only hashed assets |
| 2 | Served bundle has no dev shim / test hook | `ui.served_bundle_clean` | PASS | `check-prod-bundle.cjs`: 14 passed, 0 failed over 67 files (1.4 MB prod + 1.0 MB test), positive control present |
| 3 | No untrusted `dangerouslySetInnerHTML` | `ui.no_untrusted_innerhtml` | PASS | 2 uses, both allowlisted (`Icon.jsx` static table, `Dielines.jsx` local print-engine SVG); every value is a file-local variable |
| 4 | No secret in shipped code | `secrets.repo_clean` | PASS | 3,300 source/config files scanned; 4 shipped findings, all the same registered pattern false positive; 40 test fixtures + 2 reports + 2 tools reported as advisory; 11,474 evidence/media files declared not scanned |
| 5 | Secrets the API reads at import time are documented | `config.env_example_covers_secrets` | PASS with 4 registered gaps | 123 import-time keys; gaps `CANOPY_API_KEY`, `EASYPARSER_API_KEY`, `RAPIDAPI_KEY`, `VOICESTUDIO_API_KEY`; full graph: 169 of 209 names absent (optional knobs) |
| 6 | Hosted deploy keys are documented | `config.env_example_covers_hosted` | PASS with 3 registered gaps | 15 hosted keys; gaps `DB_URL`, `NORTHSTAR_JWT_ALGORITHMS`, `NORTHSTAR_OWNER_SELF_APPROVAL` |
| 7 | Dev bypass unreachable outside development | `config.dev_bypass_guarded` | PASS | production and staging refuse an `X-User-Id` loopback request; development needs the explicit header; the gate is an AST-verified `environment() == "development"` |
| 8 | Logs and error paths never emit credentials | `redaction.enforced` | PASS | a fake key, bearer header and JWT (message **and** traceback) become `[REDACTED]`; `RedactionFilter` + `RedactingFormatter` are both attached by `logging_config.setup_logging()` |
| 9 | Health and readiness endpoints exist and answer | `health.endpoints_answer` | PASS | `/health`, `/health/detailed`, `/readyz`, `/health/readyz` all 200 with JSON; `/readyz` reports six checks |
| 10 | Backup/restore is documented and tested | `backup.restore_drill` | PASS | 6 stores, 60,034 rows backed up, all verified, 2 restored and integrity-checked (foundation 384 rows/61 tables, tys_memory 9 rows/7 tables incl. a `sqlite-vec` table) |
| 11 | Rate limits are configured and enforced | `rate_limits.enforced` | PASS | 30 anonymous requests allowed, 31st is 429 with `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `Retry-After`; production opt-out refused |
| 12 | The checklist cannot drift from the code | `docs.checklist_commands` | PASS | 30 rows, every one with a command; all 12 checks documented; all 7 registered gaps named |

Two rows are "PASS with registered gaps" by design: the gap is reported on every
run, `--strict` fails on it, and the doc names the exact `.env.example` lines to
add. That is deliberate — see §4.

---

## 4. What I could not do, and why

1. **`.env.example` is at the repo root, outside my write manifest.** Seven keys
   the app really reads are therefore registered rather than documented:
   `CANOPY_API_KEY`, `EASYPARSER_API_KEY`, `RAPIDAPI_KEY`, `VOICESTUDIO_API_KEY`,
   `DB_URL`, `NORTHSTAR_JWT_ALGORITHMS`, `NORTHSTAR_OWNER_SELF_APPROVAL`. The
   exact lines are in `docs/PRODUCTION_READINESS.md` §2.3; applying them turns
   `--strict` green.
2. **`docker-compose.yml` / `Dockerfile.api` are outside the manifest.** The API
   container still healthchecks `/health`; it should point at `/health/readyz`,
   and the `api` service has no `healthcheck` block at all. Documented in §8.
3. **`npm run build` was not run.** It writes `northstar-os-ui/dist`, outside the
   manifest, and the release lane owns the build. The script verifies the
   artefact that is in the tree (and the dist changed under me twice during this
   lane — 75 → 78 assets — which is why the numbers are labelled "recorded run").
4. **`northstar-os-ui/src` was not edited.** `Dielines.jsx` injects an SVG string
   returned by the local print engine; I reviewed it and allowlisted it **with a
   structural guard** (bare variable, derived in-file) rather than changing UI
   code outside the manifest. A reviewer may still prefer to render it as a data
   URL; that is a UI-lane decision.
5. **`.secret_scan_baseline.json` is outside the manifest.** 44 findings outside
   shipped code (40 test fixtures, 2 reports, 2 tools) remain un-baselined;
   `python -m northstar.security.secret_scan --tracked` still exits 1. Reported,
   not hidden.
6. **Postgres readiness is not probed by `/readyz`.** The check reports
   `backend=postgres, checked=false` and the reason (compose dependency +
   migrate gate). A DB ping with a timeout belongs with the compose change in
   (2).

---

## 5. The one thing a verifier should re-run

```powershell
python Northstar_backend/production_assert.py --json
```

Expect `exit 0`, `"ok": true`, `"summary": {"pass": 12, "fail": 0, "skip": 0,
"advisory": 10}`, and a `checks[]` entry per claim with its `evidence`. Then:

```powershell
python -m pytest Northstar_backend/test_production_assert.py Northstar_backend/test_production_sqlite_backup.py Northstar_backend/test_production_health.py Northstar_backend/test_production_rate_limits.py -q -p no:cacheprovider
```

Expect `68 passed`. If `--strict` is the acceptance bar, expect `exit 1` until
the seven `.env.example` lines from §2.3 are added.

Gates held: no Amazon request, no spend, no credential read, no login, no
browser, no GPU, no `git add`/`commit`/push, no policy or allowlist edit.
