# Master Build Plan — session report (P0-T1 → P2-T2)

Date: 2026-09-28. Branch: `build/master-plan` (off `5967f7e`). Companion repo
`fba-product-screener` also on branch `build/master-plan`.

## Cards completed (with acceptance)

| Card | Status | Evidence |
|---|---|---|
| P0-T1 State capture | DONE | branch created; `backups/northstar.db.bak` sha256 A4684F36…; commit 1711edd |
| P0-T2 Two-repo reconciliation | DONE | `docs/DATA_CONTRACT.md`; default B; pipeline config reference renamed (config-only); main 39ba28f, companion 07e69ab |
| P0-T3 Constitution diff | DONE | `docs/PLAN_CONSTITUTION_CHECK.md`: 21 COMPATIBLE, 1 NEEDS-AMENDMENT (self-approval; safe default) 00ba0a8 |
| P1-T1 Baseline | DONE | smoke 40/0, guards 8/0, acceptance 26/0, invite 11/0; backend invite+auth 23/0; frontend gate 2 known failures; costco 217/0 (plan 191, reconciled) dc2f48c |
| P1-T2 Fix test_frontend_gate.py | DONE | v3 invariants; gate 25/0 cad937e |
| P1-T3 Frontend defects F1–F11 | DONE | F1–F8,F11 fixed (F9/F10 in P8); harnesses green after auth-gate fix; commits 1a25225…ab1e964 |
| P2-T1 Hosting intake | DONE | default local Compose only; assumption #3; a112b7e |
| P2-T2 Containerize | DONE | Dockerfile.api/.ui, Caddyfile, compose (api/worker/scheduler/postgres/caddy/migrate), `/api/v1/foundation/health`; stack verified: health ok (postgres), UI 200 at http://127.0.0.1/ui/; 4fd73f8 |

## Verification highlights

- Four UI harnesses: verify-smoke 40/0, verify-guards 11/0, verify-acceptance
  26/0, verify-invite-flow 11/0 (hosted build).
- `GET /api/v1/foundation/health` → `{"status":"ok","db_backend":"postgres"}`;
  UI served at `/ui/` (Caddy → static SPA; `/api/*` → FastAPI).

## Blockers / open questions

1. Pre-existing malformed root `.env` (line 98) → plain `docker compose up`
   fails parsing. Used `--env-file .env.example`. `.env` is a secret file and
   was not touched. Operator must fix line 98.
2. OQ-6 (P2-T3): BrowserRouter base path — keep `/ui` basename or move to root
   `/`; and identify the external server on port 8104 (+ SPA fallback support).
3. OQ-1/OQ-2/OQ-3 (P0-T2), OQ-4 (P0-T3), OQ-5 (P2-T1): owner rulings pending;
   safe defaults applied and logged in `docs/BUILD_STATE.md`.

## Next

P2-T3 BrowserRouter migration (accept: four harnesses pass with path routing;
direct load of `/golden-goose` works). Not started: base-path decision + unknown
harness server gate verification. See `docs/BUILD_STATE.md`.