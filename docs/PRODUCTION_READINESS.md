# Production readiness

This is the checklist the repository can **prove**, not the checklist someone
believes. Every row names a command; every command is either the assertion
script itself or a tool it invokes. Nothing here contacts a provider, reads a
credential value, spends money, or opens a browser.

```powershell
# the whole claim, one verdict
python Northstar_backend/production_assert.py --json

# human table, one area at a time
python Northstar_backend/production_assert.py
python Northstar_backend/production_assert.py --only ui
python Northstar_backend/production_assert.py --list
```

Exit code `0` = the repository is production-shaped. `1` = at least one claim
failed (the failing row names what and where). `2` = usage error. `--strict`
also fails on the tracked gaps in [§2.3](#23-known-config-documentation-gaps),
which the default run reports as advisories.

Last full run on this machine (Windows, Python 3.14.5, node 20): 12 of 12 checks
passed, 10 advisories, exit 0. The evidence for that run is
`reports/ty/lane_block5.md`.

---

## 1. The UI production build is production-shaped

| Area | Requirement | Command | What it proves |
|---|---|---|---|
| Build shape | `dist/` exists, every asset is content-hashed, no source maps are served, and `index.html` references only hashed assets | `python Northstar_backend/production_assert.py --only ui.dist_production_shaped` (`ui.dist_production_shaped`) | A cache cannot serve a stale bundle; no `.map` file exposes the source. Measured on the recorded run: 78 hashed assets (4.4 MB), 0 source maps. |
| Served bundle | the production bundle carries no dev shim (identity, `123abc`, `demo-t2`, `X-User-Id`, the runtime switch) and no `?engine=1` test hook | `python Northstar_backend/production_assert.py --only ui.served_bundle_clean` (`ui.served_bundle_clean`) | Runs `node tools/check-prod-bundle.cjs`. Measured: 14 passed, 0 failed over 67 files (1.4 MB prod + 1.0 MB test), with a positive control so the scan is not vacuous. |
| HTML injection | no `dangerouslySetInnerHTML` outside an allowlist, and every allowed use injects a **bare variable** the same file derives (never a prop, template, call result or request string) | `python Northstar_backend/production_assert.py --only ui.no_untrusted_innerhtml` (`ui.no_untrusted_innerhtml`) | Two reviewed uses: `Icon.jsx` (static SVG path table) and `Dielines.jsx` (SVG from the local print engine). A new file, or an expression instead of a variable, fails. |
| Build clean | the production build completes with no errors | `npm run build` (run in `northstar-os-ui/`; CI and the release lane own the build, this lane only reads `dist/`) | The build is produced by the release lane; the three rows above verify the artefact it produced. A stale `dist/` is visible above (an unhashed or missing asset fails the first row). |

## 2. Config and secrets

| Area | Requirement | Command | What it proves |
|---|---|---|---|
| No secrets | no secret value in the code that ships (backend, `northstar`, `shared`, `autothink`) | `python Northstar_backend/production_assert.py --only secrets.repo_clean` (`secrets.repo_clean`) | Scans every tracked source/config file (3,300) with `northstar/security/secret_scan.py`. Measured: 4 findings in shipped code, all the same registered pattern false positive (the `authorization:` parameter annotation in `operator_rea_capture.py`), 0 real values. Findings outside shipped code are classified (40 test fixtures, 2 reports, 2 tools) and reported; 11,474 tracked evidence/media/vendored files are declared as not scanned, and the whole-tree command remains `python -m northstar.security.secret_scan --tracked`. |
| Secrets documented | every secret-shaped key the API reads at import time is named in `.env.example` | `python Northstar_backend/production_assert.py --only config.env_example_covers_secrets` (`config.env_example_covers_secrets`) | Walks the real import graph from `Northstar_backend/main.py`, parses every env read, and compares with `.env.example`. Measured: 123 import-time keys, 4 registered gaps ([§2.3](#23-known-config-documentation-gaps)). |
| Hosted config | every key the hosted deploy requires is documented, or is a compose variable | `python Northstar_backend/production_assert.py --only config.env_example_covers_hosted` (`config.env_example_covers_hosted`) | Reads `deploy/hosted.env.example` and checks each name against `.env.example` and `docker-compose*.yml`. Measured: 15 keys, 3 registered gaps. |
| Dev bypass | the local identity shim is unreachable outside `ENVIRONMENT=development` | `python Northstar_backend/production_assert.py --only config.dev_bypass_guarded` (`config.dev_bypass_guarded`) | Proves it functionally: a loopback request with `X-User-Id` returns no identity under `production` and `staging`; under `development` it needs an explicit header. Also parses the AST of `dev_shim_enabled()` and refuses anything but `return environment() == "development"`. |
| Rate-limit opt-out | `NORTHSTAR_DISABLE_RATE_LIMIT=1` is refused in staging/production | `python Northstar_backend/production_assert.py --only rate_limits.enforced` (`rate_limits.enforced`) | Calls `assert_prod_posture()` with a production environment and requires the refusal; see [§6](#6-rate-limits). |

### 2.3 Known config documentation gaps

`.env.example` lives at the repository root, outside this lane's write manifest,
so the gaps below are **registered** rather than fixed: the check re-verifies
that each key is still read by the app (a stale entry fails), names it here, and
the default run reports it as an advisory. `--strict` fails until they are
documented. The fix for each is one commented line in `.env.example`:

```text
CANOPY_API_KEY=
EASYPARSER_API_KEY=
RAPIDAPI_KEY=
VOICESTUDIO_API_KEY=
DB_URL=
NORTHSTAR_JWT_ALGORITHMS=HS256
NORTHSTAR_OWNER_SELF_APPROVAL=0
```

| Key | Why it is not in `.env.example` yet | Command |
|---|---|---|
| `CANOPY_API_KEY` | secondary supplier adapter, optional, read at import time | `python Northstar_backend/production_assert.py --only config.env_example_covers_secrets` |
| `EASYPARSER_API_KEY` | secondary offer adapter, optional, read at import time | `python Northstar_backend/production_assert.py --only config.env_example_covers_secrets` |
| `RAPIDAPI_KEY` | legacy RapidAPI client, optional, read at import time | `python Northstar_backend/production_assert.py --only config.env_example_covers_secrets` |
| `VOICESTUDIO_API_KEY` | voice adapter, optional, read at import time | `python Northstar_backend/production_assert.py --only config.env_example_covers_secrets` |
| `DB_URL` | the hosted example and `auth`/`data_layer` use `DB_URL`; `.env.example` documents `FOUNDATION_DB_URL` | `python Northstar_backend/production_assert.py --only config.env_example_covers_hosted` |
| `NORTHSTAR_JWT_ALGORITHMS` | algorithm allowlist, defaults to `HS256` | `python Northstar_backend/production_assert.py --only config.env_example_covers_hosted` |
| `NORTHSTAR_OWNER_SELF_APPROVAL` | owner self-approval guard, defaults off | `python Northstar_backend/production_assert.py --only config.env_example_covers_hosted` |

The wider picture, reported by the same check: 209 distinct env names are read
across the whole import graph and 169 are absent from `.env.example`. Most are
optional tuning knobs with code defaults (model paths, cache TTLs, GPU
headroom); they are not secrets and the process starts without them.

## 3. Redaction

| Area | Requirement | Command | What it proves |
|---|---|---|---|
| Log redaction | log lines and tracebacks never carry a key, bearer token or JWT | `python Northstar_backend/production_assert.py --only redaction.enforced` (`redaction.enforced`) | Enforced by `northstar/security/redaction.py` (`RedactionFilter`, `RedactingFormatter`), wired into every handler by `logging_config.setup_logging()`. The check logs a fake key, a fake `Authorization` header and a fake JWT — including through `logger.exception` — and asserts the values do not appear and `[REDACTED]` does, and that the handler really carries the filter and the wrapped formatter. |
| Error paths | an exception message cannot leak a credential either | `python Northstar_backend/production_assert.py --only redaction.enforced` | The formatter redacts the **final** formatted string, so `record.exc_info`'s traceback is covered too; the check raises inside a `try` and asserts the traceback is clean. |

## 4. Health and readiness

| Area | Requirement | Command | What it proves |
|---|---|---|---|
| Liveness | `GET /health` answers 200 with JSON | `python Northstar_backend/production_assert.py --only health.endpoints_answer` (`health.endpoints_answer`) | Boots `main:app` in a **subprocess** with FastAPI's TestClient (no port, no egress). |
| Readiness | `GET /readyz` (and `/health/readyz` through Caddy's `/health*` rule) answers 200 `ready`, or **503** with the failing checks | `python Northstar_backend/production_assert.py --only health.endpoints_answer` | `northstar-backend`'s `production_health.readiness_snapshot()` asserts rate-limit posture, redaction wiring, a writable data dir, the UI build (critical in production-like envs), the Foundation store (`PRAGMA quick_check`) and the live posture. A wedged or misconfigured instance is drained, not served. |
| Detail | `GET /health/detailed` answers 200 and reports files, providers (names only), scanner mode, live posture, adapter load failures and data readiness | `python Northstar_backend/production_assert.py --only health.endpoints_answer` | The existing monitoring surface still works after the readiness route was added. |
| Compose probe | the API container healthcheck targets `/health`; the worker and scheduler target `/readyz` on 8090/8091 | `python Northstar_backend/production_assert.py --only health.endpoints_answer` (the route contract) and `docker compose config` for the compose wiring | The probes exist and answer; wiring a container to `/readyz` is a compose change (see [§7](#7-what-this-lane-did-not-do)). |

## 5. Backup and restore

| Area | Requirement | Command | What it proves |
|---|---|---|---|
| Backup | every present SQLite store is snapshotted consistently, with a manifest (SHA-256, size, `user_version`, per-table row counts) | `python Northstar_backend/production_assert.py --only backup.restore_drill` (`backup.restore_drill`) | `Northstar_backend/sqlite_backup.py` uses `VACUUM INTO` against a **read-only** connection, so a backup never writes to the live store. Measured: 6 stores, 60,034 rows. |
| Verify | a backup is refused unless hash, size, `integrity_check` and every row count match its manifest | `python Northstar_backend/production_assert.py --only backup.restore_drill` | `verify_backup()` raises on the first mismatch; nothing is "restored anyway". |
| Restore | a restore round-trips into a temp target, passes `integrity_check` and matches the manifests row counts, and refuses to overwrite a live file without `--force` | `python Northstar_backend/production_assert.py --only backup.restore_drill` | Measured: 2 stores restored and integrity-checked on every run (the foundation store and `tys_memory`, which carries a `sqlite-vec` virtual table). |
| Operator runbook | a human can take and restore a backup without the assertion script | `python Northstar_backend/sqlite_backup.py backup --dest backups/sqlite` then `python Northstar_backend/sqlite_backup.py restore --manifest <manifest.json> --target <path>` | The same module, with a CLI: `inventory`, `backup`, `verify`, `restore` (`--receipt` writes a restore receipt). Stop the writer before `--force`. Postgres is covered separately by `deploy/backup.sh` / `deploy/restore.sh` (`docs/hosted-readiness/BACKUP_RESTORE.md`). |

## 6. Rate limits

| Area | Requirement | Command | What it proves |
|---|---|---|---|
| Configured | per-plan budgets exist and the anonymous bucket is the tightest | `python Northstar_backend/production_assert.py --only rate_limits.enforced` (`rate_limits.enforced`) | Reads `RateLimitMiddleware.PLAN_LIMITS` and mounts the real middleware on a throwaway app. |
| Enforced | the 31st anonymous request in a minute is a `429` carrying `X-RateLimit-Limit` and `Retry-After` | `python Northstar_backend/production_assert.py --only rate_limits.enforced` | 30 allowed, 1 throttled, headers present — measured every run. |
| Mounted | the real app mounts the limiter, and the probe paths are exempt | `python Northstar_backend/production_assert.py --only rate_limits.enforced` | Asserts `app.add_middleware(RateLimitMiddleware` in `Northstar_backend/main.py`; `/health`, `/health/detailed`, `/health/readyz`, `/readyz` bypass the bucket so a probe can never be throttled. |

## 7. The checklist itself

| Area | Requirement | Command | What it proves |
|---|---|---|---|
| Doc/code parity | every row here carries a runnable command, every check id it cites exists, every check is documented, and every registered gap is named | `python Northstar_backend/production_assert.py --only docs.checklist_commands` (`docs.checklist_commands`) | The document cannot drift from the code: a deleted check, a renamed id, a row without a command, or a registered gap that stopped being named all fail. |

## 8. What this lane did not do

- **`.env.example` was not edited** (outside the write manifest). The seven gaps
  in [§2.3](#23-known-config-documentation-gaps) are one commit away.
- **`docker-compose.yml` / `Dockerfile.api` were not edited** (outside the
  manifest). The API container still healthchecks `/health`; pointing it at
  `/readyz`, and giving the `api` service a `healthcheck` block, is the next
  one-line change.
- **`npm run build` was not run** by this lane: it writes `northstar-os-ui/dist`
  (outside the manifest) and the release lane owns the build. The assertion
  script verifies the artefact that is in the tree.
- **`northstar-os-ui/src` was not edited**: the two `dangerouslySetInnerHTML`
  uses are reviewed and allowlisted with a structural guard rather than changed.
- **The secret-scan baseline was not extended**: `.secret_scan_baseline.json`
  is outside the manifest, so 44 findings outside shipped code (mostly test
  fixtures) are reported as an advisory instead of baselined, and
  `python -m northstar.security.secret_scan --tracked` still reports them.
