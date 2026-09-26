# 01 — Pre-flight and Baseline

**Date:** 2026-09-23

## 1. Pre-flight correction (control-character scan)

The terminal earlier rendered `§G`/`§R1` in a way that looked like non-printable
characters. Investigation:

- Method: read the raw bytes of every file under `docs/northstar-discovery/` and
  `docs/northstar-phase1/`; counted bytes `< 0x20` excluding TAB/LF/CR.
- **Result: zero control characters in any Phase 0 or Phase 1 file.**
- The `§` symbol is the valid UTF-8 section sign (bytes `C2 A7`), which is intended
  content (e.g. `17-evidence-index.md` §G, §R1).
- **Conclusion: a terminal/encoding rendering artifact, not a file-content problem.**
  No documentation correction was required for the `§` characters. (Earlier Phase 0
  *content* corrections for the git record and Ollama disclosure were already applied;
  see `17-evidence-index.md` of the Phase 0 package — meaning unchanged.)

`writes_performed` for the scan: **0** (read-only).

## 2. Baseline (pre-implementation)

| Item | Value |
|---|---|
| Branch | `main` (protected — no push performed) |
| Python | 3.14.5 |
| Node / npm | v24.15.0 / 11.12.1 |
| Available Python deps | fastapi ✓, pydantic ✓, pytest ✓, httpx ✓, uvicorn ✓, **sqlalchemy ✗** |
| Existing migrations | `migrations/001_core_auth.sql`, `002_productivity.sql`, `003_golden_goose.sql` — all NOT APPLIED |
| Frontend build state | `northstar-os-ui/dist/` present; `node_modules/` present |
| Production-like DB | `Northstar_backend/data/northstar.db` (read-only use only) |

Because SQLAlchemy is unavailable, the foundation uses **stdlib `sqlite3`** with a thin
abstraction, keeping the package dependency-light and fully offline-testable.

## 3. Existing tracked/untracked state (at baseline)

The working tree already contained pre-existing session modifications (runtime cache
writes from earlier live-mode work and earlier UI work). Phase 1B did not revert them;
it added new files and made small additive edits (see `02-files-changed.md`).

## 4. Safe test commands identified

| Command | Safety |
|---|---|
| `python -m pytest Northstar_backend/foundation/tests -q -p no:cacheprovider` | offline, temp-DB, no providers |
| `cd northstar-os-ui && npm run build` | offline build |

## 5. Pre-implementation expectations (files expected to change)

- NEW: `Northstar_backend/foundation/**`, `Northstar_backend/migrations_foundation/**`,
  `Northstar_backend/tools/foundation_migrate_dryrun.py`, `northstar-os-ui/src/foundation/**`.
- MODIFIED (additive): `Northstar_backend/main.py`, `northstar-os-ui/src/{App.jsx,main.jsx}`,
  `northstar-os-ui/src/components/{Header,Sidebar,Icon}.jsx`, `northstar-os-ui/src/data/services.js`.

## 6. Explicitly out of scope

Service page rebuilds; database migration application; provider execution; live writes;
secret access; AGENTS.md/constitution edits; deployment; commits/pushes.