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
| P1-T1 Baseline | DONE | | all four UI harnesses pass (40/8/26/11); backend invite+auth 23 passed + foundation auth subset 108p/7s; costco 217p/0f (plan expected 191 — see Baseline); test_frontend_gate.py 2 failed/23 passed (known) |
| P1-T2 Fix test_frontend_gate.py | DONE | | replaced retired Sidebar.jsx + "Legacy UI disabled" assertions with v3 invariants; gate 25 passed/0 failed |
| P1-T3 Frontend defects F1-F11 | DONE | | F1-F8,F11 fixed (F9/F10 deferred to P8). App.jsx hosts F2/F3/F4 and was committed once. Harnesses green: smoke 40/0, guards 11/0, acceptance 26/0, invite 11/0; frontend gate 25/0 |
| P2-T1 Hosting intake | DONE | | owner silent; default applied: local Docker Compose only, no public URL, no domain/VPS yet |
| P2-T2 Containerize | DONE | | Dockerfile.api/.ui, Caddyfile, docker-compose.yml (api/worker/scheduler/postgres/caddy/migrate); GET /api/v1/foundation/health added; stack verified: health ok (db_backend=postgres), UI 200 at http://127.0.0.1/ui/. Existing compose preserved as docker-compose.local.yml. Pre-existing malformed root `.env` (line 98) blocks plain `up`; used `--env-file .env.example` |
| P2-T3 BrowserRouter migration | PENDING | | |

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
- OQ-4 (P0-T3): owner ruling on test-mode self-approval vs Constitution §3
  purchase-approval rule. Safe default applied (see Assumptions #2).
- OQ-5 (P2-T1): domain name, VPS provider, and additional user emails (Tyler).
  Default applied: local Compose only, no public URL (Assumptions #3).
- OQ-6 (P2-T3, next card): BrowserRouter base path. Plan says base `/`; the SPA
  is built and served under `/ui/` (Vite base `/ui/`, FastAPI `ui_serving`, Caddy
  `handle_path /ui/*`). Options: (a) BrowserRouter `basename="/ui"` keeping
  serving as-is; (b) move Vite base + serving to root `/`. Also need to know what
  serves the harness port 8104 (external process, not in repo) and whether it
  does SPA fallback for path routing. Next card resumes here.

## Owner Answers

(none yet)

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

Reconciliation (spec vs disk, per §5):
- Root `npm run build` fails in this environment: the root script uses
  `npm --cwd northstar-os-ui run build`, and the installed npm treats `--cwd` as
  a package spec (`npm error 404 northstar-os-ui`). Running `npm run build`
  with workdir `northstar-os-ui` succeeds. Candidate frontend defect (F-class)
  for P1-T3.
- Costco plain suite is 217, not 191. The 191 figure is documented in
  `reports/northstar_ui_owner_acceptance_packet_20260927.md` and
  `reports/post_acceptance_p2_hardening_20260927.md` for the same command on
  2026-09-27. The working tree now carries untracked Bright Data test files
  (`test_brightdata_campaign.py`, `test_brightdata_manifest.py`,
  `test_brightdata_schema_test.py`) plus modified frozen test files added by
  prior sessions (already captured at P0-T1). Zero failures either way; the
  delta is additional tests, not regressions.

## Credentials Status (names only, never values)

| Name | Provider | Status |
|---|---|---|
| (none recorded) | | |