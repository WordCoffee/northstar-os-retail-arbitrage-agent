# BUILD STATE — NorthstarOS Master Build Plan

Source of truth for build progress. Re-read at the start of every card; update after every card.
Plan: `docs/NORTHSTAROS_MASTER_BUILD_PLAN.md` (copied from owner attachment 2026-09-28).
Branch: `build/master-plan`. Base commit: `5967f7e`.

## Cards

| Card | Status | Commit | Notes |
|---|---|---|---|
| P0-T1 State capture | DONE | 1711edd | branch `build/master-plan` created; db backed up; BACKUP_SHA256=A4684F36DCF760870A3B4707D174C72C9A9FB370CAF08010620EB3562C99D0AD |
| P0-T2 Two-repo reconciliation | DONE | | default B applied; pipeline config reference renamed (config-only, no file move); contract in `docs/DATA_CONTRACT.md` |
| P0-T3 Constitution diff | DONE | | `docs/PLAN_CONSTITUTION_CHECK.md`; 21 items COMPATIBLE, 1 NEEDS-AMENDMENT (test-mode self-approval; safe default applied) |
| P0-T4 Env sanity check | DONE | | `docs/ENV_SANITY_REPORT.md`; hazards: .env L98 malformed (key whitespace), northstar-os-retail-arbitrage-agent/.env L13 unquoted whitespace, Northstar_backend/.env L32 duplicate-key; 112 code-referenced names absent from .env.example. No values printed. Owner fixes `.env`. |
| P1-T1 Baseline | DONE | | all four UI harnesses pass (40/8/26/11); backend invite+auth 23 passed + foundation auth subset 108p/7s; costco 217p/0f (plan expected 191 — see Baseline); test_frontend_gate.py 2 failed/23 passed (known) |
| P1-T2 Fix test_frontend_gate.py | DONE | | replaced retired Sidebar.jsx + "Legacy UI disabled" assertions with v3 invariants; gate 25 passed/0 failed |
| P1-T3 Frontend defects F1-F11 | DONE | | F1-F8,F11 fixed (F9/F10 deferred to P8). App.jsx hosts F2/F3/F4 and was committed once. Harnesses green: smoke 40/0, guards 11/0, acceptance 26/0, invite 11/0; frontend gate 25/0 |
| P2-T1 Hosting intake | DONE | | owner silent; default applied: local Docker Compose only, no public URL, no domain/VPS yet |
| P2-T2 Containerize | DONE | | Dockerfile.api/.ui, Caddyfile, docker-compose.yml (api/worker/scheduler/postgres/caddy/migrate); GET /api/v1/foundation/health added; stack verified: health ok (db_backend=postgres), UI 200 at http://127.0.0.1/ui/. Existing compose preserved as docker-compose.local.yml. Pre-existing malformed root `.env` (line 98) blocks plain `up`; used `--env-file .env.example` |
| P2-T3 BrowserRouter migration | DONE | | App.jsx HashRouter->BrowserRouter basename="/ui"; BetaInviteAccept links/router nav; four harnesses rewritten to path routing; direct load /ui/golden-goose 200 + renders; smoke 42/0, guards 11/0, acceptance 27/0, invite 11/0; frontend gate 25/0 |
| P2-T4 Postgres in hosted mode | DONE | | DB_URL canonical (+legacy FOUNDATION_DB_URL); migrate entrypoint records `schema_migrations` + checksum drift; startup check fails closed in hosted env (dev no-op). Compose stack: migrations 7/7, ledger=7, api health ok. SQLite foundation suite 642 passed/58 skipped/0 failed. Postgres suite 45 passed/0 failed against a self-spun disposable PG (127.0.0.1:55443, `northstar-pg-testrun`), torn down after. Test guards decoupled from port 55432 via `NORTHSTAR_PG_TEST_PORT/USER/DB` env. |
| P2-T5a Owner credential storage + bootstrap | DONE | | `foundation/credentials.py` (bcrypt, dedicated `owner_credentials` table), forward migration `008_owner_credentials.sql`, interactive `foundation_seed_owner.py` (getpass, idempotent, refuses ambiguous/remote/prod targets; no password in output), `state.py` db_path authoritative over env. Tests: 8 passed/1 skipped SQLite, 9 passed vs disposable PG; no password/hash in output. |
| P2-T5b Backend auth and session | DONE | | `foundation/auth_session.py` (HS256 mint matching validator, HttpOnly session cookie Path=/api/v1/foundation, double-submit CSRF cookie, per-process login throttle); deps reads session cookie + CSRF on unsafe methods; router `POST /auth/login`, `POST /auth/logout`; no token in body; hosted fail-closed (dev shim ignored, Secure cookie). Tests 8 passed; auth/invite/authorization subset 157 passed/9 skipped/0 failed. |
| P2-T5c UI sign-in and route guards | DONE | | `foundation/dev.js` explicit local-dev switch; api.js cookie transport (`credentials:include`, CSRF header, login/logout, no hosted token); session.jsx always resolves identity from /me (empty user_id = signed out) + logout revokes cookie; SignIn.jsx real login (local demo only when LOCAL_DEV); harnesses set `window.__NORTHSTAR_LOCAL_DEV__=true`; invite stub returns 401 when signed out. Harnesses: smoke 42/0, guards 11/0, acceptance 27/0, invite 11/0; frontend gate 25/0; auth subset 119 passed/8 skipped; SQLite suite 658 passed/59 skipped/0 failed; disposable PG 62 passed; PG torn down. |
| P2-T5 acceptance (hosted HTTPS sign-in) | PARTIAL | | implementation complete; hosted-HTTPS owner sign-in UNVERIFIED (needs a real URL + operator-created owner credential). Not claimed. |
| P2-T6 prep (LOCAL VERIFICATION) | PARTIAL | | local only; not deployed. Shared DB login throttle (migration 009) + hosted fail-closed without shared store. Live browser walkthrough `northstar-os-ui/verify-live-signin.cjs` against local Compose: 14 passed / 0 failed — sign-in -> /ui/home; no token in localStorage; NO local-dev flag in served build; protected load + refresh stay authenticated; /me=internal_platform_admin; logout no-CSRF 403 / with-CSRF 200; /me after logout 401; signed-out /ui/monitoring -> /ui/sign-in; 8 expected non-2xx resource notices, 0 unexpected console errors, 0 uncaught JS exceptions, 0 failed requests. HTTP only — NOT a hosted-TLS test. Test owner seeded + cleaned up. |

## Backup record

- `backups/northstar.db.bak` from `Northstar_backend/data/northstar.db`
- SHA256 `A4684F36DCF760870A3B4707D174C72C9A9FB370CAF08010620EB3562C99D0AD`
- Size 7,815,168 bytes; checksum matches source at capture time.

## Working-tree notes

- At P0-T1 the working tree was dirty and included FROZEN files
  (`costco_non_kirkland/brightdata_costco_enrichment.py`, `enrichment.py`, `cli.py`).
  These are NOT staged and will NOT be edited or committed (Plan 1.1.6).
- `docs/NORTHSTAROS_MASTER_BUILD_PLAN.md` did not exist in the repo; the owner's
  attached plan was copied in so in-repo references resolve.

## Assumptions

1. (P0-T2) Applied default **B** for the two-repo decision: Foundation repo is the
   hosted product; `fba-product-screener` stays a separate repo exchanging data
   via a documented ingest contract (`docs/DATA_CONTRACT.md`). Owner silent.
2. (P0-T3) Applied safe default for owner-test-mode **self-approval**: permitted
   for non-purchase actions only; any real purchase still needs a fresh explicit
   named owner approval per Constitution §3 (score/self-approval alone never
   yields `PURCHASE_READY`). Owner silent.
3. (P2-T1) Applied default hosting posture: **local Docker Compose only, no
   public URL, no domain or VPS** until the owner supplies (1) domain, (2) VPS
   provider, (3) other users' emails. Owner silent.

## Open Questions

- OQ-1 (P0-T2): owner decision A/B/C. Default B applied.
- OQ-2 (P0-T2): approval to physically rename pipeline `data/northstar.db` ->
  `data/pipeline_northstar.db` (file move deferred; config reference only).
- OQ-3 (P0-T2): whether pipeline `data/products.db` is ingested or stays
  pipeline-internal.
- OQ-4 (P0-T3): owner ruling on test-mode self-approval. Status: OPEN. Gated off
  via `NORTHSTAR_OWNER_SELF_APPROVAL=0` until owner replies option A. Draft
  amendment proposed (Plan addendum §6).
- OQ-5 (P2-T1): domain name, VPS provider, and additional user emails (Tyler).
  Default applied: local Compose only, no public URL (Assumptions #3).
- OQ-6 (P2-T3): RESOLVED. Base path `/ui` (addendum). Acceptance = direct load of
  `/ui/golden-goose`. Harness target via `HARNESS_BASE_URL` (default
  `http://127.0.0.1/ui/`); port 8104 is out of scope.

## Owner Answers

Resolved in the resume kickoff (addendum, 2026-09-28) — do not re-ask:
- Base path: `/ui` (addendum precedence over plan). Acceptance = direct load of `/ui/golden-goose`.
- Harness target: use `HARNESS_BASE_URL` (default `http://127.0.0.1/ui/`). Do not touch/inspect/kill any process on port 8104 or other ports not covered by this var.
- Root `.env` line 98: owner fixes manually outside the session. Do not edit `.env`. P0-T4 reports hazards only, never values.
- Self-approval: `NORTHSTAR_OWNER_SELF_APPROVAL=0` (disabled) until owner replies option A to the P0-T3 ASK OWNER block (printed once this session).
- P0-T2 two-repo: default B (two repos + ingest contract) per prior assumption.
- P2-T1 hosting: local Compose only until domain/VPS/email supplied.

## Baseline (P1-T1, 2026-09-28, branch build/master-plan)

| Check | Command | Result | Expected |
|---|---|---|---|
| UI build | `npm run build` (run in `northstar-os-ui`) | OK, 83 modules, 0 errors | OK |
| Smoke | `node verify-smoke.cjs` | 40 passed / 0 failed | 40 |
| Guards | `node verify-guards.cjs` | 8 passed / 0 failed | 8 |
| Acceptance | `node verify-acceptance.cjs` | 26 passed / 0 failed | 26 |
| Invite flow (UI) | `node verify-invite-flow.cjs` | 11 passed / 0 failed | 11 |
| Backend invite+auth | `pytest test_invite_flow.py test_auth_rbac.py test_auth_schema.py -q` | 23 passed / 0 failed | — |
| Foundation auth/invite | `pytest Northstar_backend/foundation/tests -q -k "auth or invite or authorization"` | 108 passed / 7 skipped (Postgres) / 578 deselected | — |
| Frontend gate | `pytest Northstar_backend/foundation/tests/test_frontend_gate.py -q` | 2 failed / 23 passed (KNOWN: Sidebar.jsx missing; "Legacy UI disabled" marker absent) | 2 known failures |
| Costco plain | `pytest costco_non_kirkland/tests -q` | 217 passed / 0 failed | 191 (see note) |
| Costco non-frozen (VERIFIED baseline) | `pytest costco_non_kirkland/tests -q --ignore=<4 test_brightdata_*.py>` | 172 passed / 0 failed | new baseline |

Reconciliation (spec vs disk, per §5):
- Root `npm run build` fails in this environment: the root script uses
  `npm --cwd northstar-os-ui run build`, and the installed npm treats `--cwd` as
  a package spec (`npm error 404 northstar-os-ui`). Running `npm run build`
  with workdir `northstar-os-ui` succeeds. Candidate frontend defect (F-class)
  for P1-T3.
- Costco 191->217 delta verification (addendum §5, required). Per-file counts in
  the current tree: test_brightdata_preflight 9, test_brightdata_campaign 13,
  test_brightdata_manifest 13, test_brightdata_schema_test 10 (all four are the
  frozen Bright Data test files) = 45; test_enrichment_identity 20 (modified
  frozen-adjacent). The three untracked frozen files (campaign/manifest/
  schema_test = 36) are part of the increase over HEAD; the plain 217 therefore
  **includes frozen Bright Data tests**. The 191->217 delta (+26) is NOT a clean
  non-frozen delta. Verified non-frozen count: **172 passed / 0 failed**
  (excluding the four `test_brightdata_*` files). If test_enrichment_identity.py is
  also treated as frozen, the count is 152. Treat 172 as the Costco non-frozen
  baseline; 217 stays the plain-collection number only.

## Credentials Status (names only, never values)

| Name | Provider | Status |
|---|---|---|
| (none recorded) | | |