# OWNER DECISION SHEET — A1–A9

**Prepared:** 2026-10-09 · **Baseline:** `2482048` (audit) · **HEAD:** `d67e83a`
**How to use:** one line per decision. Write the answer in the last column. Nothing below is implemented until you sign it — except where you have already given an explicit direction, which is flagged.

---

## The four that unblock everything (decide first)

### A1 — Live-call policy for the scanner
**Question:** may *any* plain `GET` ever trigger a paid provider search?
**Options:**
- **(A1.1 — recommended)** No. Set `SCANNER_LIVE_ALLOWED` to a non-opt-in value in `Northstar_backend/.env` **and** add a startup assertion (mirroring the existing `assert_prod_posture()` for the rate limiter) that refuses to boot if a GET-reachable path can search live. Live search stays available only via the explicit `POST /api/kirkland/refresh` command with an operator-supplied flag.
- (A1.2) Yes, but only for named operators, gated by an allowlist.
- (A1.3) Status quo — GET may search live.
**Recommended answer:** A1.1.
**Note:** you have already directed the env disarm ("Disarm live gating now"), so the first half of A1.1 is operator-authorised. The second half (the startup guard) is a code change and needs this signature.
**Blocked by your answer:** P0-01, and every tier-A live-call test case (A-06, A-07, C-03).

### A2 — Canonical hosted API entrypoint
**Question:** does the deployed stack run `main:app` or `foundation.app:app`?
**Options:**
- **(A2.1 — recommended)** `main:app`. It already mounts the foundation router, the noncreative router, and every legacy route, so local and hosted converge with no route moves.
- (A2.2) `foundation.app:app`, and move the ~200 `main.py` routes into the foundation app first.
**Recommended answer:** A2.1.
**Why it is first-class:** until this is decided, every "works locally, 404s in hosted" bug is unresolvable — including P0-02 and P0-03, which interact.
**Blocked by your answer:** P0-02, P0-03, B-01.

### A3 — Authentication policy for `/api/autothink/*`
**Question:** who may run a model or read the AutothinK history?
**Options:**
- **(A3.1 — recommended)** Requires a session; history scoped by organization; any credit-spending provider additionally requires an armed flag.
- (A3.2) Requires a session; history global but authenticated.
- (A3.3) Leave public.
**Recommended answer:** A3.1.
**Blocked by your answer:** P0-04, P1-17, A-21, A-23, B-10.

### A9 — Repository freeze
**Question:** do we freeze the repo before the full-service test?
**Recommended answer:** yes — pause the parallel session or agree a landing window, tag the audited commit, and re-audit anything that lands after it.
**Why it is urgent:** five commits landed during the audit window alone. A test run against a moving tree is not reproducible, and a concurrent session may hold the answer to "who is running the Golden Goose scans."
**Blocked by your answer:** every tier-B and tier-C case.

---

## The five that should follow

### A4 — One bounded hosted OpenCode Go call
**Only after P0-02 is fixed.** One call, `step-5-preview-free` (free tier), `max_tokens=8`, no retry, no fallback. This is a live call, so it needs your named approval at the time, not now.

### A5 — Cloud (OpenRouter) arming and cost cap
Arm `CLOUD_MODEL_LIVE` or keep it closed? If armed, name the per-run USD cap and require a `max_price` in the request body. Currently the armed path has **no ceiling at all**.

### A6 — Scope for The Watch / RankLedger / Rival Board
Retire (delete the unrouted legacy pages and the spec references) or revive (needs SP-API access). "Parked forever" is the worst option — it leaves three promised services invisible.

### A7 — Isolated test accounts
Six roles: unauthenticated, invited-not-activated, subscriber, operator, platform admin, unauthorized/other-workspace. Needed for 14 of 28 tier-B cases. `verify-live-signin.cjs` is currently **BLOCKED** for want of `NS_TEST_EMAIL`/`NS_TEST_PASSWORD`.

### A8 — Media provider or "stay concept"
**Easy answer if you want one:** if no image/video provider is approved, mark Creative Studio, SocialPulse, AdPilot and Design Studio as `concept` in `readiness.js` so the nav badge matches reality. That is a two-line change and closes the honesty gap immediately.
Note: the studio workstream has already moved these rooms forward, so re-assess before setting the badge.

---

## Dependency-ordered remediation sequence

| Order | Items | Why here | Gate |
|---|---|---|---|
| 1 | **P0-05** (freeze/tag) | Nothing is reproducible without it | Gate 1 |
| 2 | **P0-01** (A1) + **P0-04** (A3) | Safety. Both are env/config + one auth dependency | Gate 1 |
| 3 | **P0-02** + **P0-03** (A2) | Restore the API contract; they interact | Gate 1 |
| 4 | **P1-01, P1-02, P1-03, P1-08, P2-18** | Close the silent-failure class (unknown must never become zero) | Gate 1 |
| 5 | **P1-10, P1-11, P1-12** | Make the suite deterministic | Gate 1 |
| 6 | **P1-06** (SourceScout wiring), **P1-21** (Admin honesty) | Highest-stakes dishonesty | Gate 1 |
| 7 | **P1-14** (Golden Goose evaluate UI), **P2-01** (Product Designer audit), **Design Studio audit** | Complete the feature surface | Gate 1 |
| 8 | **P1-15…P1-19** (AutothinK grounding, metering, tenancy, lifecycle, copy) | Deepen the intelligence layer | Gate 2 |
| 9 | **P1-07, P1-09, P1-13, P2-16, P2-17, P2-19, P2-20, P2-22, P3-*** | Ops, docs, hygiene | Gate 2 |
| 10 | **P2-04, P2-05, P2-06, P2-08, P2-09** | Creative honesty and accessibility | Gate 2 |

**Do not action P2-02 or P2-03** — the studio commits already fixed them (see the addendum).

---

## Sign-off — defaults applied by the overnight autonomous run

The owner was asleep and pre-authorised defaults for A1–A9. Every row below
records the default that was APPLIED, the evidence, and what the owner must
still confirm. Nothing here is treated as approved design work.

| Decision | Answer applied | Initials | Date | Evidence |
|---|---|---|---|---|
| A1 | **A1.1 applied by default.** `SCANNER_LIVE_ALLOWED=0` in `Northstar_backend/.env`, plus `live_gate.assert_live_posture()` which refuses to boot a live mode lacking a per-run arm flag and a positive per-run cost cap. Live search stays reachable only through the explicit `POST /api/kirkland/refresh` path. | — | 2026-10-09 | `Northstar_backend/live_gate.py`, `main.py` lifespan, `test_live_posture_guard.py` (12 tests incl. a socket-level proof that 8 UI GET routes open zero non-loopback provider connections) |
| A2 | **A2.1 applied by default.** One entrypoint: `uvicorn main:app`. The SPA is built inside the image and served at `/ui/`; `/autothink/*` is served too. Caddy remains for TLS termination only. | — | 2026-10-09 | `Dockerfile.api` (built and run locally; container healthy, 19/19 UI routes resolve), `Caddyfile`, `tools/verify-hosted-container.ps1` |
| A3 | **A3.1 applied by default.** `/api/autothink/*` requires a strict session (`require_session`, Bearer JWT or the HttpOnly cookie — no anonymous fallback). History, usage and cancellation are org-scoped. A credit-spending provider additionally requires the live arm flag. | — | 2026-10-09 | `auth_deps.require_session`, `main.py` (7 routes), `test_autothink_auth_boundary.py` (9 tests: 401 without a session, cross-tenant isolation) |
| A4 | **NOT RUN LIVE.** No live hosted reasoning call was made: no budget was supplied. Recorded as NOT RUN, never as PASSED. | — | 2026-10-09 | `tools/live_test_runner.py --dry-run` (refuses to arm without cap + acknowledgement) |
| A5 | **No cloud arming beyond the cap.** `CLOUD_MODEL_LIVE` remains absent from both env files. The armed cloud path has no ceiling yet — this is an open gap, not a closed one. | — | 2026-10-09 | both `.env` files; cloud lane gated in `llm_adapter.py` |
| A6 | **Labelled, not deleted.** The Watch / RankLedger / Rival Board stay in the inventory as S20–S22, `MISSING / NOT_APPLICABLE` with "requires Amazon SP-API (not integrated)". No route, no page, no promise. | — | 2026-10-09 | `SERVICE_INVENTORY.csv` S20–S22 |
| A7 | **7 isolated local test accounts created**, one per role plus a read-only member for least-privilege checks. Credentials are outside the git tree with owner-only ACLs. | — | 2026-10-09 | `Northstar_backend/create_test_accounts.py`, `test_invite_flow_e2e.py` (7 tests), `verify-live-signin.cjs` fixed |
| A8 | **Media stays concept.** `GET /api/v1/foundation/creative/readiness` (added) reports `armed:false` with no provider connected. Product Designer / Creative Studio / SocialPulse are labelled `concept` in `readiness.js`. Video disabled. No generated-image export without a fidelity warning. | — | 2026-10-09 | `main.py` creative readiness route, `readiness.js`, route sweep screenshots |
| A9 | **One branch.** All work committed to `feature/overnight-remediation-20261009` (9 commits). The concurrent session's 79 untracked files were left untouched and reported as UNATTRIBUTED. | — | 2026-10-09 | `git log`, `evidence/p0-05-unattributed-sessions_20261009.txt` |

## Still needs the owner's answer

1. **The untracked `costco_non_kirkland/tests` files block the test suite from
   collecting** (they import three symbols that do not exist). They are
   UNATTRIBUTED work-in-progress from a concurrent session, so they were not
   deleted. The suite must be run with
   `--ignore=costco_non_kirkland/tests` until that session lands or is stopped.
2. **The stock local model is missing.** `DEFAULT_LOCAL_MODEL` is
   `northstar-qwen3:rev1`, which is not installed; Ollama returns 404 for it.
   Either `ollama pull northstar-qwen3:rev1` or set
   `AUTOTHINK_LOCAL_MODEL=qwen3:14b` (a real completion was verified on
   `qwen3:14b`, 33 s).
3. **No live provider budget was supplied**, so every metered lane is NOT RUN.
   Bright Data spend from the 2026-10-08 audit (19 calls) is still UNKNOWN and
   needs the dashboard.
4. **A persistent `NORTHSTAR_JWT_SECRET` must be set before any hosted boot** —
   the app now refuses to start without one, deliberately.
5. **The API process on :8000 from an earlier session is still running** with
   the old armed env. It was left alone (P0-05 rule) and must be restarted by
   its owner for the disarm to take effect for that process.

---

## ADDENDUM ? decisions applied by default during the overnight Phase 5 loop
(2016-10-10, Design Studio). Each of these was decided WITHOUT the owner and is
reversible. Reverse any of them with one line.

| # | Decision | Chosen | Why | Reverse by |
|---|---|---|---|---|
| D1 | Sections without the compositing surface | Projects and 3D Product Scene keep their OWN canvases and are documented, not duplicated | Both already own a purpose-built canvas; a second one would duplicate an equivalent surface | Embed `CompositingSurface` in those two components |
| D2 | Dev-only engine hook | Gated on `import.meta.env.DEV`, eliminated from production | The directive requires it not to run in production; the harness now SKIPs instead of failing | Remove the `if (!import.meta.env.DEV) return` line |
| D3 | Fidelity thresholds | 6% mean / 45% worst-pixel / 2% label | Calibration shows the average test alone is blind to small in-product edits; the tripwire catches them | `DEFAULT_THRESHOLD`, `DEFAULT_MAX_PIXEL_DELTA`, `DEFAULT_LABEL_THRESHOLD` in `fidelity.js` |
| D4 | Re-check log storage | Tenant-scoped `ds_rechecks`, local mirror only as an offline fallback | The directive requires tenant scoping; a mirror prevents silent loss when the API is down | `studio/engine/rechecks.js` |
| D5 | Public Amazon pages | NOT re-pulled | All 35 sources are current on the pull date, so nothing was past cadence; no budget spent on reads with no delta to find | Re-run `freshnessReport()` after 2026-11-09 |
| D6 | Items 6 and 7 | NOT STARTED | The loop reached the end of the budget first | Assign them as the next work item |
| D7 | Compositing harness | Documented NOT RUN rather than forced green | It times out and the cause was not isolated within budget; reporting it as passing would be a false claim | Run `HARNESS_BASE_URL=http://127.0.0.1:8101/ui/ node test-compositing.cjs` and diagnose the hang |

### Phase 6 continuation (2026-10-10, Design Studio)

| # | Decision | Chosen | Why | Reverse by |
|---|---|---|---|---|
| D8 | Dev sign-in failure path | A dev build VERIFIES the shim result and falls back to the real `/auth/login`; both failures show an explicit alert | The containerized backend ignores the shim (bridge client), and the old branch assumed success — a silent no-op. Verified: demo creds now fail visibly; a real account signs in | Remove the fallback block in `SignIn.jsx` |
| D9 | Engine-hook build flag | Named `VITE_TEST_HOOKS`; gate is `import.meta.env.DEV \|\| VITE_TEST_HOOKS === '1'` | Separates the test artifact from the dev server; production carries neither | Rename the flag in DesignStudio.jsx + docs |
| D10 | Route identity for imported evidence | The NEW endpoints (`/imports`, `/terms`, `/variants`) use a strict org-scoped session (`studio_account`); anonymous → 401. Legacy Design Studio routes keep `get_current_user` bucketing | Legacy callers collapse into one bucket because `get_current_user` has no cookie awareness; changing it moves already-stored data, so it is left and recorded | Swap the dependency back / apply the tenant-preferring `_account_id` and migrate buckets |
| D11 | Local stack during harness runs | `NORTHSTAR_DISABLE_RATE_LIMIT=1` (the documented, production-refused harness opt-out) re-set the local container so the evidence flow can exceed 30 req/min | The compose default is 0 and `assert_prod_posture()` refuses the flag in production; `tools/start-local.ps1` re-ups without it, so the next normal start restores the limiter | Run `tools/start-local.ps1` (or `docker compose up -d api` without the flag) |
| D12 | Capability gaps in Projects / 3D | DOCUMENTED as limits in `reports/design-studio-capability-audit_20261010.md` instead of closed | Porting the compare/fidelity track into Stage and gating 3D exports are product decisions, not overnight fixes | Close either gap per the report's follow-ups |
| D13 | Harness fixture hygiene | `verify-search-terms.cjs` deletes its own prior fixtures (labels starting with `harness`/`Harness `) before running | The tenant store persists between runs, which made the BA available→unavailable transition untestable on re-runs | Remove the cleanup block and use a fresh tenant |

### Phase 7 (2026-10-10/11, Design Studio)

| # | Decision | Chosen | Why | Reverse by |
|---|---|---|---|---|
| D14 | Dev sign-in | Shim path is the EXACT demo pair only and NEVER touches `/auth/login`; it fails closed with an explicit message. Real login happens only when the operator explicitly types non-shim credentials | Reverses the D8 auto-fallback: a demo credential must never reach the credential endpoint, whatever the backend posture | Restore the fallback in `SignIn.jsx` |
| D15 | Rate-limit opt-out | Refused in staging AND production (startup guard + hosted pin "0" + compose-guard assertion). The local harness phase ran with the documented opt-out | The hosted overlay runs ENVIRONMENT=staging, so a staging deploy could previously carry it | Loosen `prod_posture_ok()` / remove the hosted pin |
| D16 | D10 migration mapping | Shared buckets move only with exactly ONE organization; unknown buckets ALWAYS quarantine; nothing is deleted; apply is idempotent. Live: the real store held no shared-bucket records at run time (image rebuild reset it) — the quarantine path was demonstrated with labeled seeds and the move path with fixtures + a test-only `--orgs` override | Attribute nothing that cannot be attributed; a migration that guesses steals data | Change the mapping rule in `migrate_ds_identity.py` |
| D17 | Projects reference lock | The version-bound human sign-off is the export gate; the objective pixel diff is ON DEMAND (verdict + limits shown) | A composed canvas legitimately differs from the raw photograph; an automatic diff would block every real composition | Make the diff automatic in `lockedGate` |
| D18 | 3D render gate | Listing-purpose renders BLOCK on the actual-photo rule (rule id + source shown); internal renders pass with disclosure + (when locked) fidelity; one scene sign-off covers all views | A render is not a photograph; the rule is Brand Registry's, cited with its source | Allow listing purpose / drop the rule |
| D19 | Listing context sources | Browser-local stores only (ListingForge, brand profile, studio A+ projects); freshness window 90 days is an engineering choice, stated in the UI | No marketplace read exists locally; inventing one would be a live call | Point the context at a real marketplace read when one exists |
| D20 | Imported keywords in briefs | Imported keyword lists feed the brief's matching and the brief names its keyword provenance; the terms table's default view excludes brand-voice/keyword rows | Keeps the metric table honest and the brief's evidence traceable | Drop the merge / show all kinds |

### Phase 8 (2026-10-11, Design Studio)

| # | Decision | Chosen | Why | Reverse by |
|---|---|---|---|---|
| D21 | Postgres for the Design Studio store | `DATABASE_URL` is set in docker-compose.yml (local + hosted), so ds_* tables live in the `northstar_data` PG schema and survive container recreation. SQLite remains the fallback when the URL is absent | The Phase 7 report flagged the container-local SQLite store as a durability gap; item 2 required running the store against local Postgres | Remove the DATABASE_URL line from the compose anchor |
| D22 | Synthetic test tenants | KEPT but clearly labelled (slug `ns-test-tenant-` + name `Northstar Test Tenant`); `cleanup_test_tenants.py` removes ONLY tenants with both markers (dry run by default) | The live cross-tenant negatives use them; removal is one command away | `docker exec <api> python cleanup_test_tenants.py --apply` |
| D23 | Listing-context migration scope | The one-shot migration copies FROM the ListingForge store and clears only the local marker/mirror after the server confirms; the ListingForge working store is never deleted | Clearing another room's working data would be destructive; the directive's "clear after confirmation" applies to the migrated copy | Make the migration delete the ListingForge records |
| D24 | Fidelity trial inputs | Live trial NOT RUN (no reference photos; no local media runtime). Fixtures + drop-in folder provided; runtime generation never exercised | Nothing to run against; claiming a pass rate from fixtures alone would be false | Drop ≥5 real photos into research/design-studio/reference-photos and run with a local runtime |
| D25 | Registry claim statuses | Title-length REPORTED (FLAG), AI-people window REPORTED, formats VERIFIED via the Product image guide, 10 MB REPORTED + NOT enforced, A+ eligibility INFO with "confirm in A+ Content Manager" | Only recorded Amazon-owned sources may be VERIFIED; an unconfirmed figure must never block | Edit the claim records in `registryClaims.js` |
| D26 | PG read transactions | Every statement with a result set commits immediately (no idle-in-transaction); the live-columns migration checks information_schema before ALTER | A live hang proved an idle SELECT can hold locks that block schema DDL | Remove the read-commit in `data_layer._execute_pg` |

### Phase 9 (2026-10-11, Design Studio)

| # | Decision | Chosen | Why | Reverse by |
|---|---|---|---|---|
| D27 | Title-rule source | New `title-guide` source marked VERIFIED from the owner's capture (login-gated; a public read returned the gate). All rules applied as FLAGS only; the promotional example list is stated as illustrative, not Amazon's full list | The owner supplied the observation and directed the upgrade; the studio must never edit a title | Set the source/claims back to REPORTED in `registryClaims.js`/`specRegistry.js` |
| D28 | Master-brain panels | One read-only, tenant-scoped endpoint renders in ListingForge, AdPilot and SocialPulse; sections carry source/observed/limits; missing = UNKNOWN | The other rooms need the Studio's evidence without write paths or provider calls | Remove the panel component / endpoint |
| D29 | Item Highlights flat-file column | Recorded UNKNOWN until Amazon publishes it; the new ListingForge CSV export states it and leaves the column empty | An unpublished column name must never be invented | Publish the column name when Amazon does |
| D30 | Mask-protected fidelity semantics | The masked reference is rendered with the same engine geometry (transparent outside the product), so edits outside the mask pass and edits inside block. Live trial still NOT RUN (no photos/runtime) | The transparency-skip IS the mask contract; fixtures prove both directions | Change the reference construction in `fidelity-trial.cjs` |
| D31 | Harness fixture hygiene on PG | `_check-recheck-migration.cjs` now deletes its own previously-migrated entries before seeding (the PG store persists between runs) | The harness assumed a clean store; persistence made the count assertion fail | Remove the cleanup block and use a fresh tenant |

### Phase 10 (2026-10-11, file-only Amazon integration)

| # | Decision | Chosen | Why | Reverse by |
|---|---|---|---|---|
| D32 | Amazon linkage | OFF by architecture: `NS_AMAZON_LINKAGE_ENABLED` default off; staging/production REFUSE to boot with it on; the SP-API/Ads-API importers, the unified adapter and the blacklist re-check refuse even with credentials while off | The owner's architecture decision: no sign-in, no account linking, no APIs; files in, files out | Set the flag and (for a hosted posture) remove the boot refusal |
| D33 | Legacy .xls (BIFF) | Honestly REFUSED with the stated fix (re-save as .xlsx/.csv); not parsed | A binary BIFF parser would be guesswork; the honest path is stated | Implement a BIFF reader |
| D34 | Proposal list contract | The API returns the FLAT proposal shape (payload fields at the top level + decision fields) | The nested shape crashed the surface; the flat shape is now the contract | Return raw rows and adapt the UI |
| D35 | Committed fixtures | `tools/fixtures/amazon_files/` holds the six upload fixtures, built with openpyxl by `_make_amazon_fixtures.py` | Real interop proof (a different writer than the parser) and stable harness inputs | Regenerate/remove the fixture set |
