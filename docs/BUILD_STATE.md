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
| P2-T1 Hosting intake | DONE | | original: owner silent; default applied: local Docker Compose only, no public URL, no domain/VPS. SUPERSEDED for deployment preparation (not erased) by the 2026-09-29 owner decision: attempt OCI Always Free, $0 infra, neutral free hostname; see Owner Answers + Deployment track. |
| P2-T2 Containerize | DONE | | Dockerfile.api/.ui, Caddyfile, docker-compose.yml (api/worker/scheduler/postgres/caddy/migrate); GET /api/v1/foundation/health added; stack verified: health ok (db_backend=postgres), UI 200 at http://127.0.0.1/ui/. Existing compose preserved as docker-compose.local.yml. Pre-existing malformed root `.env` (line 98) blocks plain `up`; used `--env-file .env.example` |
| P2-T3 BrowserRouter migration | DONE | | App.jsx HashRouter->BrowserRouter basename="/ui"; BetaInviteAccept links/router nav; four harnesses rewritten to path routing; direct load /ui/golden-goose 200 + renders; smoke 42/0, guards 11/0, acceptance 27/0, invite 11/0; frontend gate 25/0 |
| P2-T4 Postgres in hosted mode | DONE | | DB_URL canonical (+legacy FOUNDATION_DB_URL); migrate entrypoint records `schema_migrations` + checksum drift; startup check fails closed in hosted env (dev no-op). Compose stack: migrations 7/7, ledger=7, api health ok. SQLite foundation suite 642 passed/58 skipped/0 failed. Postgres suite 45 passed/0 failed against a self-spun disposable PG (127.0.0.1:55443, `northstar-pg-testrun`), torn down after. Test guards decoupled from port 55432 via `NORTHSTAR_PG_TEST_PORT/USER/DB` env. |
| P2-T5a Owner credential storage + bootstrap | DONE | | `foundation/credentials.py` (bcrypt, dedicated `owner_credentials` table), forward migration `008_owner_credentials.sql`, interactive `foundation_seed_owner.py` (getpass, idempotent, refuses ambiguous/remote/prod targets; no password in output), `state.py` db_path authoritative over env. Tests: 8 passed/1 skipped SQLite, 9 passed vs disposable PG; no password/hash in output. |
| P2-T5b Backend auth and session | DONE | | `foundation/auth_session.py` (HS256 mint matching validator, HttpOnly session cookie Path=/api/v1/foundation, double-submit CSRF cookie, per-process login throttle); deps reads session cookie + CSRF on unsafe methods; router `POST /auth/login`, `POST /auth/logout`; no token in body; hosted fail-closed (dev shim ignored, Secure cookie). Tests 8 passed; auth/invite/authorization subset 157 passed/9 skipped/0 failed. |
| P2-T5c UI sign-in and route guards | DONE | | `foundation/dev.js` explicit local-dev switch; api.js cookie transport (`credentials:include`, CSRF header, login/logout, no hosted token); session.jsx always resolves identity from /me (empty user_id = signed out) + logout revokes cookie; SignIn.jsx real login (local demo only when LOCAL_DEV); harnesses set `window.__NORTHSTAR_LOCAL_DEV__=true`; invite stub returns 401 when signed out. Harnesses: smoke 42/0, guards 11/0, acceptance 27/0, invite 11/0; frontend gate 25/0; auth subset 119 passed/8 skipped; SQLite suite 658 passed/59 skipped/0 failed; disposable PG 62 passed; PG torn down. |
| P2-T5 acceptance (hosted HTTPS sign-in) | PARTIAL | | implementation complete; hosted-HTTPS owner sign-in UNVERIFIED (needs a real URL + operator-created owner credential). Not claimed. |
| P2-T6 prep (LOCAL VERIFICATION) | PARTIAL | | local only; not deployed. Shared DB login throttle (migration 009) + hosted fail-closed without shared store. Live browser walkthrough `northstar-os-ui/verify-live-signin.cjs` against local Compose: 14 passed / 0 failed — sign-in -> /ui/home; no token in localStorage; NO local-dev flag in served build; protected load + refresh stay authenticated; /me=internal_platform_admin; logout no-CSRF 403 / with-CSRF 200; /me after logout 401; signed-out /ui/monitoring -> /ui/sign-in; 8 expected non-2xx resource notices, 0 unexpected console errors, 0 uncaught JS exceptions, 0 failed requests. HTTP only — NOT a hosted-TLS test. Test owner seeded + cleaned up. |
| P3-T1 Owner Test Mode flag + scope + banner | DONE | | `foundation/owner_test_mode.py` (flag off = zero change; owner-role only; never in `production_tenant`; self-approval default off); `/environment` exposes `owner_test_mode`/banner/`owner_self_approval`; UI persistent banner (`data-testid=owner-test-mode-banner`) gated on session flag. Tests 5/0; harnesses smoke 42/0, guards 11/0, acceptance 27/0, invite 11/0. |
| P3-T2 Owner Test Mode bypasses | DONE | | Entitlements: owner gets all gated features on + unbounded limits (via `entitlements_for_org(..., ctx)`/`enforce_*`), non-owner/other-tenant/base view unchanged, flag-off restores. Quotas: usage still counted, blocks not enforced for the owner; flag off restores enforcement. RBAC: owner holds every permission (net-zero: matrix already grants admin all; reason `owner_test_mode`). Env safety: allowlist `{development,test}` via raw ENVIRONMENT (missing/production/production_tenant/staging/unknown all fail closed). Audit: per actual bypass only (`owner_test_mode.entitlement_bypass`/`quota_bypass` with owner_test_mode=true, actor, org, action, reason, occurred_at); unrelated page loads do NOT flood. Concept-badged rooms: UI-nav only, no server feature gate; owner entitlements all-on, non-owner normal. Tests: 20/0 (own) + subset 229 passed / 23 skipped / 0 failed. Self-approval stays disabled. |
| P3-T3 Non-bypassed rules | DONE | | `tests/test_owner_test_mode_non_bypass.py` (9/0) with Owner Test Mode ACTIVE: missing gates stay UNKNOWN (never PASS); score alone never PURCHASE_READY; gates+econ still require separate approval; unregistered job types fail closed (`UnknownJobType`); disabled providers fail closed (`provider_disabled`/`ProviderDisabledError`); provider enabled-state not altered by test mode; signed-out request 401; tenant isolation 403 for non-owner; frozen-file boundary asserted as a STATIC repo/process rule (not runtime-tested). NOTE: provider ARMING + hard daily/monthly spend caps are P7-T1 (not implemented) — not claimed as tested. |
| P3-T4 Demo Dataset toggle | DONE | | `foundation/demo_dataset.py` + migration `010_demo_dataset.sql`: owner-only `/demo/status|enable|disable`; SAMPLE rows in a separate `demo_observations` table (basis=`SAMPLE`, is_sample=1), hidden by default (no settings row), excluded from real `observations`/aggregates; toggling on/off never mutates real data; SAMPLE can never reach PURCHASE_READY (`golden_goose_decision.decide(sample=True)`). Tests 7/0 (+ golden_goose/demo subset 52/0). |
| P4-T1 Pack-count diagnostic | PARTIAL | | CORRECTED: SellerSprite export IS present (companion `products.db` `ss_product_observations`: 109,421 rows; `pack_count_claimed` non-null 26,436) — earlier "absent" was a wrong northstar.db-only check. Read-only counts: crosswalk 7343 all `pack_match_state=UNKNOWN`; sourcing_opportunities 9454 all supplier+marketplace pack NULL; catalog 5086 all pack_count NULL. CANDIDATE cap split: supplier unknown 9454/9454, marketplace unknown 9454/9454, true mismatch 0; no padded matches (prior CANDIDATE 7379 / NONE 2075). Reader wiring added (companion bb48ab8, test 5/0). Full end-to-end rerun NOT executed. Report `reports/p4_t1_pack_diagnostic_20260929.md`. |
| P4-T2 Identity ingest contract | DONE | | `foundation/ingest_identity.py` + migration `011_ingest_identity.sql`: additive `ingest_runs`/`identity_pairs`/`resale_score_inputs`; idempotent by run_id + row pk; validates ASIN format/units/timestamps; keeps supplier pack | marketplace pack | unit_count | net_quantity | package dims DISTINCT; raw + normalized + source + observed_at; freshness OBSERVED/CACHED/UNKNOWN; conflicts counted (first kept); `pack_match_state` never upgraded UNKNOWN→MATCH. Registered job `pipeline.ingest_identity` (fails closed). Tests 10/0; job/handler/durable/ingest/migration subset 233 passed/18 skipped/0 failed. SellerSprite treated as one-time historical export only (no renewal/live use); contract does not depend on it. Companion reader wiring bb48ab8. |
| P4-T3 Data rights register + enforcement | DONE | | `foundation/data_rights.py` (authoritative register + `SOURCES`/`rights()`/`customer_safe_rows()`/`export_safe_rows()`/`assert_*`) + `docs/DATA_RIGHTS.md`. Sources actually present labelled INTERNAL_ONLY/CUSTOMER_OK; planned providers NOT_INTEGRATED (rights UNKNOWN). External use requires explicit ALLOWED; UNKNOWN/PROHIBITED blocked; Owner Test Mode does NOT bypass; internal≠redistribution. Tests 9/0. No customer surface emits historical third-party rows yet (P5+); filter is the enforcement boundary. NOT deleted historical data. |
| P4-T3b Wire rights filter into customer/export surfaces | DONE (GG/api boundary) | | Provenance extractor `explicit_source_key()` (registered keys only, never inferred; reads `source`/`source_key`/`provenance_source` incl. serialized `payload_json`). `golden_goose_store.project_item()` exposes derived scalar columns only, dropping raw embedded `payload_json`. Golden-goose queue/GET routes now return projected views (raw third-party source fields never leak to PERM_VIEW callers). Added focused tests: registered keys extracted; unproven labels (`import`/`wordsample`) never become provenance; raw payload/source_url/deep fields not leaked; derived GG flows preserved. data_rights+routes 21/0; GG suite 30/0. REMAINING: wire `customer_safe_rows`/`export_safe_rows` into export/cross-tenant/external-AI surfaces as they land (none exist yet for third-party data); affected beta surfaces remain blocked from serving historical third-party data. Assumptions logged in docs/ASSUMPTIONS_LOG.md; OA-7 retained as owner/legal blocker. |
| P4-T4 Freshness policy | DONE | | `foundation/freshness.py`: per-field max age (defaults + `NORTHSTAR_MAX_AGE_<FIELD>_DAYS` overrides); within max -> OBSERVED (gate-usable); older -> CACHED with age (display only, gate sees UNKNOWN); missing/unparseable/future -> UNKNOWN. Tests 7/0. |
| P5-T1 Resale Score spec | DONE | | `foundation/resale_score.py` versioned `resale-score-1.0.0`, pure/config-driven; 8 components 0..1 (missing = unavailable `None`, never 0); weighted mean over available only; uncertainty separate labeled penalty; ROI informational only; `purchase_ready` always False. Display "Resale Score"/code `resale_score` (provisional, OA-8). Tests 8/0 (determinism, missing-component, all-missing→None, net floor, ROI informational, penalty, config weights, never-purchase). |
| P5-T2 Golden Goose decision endpoint | DONE | | Routes in `foundation/api/router.py`: `POST /golden-goose/evaluate` (returns `decide()` + informational `resale_score`), `GET /golden-goose/queue` (empty, basis UNKNOWN, no fabrication), `GET /golden-goose/{id}` (404 not_found — no store yet), `POST /golden-goose/{id}/decision` (requires PERM_APPROVE). Score alone can never produce PURCHASE_READY; SAMPLE never PURCHASE_READY. Tests 7/0. |
| P5-T3 Golden Goose Top-5 | PARTIAL | | `foundation/golden_goose_top5.py` (pure deterministic select_top5: eligible only at QUALIFIED_FOR_REVIEW+, policy_exclusion_flag=0, economics_complete, net>=floor; sorted score desc then item_id; NEVER padded; blocked list per item; inputs_hash) + registered job `golden_goose.monthly_top5`. Persistence added: `foundation/golden_goose_store.py` + migration `012_golden_goose_persistence.sql` (org-scoped items/decisions; decisions persist scorer_version + inputs_hash = the evidenced snapshot-with-version mechanism). Routes: queue lists stored items (basis OBSERVED/UNKNOWN), GET returns item+latest decision, decision persists (round-trip). **Item 3 (evidence-based):** persisted scheduler (`jobs_scheduler.py`) fully implemented — enqueue-only, atomic occurrence claim, idempotent, concurrency/misfire/org-suspended/owner-revoked guards, org isolation, GET-never-ticks, NEVER executes jobs or calls providers; verified jobs+scheduler+worker 41/0. New `test_monthly_top5_operator_schedule_path` proves an operator-created `golden_goose.monthly_top5` schedule enqueues exactly one occurrence and the handler runs deterministically/provider-free (top5 suite now 6/0). **NO default monthly cron cadence invented/seeded** (provider-backed schedules default disabled; operator opts in via API). **NO snapshot retention/deletion/snapshot-payload schema invented.** See ASSUMPTIONS_LOG A-07..A-09. Tests: top5 6/0, routes 9/0, jobs+scheduler 41/0. REMAINING/UNKNOWN: turnkey out-of-the-box monthly schedule (only operator-created exists), snapshot retention/deletion semantics (unspecified), candidate source auto-population depends on P4-T1 coverage. |
| P5-T4 Wire rooms | PARTIAL | | Client methods `foundation/api.js`: goldenGooseQueue/Item/Decision/Evaluate. `GoldenGoose.jsx`: `PersistedQueue` panel (basis OBSERVED, or UNKNOWN when empty); item **Review** view wired to `GET /golden-goose/{id}` for non-demo ids with explicit loading / not-found / denied / error states and UNKNOWN when no decision; **Decisions** view shows persisted latest decision per item (UNKNOWN / DENIED, never fabricated); static SAMPLE (GG-001/GG-002) preserved as an explicit demo/deep-link fallback. Focused harness `verify-golden-goose.cjs` 16/0 (org-scoped review, not-found, denied, decision round-trip after reload, cross-tenant denied, demo fallback). No regression: smoke 42/0, guards 11/0, acceptance 27/0, invite 11/0; backend GG subset 29/0. REMAINING: move inline SAMPLE behind a Demo toggle; apply P4-T3b rights filter where third-party data surfaces; extend acceptance with round-trip. NON-CLAIMS: no monthly scheduling, no snapshots, no P4-T1 completion, no live provider evidence. |
| ITEM-4 Local admin / tenant / backup-restore (completion sprint) | DONE (LOCAL) | | Local-only. Admin `/beta-ops/*` + `/admin` UI verified as sample-mode: every destructive control disabled, internal DataNotices present, nav renders, role isolation (`platform_admin` only; operator→`/home`, anonymous→`/sign-in`). Harness `northstar-os-ui/verify-admin.cjs` **34/0**. Backend admin/tenant/audit/migration/e2e suites **92/0**. Backup/restore local drill added: `test_backup_restore_drill.py` **2/0** (SQLite online-backup round-trip parity across tenants + `PRAGMA integrity_check` + disposable-target `drill`/`restore` name guard mirroring `deploy/restore.sh`). Postgres `backup.sh`/`restore.sh` remain DEPLOY-F5 (NOT executed). SOP/checklist: `docs/ADMIN_SOP_AND_INTEGRITY.md`; assumptions A-10..A-13. NO real invitations, tester contacts, external accounts, email/SMS, or cloud/production changes. |
| ITEM-5 Memory-limits review (completion sprint) | DONE (LOCAL, evidence-only) | | Reviewed all compose files (2026-09-30): `docker-compose.yml` + `docker-compose.hosted.yml` define NO `mem_limit` and no `deploy.resources` memory section; the only `deploy.resources` block is `docker-compose.local.yml` (GPU device reservation `driver:nvidia capabilities:[gpu]` for Ollama — not a memory cap). Matches OA-2 prep estimate (4 hosted containers ~0.46–0.78 GB RSS of 12 GB Always-Free A1; ~11 GB headroom). No compose file changed; explicit `mem_limit`/reservations remain an OPEN DEPLOY-F3 owner decision. Assumption A-14. |
| ITEM-6 Local runbook + one-command verify (completion sprint) | DONE (LOCAL) | | `docs/LOCAL_RUNBOOK.md` + `docs/SERVICE_READINESS_MATRIX.md` + `docs/SERVICE_GAPS.md` authored in Parallel Session A (commit `c5aa054`, merged into this branch) — cited, not re-authored. This sprint adds `docs/ADMIN_SOP_AND_INTEGRITY.md` and the final completion report tied to the local end-to-end flow: startup path, env vars by name only, DB migrations/seed/persistence, GG+PF local flows, admin/internal dashboards, scheduler local-or-PARTIAL/UNKNOWN (blocker: no monthly cron cadence invented), backup/restore drill, full test matrix. Verifications: foundation suite 757/59s, admin/tenant/audit/migration/e2e 92/0, drill 2/0, GG 16/0, acceptance 32/0, admin UI 34/0; `npm run build` 0 errors. Parallel-runbook working-copy edits left uncommitted (pre-existing, not mine). Assumption A-15. |

## Deployment track — Free private beta (OCI Always Free, $0 infra)

Binding update 2026-09-29. Room-readiness labels are separate from card status.

| Card | Status | Notes |
|---|---|---|
| DEPLOY-F1 Local architecture preflight | DONE | docs/FREE_BETA_DEPLOYMENT.md; docker-compose.hosted.yml (staging posture, remote-dev off, Owner Test Mode off, Caddy 80/443 + cert volumes); deploy/hosted.env.example (names only); deploy/images.lock (base digests + linux/arm64); deploy/backup.sh + deploy/restore.sh. Resolved-config regression test `tests/test_hosted_compose.py` 3/0: ONLY caddy publishes 80/443; api/postgres/worker/scheduler/migrate publish nothing; no 5432/8000/2375/2376; hosted api env = staging + remote-dev 0 + owner-test-mode 0 + self-approval 0. ARM64: `ns-api-arm64:f1` + `ns-ui-arm64:f1` built under QEMU (EMULATED evidence only) + arm64 import smoke ok; real ARM runtime/migration acceptance PENDING (F5/F6). VERIFICATION LEDGER: executed = compose config validation, port-exposure regression test, ARM emulated build + import smoke, prerequisite subset (165p/7s). NOT executed = backup.sh, restore.sh, any restore drill, certificate issuance, OCI resource eligibility, any hosted runtime. No Oracle account/cloud resources created. |
| DEPLOY-F2 Oracle account handoff | BLOCKED | owner account/verification/MFA/home-region; requires owner action + (optional) ChromeConnect; no cloud resources. |
| DEPLOY-F3 Resource approval + provisioning | BLOCKED | needs approved free-eligible resource packet + capacity; $0 verification required. |
| DEPLOY-F4 Hostname + HTTPS | BLOCKED | DuckDNS candidate; owner login + hostname approval. |
| DEPLOY-F5 Host hardening, deploy, recovery | BLOCKED | depends on F3/F4. |
| DEPLOY-F6 Hosted acceptance | BLOCKED | depends on F5; P2-T5 hosted sign-in + P2-T6 stay PARTIAL until it passes. |
| DEPLOY-F7 Five-tester rollout | BLOCKED | owner-approved tester identities; after F6 evidence. |
| DEPLOY-F8 Email (optional later) | BLOCKED | no approved sender domain → manual invite links required. |

## Browser integration (ChromeControl) — selection-aware

- Northstar `opencode.jsonc` now launches the **selection-aware launcher** `Default Project\scripts\chromecontrol-mcp.js` (absolute path); the hard-coded `--profile-dir-name "Profile 6"` pin is removed. Default Project `opencode.json` already uses the same launcher.
- Selection source: `Default Project\config\chromecontrol.json` (`attach_mode: extension`, `extension_profile_dir_name: null` = **unpinned** default); CLI `node scripts/chromecontrol.js use-profile <dir|name|index>` (rejects unknown/ambiguous).
- Launcher `--print-args` verified: `attach_mode=extension profile=(unpinned)` → args `--extension`; no browser launched. Spawner resolves the cached `@playwright/mcp` `cli.js` directly (no `@latest` upgrade) and only falls back to npx if the cache is absent.
- **STARTUP_SELECTION_WORKING**; **LIVE_SWITCHING_NOT_IMPLEMENTED** — opencode loads MCP config once, so changing the saved selection requires reconnect/restart (no in-conversation switch mechanism observed). Supported procedure: run `use-profile`, then restart opencode (or reconnect the MCP). Not claimed DONE without a real two-profile switch.
- **Offline-tested, idle baseline (2026-09-30):** orchestrator 47/0, chromecontrol 48/0, browser-control 21/0 (116/0); ChromeConnect status `idle`. A first bounded dry-run created the durable Oracle run `oracle-20260930T000555Z` before any picker and the native picker launch returned `picker_launched` (`awaiting_profile_selection`). **The first real task-driven Oracle run (live profile selection -> extension attach -> Oracle open -> sign-in continuation) remains unverified and is DEFERRED.** OA-1 stays PARTIAL/DEFERRED — do not mark verified.

## Owner Action Queue (statuses: OPEN/ANSWERED/VERIFIED/DEFERRED/CANCELLED — not card statuses)

| ID | Card | Action needed | Why / when actionable | Blocks | Safe default | Status | Verification evidence | Owner response (non-secret) |
|---|---|---|---|---|---|---|---|---|
| OA-1 | DEPLOY-F2 | Create Oracle account; select home region | DEPLOY-F1 ready now; product work continues regardless | DEPLOY-F2/F3 | stay local; no cloud resources | PARTIAL / DEFERRED — offline baseline green + idle (116/0); durable Oracle run created before picker + native picker launch observed (`picker_launched` / `awaiting_profile_selection`) in a bounded run; live profile selection, extension attach, Oracle open, and sign-in continuation unverified; owner instructed to defer. No profile data copied | after an owner-requested task-driven run: real bridge + Oracle tab + read-only inspection | profile dir confirmed |
| OA-2 | DEPLOY-F3 | Approve exact free-eligible resource packet | after OA-1 + packet built | DEPLOY-F3/F5 | create nothing | DEFERRED | console free eligibility + $0 estimate | — |
| OA-3 | DEPLOY-F4 | DuckDNS login + approve neutral hostname | after OA-1 | DEPLOY-F4 | manual only | DEFERRED | hostname resolves + cert issues | — |
| OA-4 | DEPLOY-F6 | Run interactive owner bootstrap on VM | after HTTPS stable | P2-T5 hosted sign-in | none (owner-only) | DEFERRED | owner signs in over HTTPS | — |
| OA-5 | DEPLOY-F7 | Provide 1 real tester identity, then 4 more | after F6 + invite/tenant acceptance | DEPLOY-F7 | no invitations | DEFERRED | invite accepted by tester | — |
| OA-6 | P7-T1 | Set provider daily/monthly caps; arm providers | when adapters + controls exist | P7 provider calls | all providers disarmed | DEFERRED | cap set + first metered call within cap | — |
| OA-7 | P4-T3 | Legal/vendor: SellerSprite customer/export/redistribution/AI use; Amazon-derived clearance; Costco/PalletFly customer display | when a customer/export surface would serve third-party data | P5+ customer surfaces (P4-T3b) | keep INTERNAL_ONLY blocked | OPEN | written permission or counsel note | — |
| OA-8 | P5-T1 | Confirm resale score display name | now (default exists) | P5-T4 room labels | display "Resale Score", code `resale_score` | OPEN | owner confirmation | — |

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
- (2026-09-29) **P2-T6 = B: defer hosting, stay local.** Do NOT deploy publicly or purchase infrastructure. Keep P2-T6 and the P2-T5 hosted-HTTPS sign-in acceptance item PARTIAL. Do not re-ask for domain/VPS until the owner says they have them.
- (2026-09-29) **SUPERSEDES the local-only deployment posture for preparation only.** New owner deployment decision: continue local dev; attempt an Oracle Cloud Infrastructure **Always Free** deployment for a private beta; use a stable neutral free hostname; **$0 infrastructure spend**; no permanent domain, no VPS purchase, no paid upgrade, no paid fallback, no trial-credit use; ask before any payment/upgrade/billable resource. Rollout: owner + disposable accounts → one real tester → five testers only after first external acceptance → beyond five only after measured gates + separate owner decision. The 50-subscriber test is NOT authorized. Public product name stays provisional. The earlier local-only decision is retained as history; this update supersedes it for deployment preparation. Paid AI/data is governed separately and unchanged. Amazon/SP-API/Seller-Central/retail-automation exclusions remain in force.

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