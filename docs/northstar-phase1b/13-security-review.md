# 13 — Security Review

## Secrets

- **No secret values were read, printed, copied, written, or logged** during Phase 1B.
- Env var NAMES only, where referenced (none are consumed by the foundation).
- Frontend scans for hardcoded credential literals: none introduced.
- Audit + observability redaction is implemented and tested (`test_audit.py`,
  `test_repositories.py::test_logger_redacts`).

## Provider safety

- No external provider call was made.
- `ProviderRegistry.execute_write` always refuses (`write_not_permitted`).
- `execute_read` refuses disabled providers (`provider_disabled`).
- The only model execution in the whole project remains the Phase 0 **local Ollama** call
  (disclosed in the Phase 0 package §R1); Phase 1B added none.
- GET routes perform zero provider activity (verified by API tests).

## Authorization

- Server-side RBAC enforced in every route (`_require`), verified live:
  viewer → `403`, operator → success.
- Preview cannot elevate (`min(real_role, target_role)`) — unit tested.
- Sandbox blocks `write_external` — unit tested.

## Data safety

- No production DB write. The dry-run tool uses a read-only SQLite URI.
- Additive schema only; migrations not applied.
- Protected files, benchmark fixtures, and Phase 0/1A docs untouched.

## Findings (new this phase)

| ID | Finding | Severity | Mitigation |
|---|---|---|---|
| S1 | Foundation auth uses a **header-based dev shim** (`X-User-Id`, `X-Role`, `X-Env`) | **BLOCKING (amendment R1)** | **Enforced in code**: `deps.enforce_local_only()` rejects non-loopback clients with 401 before any context is built; no foundation data route (incl. preview) is reachable remotely. Replace with real JWT/org resolution as Phase 1C item **1C-01, first and alone** (see `19-amendments-and-blockers.md`). |
| S2 | Foundation temp DB is ephemeral | Low | Replace with Postgres + migration apply in a reviewed step (Phase 1C). |
| S3 | Existing `tools/test_chrome.py` hardcodes test credentials (pre-existing) | Medium | Not touched this phase; flagged for Phase 1C removal. |
| S4 | `northstar.db` git-modified (pre-existing runtime cache writes) | Low | Not modified this phase; read-only URI used by the dry-run tool. |

## Mitigation priority for Phase 1C

1. Replace the dev auth shim with real authentication/authorization (blocker before any
   exposure beyond localhost).
2. Apply the foundation migration to a **staging** Postgres only.
3. Remove hardcoded test credentials from `tools/*`.