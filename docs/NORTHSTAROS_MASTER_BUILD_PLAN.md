# NORTHSTAROS MASTER BUILD PLAN — for OpenCode (DeepSeek v4.1)

**Products:** NorthstarOS (Helium 10 / Jungle Scout competitor) and NorthstarOS AutothinK (agentic automation).
**Browser layer:** ChromeConnect (formerly "ChromeControl"; treat both names as the same layer).
**Target outcome:** a hosted web app at a real URL, every room working end to end, and an Owner Test Mode so the owner can exercise every service with no permission barriers.
**Repo:** `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`, branch `feature/ui-v3-production`. Companion repo: `fba-product-screener` (identity layer, Costco/PalletFly/SellerSprite data). See P0-T2.

---

## PART 1 — OPERATING PROTOCOL (adopt before doing anything)

### 1.1 Prime directives
1. **Read authority first, in this order:** `docs/OPERATING_CONSTITUTION.md`, `AGENTS.md`, `docs/UI_UX_BLUEPRINT_NORTHSTAROS.md`, `docs/NORTHSTAROS_SUITE_COMPLETE_BLUEPRINT.md`, `docs/BUILD_STATE.md` (create in P0 if absent). If this plan conflicts with the Constitution, **the Constitution wins**. Stop and use an ASK OWNER block.
2. **Never fabricate.** No invented data, matches, prices, credentials, test results, or "done" claims. Unknown stays UNKNOWN. If 0 qualify, report 0.
3. **Truth labels are law.** Every data region shows its basis: OBSERVED / CACHED / ASSUMED / UNKNOWN / SAMPLE / INTERNAL. SAMPLE appears only when the labeled Demo Dataset toggle is on.
4. **Fail closed.** Unregistered job types fail. Disabled providers raise `ProviderDisabledError`. Missing gates are UNKNOWN, never PASS.
5. **A score never authorizes a purchase.** Only mandatory gates plus an explicit approval reach `PURCHASE_READY`.
6. **Frozen files — do not run, edit, or commit:** `Northstar_backend/costco_non_kirkland/brightdata_costco_live.py`, `brightdata_costco_enrichment.py`, `enrichment.py`, `cli.py`, and the Bright Data tests. If a task needs them, ASK OWNER.
7. **Never store or type passwords, API keys in code, 2FA codes, or card numbers.** Secrets live only in environment variables or the secret store.
8. **Do not "fix" `test_frontend_gate.py` by recreating `Sidebar.jsx`.** Update the gate to assert the v3 shell's real invariants.

### 1.2 Working style (large-context model; long sessions still drift, so keep the discipline)
- You may read whole authority documents and whole modules at once, and you may batch closely related cards from the same phase in one working session. **Acceptance must still pass card by card**, and never start a card until the previous card's acceptance passed.
- Do not rely on conversation memory across cards. `docs/BUILD_STATE.md` is the source of truth; re-read it at the start of every card and after any long tool output.
- Never rewrite whole files. Use targeted edits. Never paste large files back into chat.
- Before each card: read `docs/BUILD_STATE.md`. After each card: update it (card ID, status, commit hash, open questions, next card). Also update `00_STATE.json` (currently stale at `c1274a3`).
- Commit per card: `P<phase>-T<n>: <imperative summary>`. Run the card's verification commands before committing. Never commit with a failing test that passed before.
- No chatter. No restating the task. No "I will now…". Output only the REPORT FORMAT in 1.5.

### 1.3 ASK OWNER protocol
Whenever a card marks `ASK OWNER`, or you hit missing information, stop and print exactly:

```
=== ASK OWNER ===
CARD: <id>
NEED: <one sentence>
OPTIONS: A) <..>  B) <..>  C) <..>   (omit if free-form)
DEFAULT IF NO ANSWER: <safe default, or NONE = cannot proceed>
BLOCKS: <what cannot proceed without this>
=================
```

Rules: ask at most 3 questions per block; batch questions that gate the same card. If a safe default exists and the owner is silent, proceed with the default and log it in `docs/BUILD_STATE.md` under "Assumptions". If default is NONE, work on any unblocked card meanwhile.

### 1.4 ChromeConnect SIGN-IN GATE (mandatory on every page load)
Any time ChromeConnect opens a site that has an account (Costco, Prime National Distribution, PalletFly, SellerSprite, Amazon Seller Central, Amazon Ads, Bright Data, DataForSEO, Keepa, Jungle Scout, Stripe dashboard, hosting/DNS dashboards, etc.), run this gate **before** reading or clicking anything else:

1. Load the site's adapter `signed_in_check` (a URL pattern + a DOM marker such as an account menu, or the absence of a sign-in form). Check for cookie **presence by name only**; never read or log cookie values.
2. Classify: `SIGNED_IN` · `SIGNED_OUT` · `CHALLENGE` (CAPTCHA / 2FA / device verification) · `UNKNOWN`.
3. If `SIGNED_IN`: verify once by loading a known authenticated page. Continue.
4. Otherwise: set job state `NEEDS_OWNER`, save a screenshot, and print:
   ```
   === SIGN-IN NEEDED ===
   SITE: <name>   PROFILE: t2
   STATE: <SIGNED_OUT | CHALLENGE | UNKNOWN>
   ACTION: Sign in (or complete the challenge) in the open ChromeConnect window, then reply "done".
   I will not enter credentials or solve challenges.
   ======================
   ```
5. Poll every 5 s, up to 10 min (configurable). On owner "done" or a detected `SIGNED_IN`, re-run steps 2–3, then resume. On timeout, mark `BLOCKED_SIGNIN` and move to another job.
6. Re-run the gate after any navigation that crosses to a different origin, and whenever a page shows a session-expired banner or redirects to a login URL mid-task.
7. Use the persistent browser profile named `t2` (user-data-dir on the owner's machine). Never clear it.

### 1.5 REPORT FORMAT (the only output after a card)
```
CARD: <id>  STATUS: DONE | PARTIAL | BLOCKED
CHANGED: <files, max 10 lines>
TESTS: <command> -> <pass/fail counts>
COMMIT: <hash>
ASSUMPTIONS LOGGED: <n>
NEXT: <card id>
BLOCKERS: <none | ASK OWNER printed above>
```

### 1.6 Stop rules
Stop and ASK OWNER if a task would: spend money or arm a live provider without a cap set; mutate a canonical dataset; touch frozen files; require a credential you do not have; require bypassing a CAPTCHA, login, rate limit, or site terms; or change a Constitution rule.

---

## PART 2 — ARCHITECTURE DECISIONS (settled; do not relitigate)

| Decision | Choice | Reason |
|---|---|---|
| Delivery | **Hosted web app** (React/Vite SPA + FastAPI Foundation) | Code, scoring weights, and keys stay server-side; one update path; shareable with Tyler. |
| Browser control | **ChromeConnect Runner**: a local agent on the owner's Windows machine (Playwright/Chromium, persistent `t2` profile) that **pulls** jobs from the hosted backend over authenticated HTTPS | Logged-in sessions stay on the owner's machine; no inbound ports; no passwords on the server. |
| Database (hosted) | **PostgreSQL 15** via existing `foundation/db_postgres.py`; SQLite stays the local dev default | Real multi-user hosting. Migrations already exist. |
| Hosting default | **Docker Compose on one VPS**: `api`, `worker`, `scheduler`, `postgres`, `caddy` (auto-TLS), nightly encrypted backup | Cheapest, fully controllable. (ASK OWNER in P2-T1 to confirm provider and domain.) |
| Routing | Move from `HashRouter` to `BrowserRouter` with SPA fallback | Needed for SEO, shareable links, marketing pages. |
| Marketing site | Static, separate from the app (P12) | Keeps the app private-beta gated. |
| Custom Chromium shell | **Future (P12)**, not required for this plan | ChromeConnect Runner delivers the same automation without maintaining a browser fork. |
| LLM | DeepSeek via provider adapter, **GATED** until the owner arms it; Master Brain routes by cost | Existing provider contract (`foundation/providers.py`). |

**Data-flow summary:**
`Owner browser → hosted SPA → Foundation API (/api/v1/foundation) → durable jobs → { provider adapters | ChromeConnect queue }` and `ChromeConnect Runner → pulls jobs → reads site (signed-in gate) → posts OBSERVED results with evidence → Foundation → rooms`.

---

## PART 3 — TASK CARDS

Card format: **Goal · Steps · Accept · Stop-if**. IDs are stable; do not renumber.

### PHASE 0 — Preflight and reconciliation

**P0-T1 State capture.** Steps: `git status`, `git log -5`, record HEAD (expected `5967f7e`), create branch `build/master-plan`, back up `Northstar_backend/data/northstar.db` to `backups/`. Create `docs/BUILD_STATE.md` with sections: Cards, Assumptions, Open Questions, Owner Answers, Credentials Status (names only, never values). Accept: file exists; backup checksum recorded. Stop-if: dirty tree containing frozen files, do not stage them.

**P0-T2 Two-repo reconciliation.** The Foundation app and the identity/data pipeline (`fba-product-screener`: `data/products.db`, `data/northstar.db`, `northstar_identity_layer.py`, `northstar_identity_config.py`) are separate. `ASK OWNER`: (A) Is the Foundation repo canonical and the pipeline should be imported as a package/module into it; (B) keep two repos and exchange data via a documented ingest contract; (C) other. Default: B until answered. Note the name collision: both use a file called `northstar.db` with different schemas. Rename the pipeline DB reference in config to `pipeline_northstar.db` (config only; no file moves) and document. Accept: decision + contract recorded in `docs/DATA_CONTRACT.md`.

**P0-T3 Constitution diff.** Read the Constitution and list every rule this plan touches (Owner Test Mode, live provider arming, self-approval, ChromeConnect scope). Write `docs/PLAN_CONSTITUTION_CHECK.md`. If any conflict, `ASK OWNER` with options. Accept: file lists each item as COMPATIBLE or NEEDS-AMENDMENT.

### PHASE 1 — Green baseline and defect sweep

**P1-T1 Baseline.** Run: `npm run build`; `verify-smoke.cjs` (40), `verify-guards.cjs` (8), `verify-acceptance.cjs` (26), `verify-invite-flow.cjs` (11); backend invite and auth suites; Costco plain suite (191). Record results. Accept: matches blueprint §11.3 (2 known failures in `test_frontend_gate.py`).

**P1-T2 Fix `test_frontend_gate.py`.** Replace assertions on retired `Sidebar.jsx` and the `Legacy UI disabled` marker with v3 invariants: `SuiteRail` exists, `TopNav` exists, `CommandPalette` exists, route table has 44 routes, legacy client `services/api.js` is not imported by v3 rooms. Accept: 0 failures.

**P1-T3 Frontend defects F1–F11.** One commit each: F1 sign-in link to `#/sign-in` (becomes a real path after P2-T3); F2 `/legal` link to a real route and mount `customer/Legal.jsx`; F3 mount `Suspended`, `Downgraded`, `Reaccept` and branch the shell on `session.suspended`; F4 extend `GuardedRoutes` so internal paths require authentication; F5 define a UI-to-backend role map (backend enum canonical: viewer, analyst, operator, organization_admin, organization_owner, internal_platform_admin); F6 add notifications and quick-create to `TopNav`; F7 delete dead `RouteGuard.jsx` or route all guards through it (pick one); F8 mount or delete the nine unmounted pages, and remove `/sourcing` and `/portfolio` from AGENTS route lists; F9 and F10 are handled in P8; F11 mark or remove `services/api.js`. Accept: the four harnesses still pass; add guard assertions for F4.

### PHASE 2 — Deployable skeleton (get a staging URL early)

**P2-T1 Hosting intake.** `ASK OWNER`: (1) domain name (or use a provider subdomain for now), (2) VPS provider (default: any Ubuntu 24 VPS with 4 GB RAM), (3) who else needs access (Tyler) and their emails. Default: local Docker Compose only, no public URL. Accept: answers logged.

**P2-T2 Containerize.** Create `Dockerfile.api`, `Dockerfile.ui` (build stage to static assets served by Caddy), `docker-compose.yml` (api, worker, scheduler, postgres, caddy), `.env.example` (names only), `Caddyfile`. Health endpoint `GET /api/v1/foundation/health` (also serves Monitoring later). Accept: `docker compose up` yields a working UI at `http://localhost` and passing health.

**P2-T3 BrowserRouter migration.** Replace `HashRouter` with `BrowserRouter`; base path `/`; SPA fallback in `ui_serving.py` and Caddy; update deep links, `CommandPalette`, `RoomTabs`, and all absolute hrefs. Accept: all four harnesses pass with path routing; direct load of `/golden-goose` works.

**P2-T4 Postgres in hosted mode.** Set driver by env (`DB_URL`); run all `migrations_foundation/` against Postgres; add a startup check that fails closed if migrations are behind. Accept: backend test suite passes on Postgres (`*_postgres.py` set) and on SQLite.

**P2-T5 Real auth on hosted.** Use existing JWT auth. Seed one `internal_platform_admin` (the owner) via a one-time CLI that prompts for the password locally (never in env files or git). Enforce HTTPS-only secure cookies, `assert_startup_posture()` remains on. Accept: owner can sign in on the hosted URL; signed-out access to internal rooms redirects.

**P2-T6 Deploy staging.** Push images, bring up stack, TLS via Caddy. Use ChromeConnect QA in P11 method (screenshot at 390, 768, 1440 px) on `/`, `/sign-in`, `/home`. Accept: staging URL loads over HTTPS, owner signs in, `/home` renders. Report the URL.

### PHASE 3 — Owner Test Mode (no barriers)

**P3-T1 Flag and scope.** `NORTHSTAR_OWNER_TEST_MODE=1` activates only for principals with role `internal_platform_admin`, only when `ENVIRONMENT != production_tenant`. Persistent banner: "OWNER TEST MODE — bypasses are audited." Accept: flag off = zero behavior change (test proves it).

**P3-T2 Bypasses (all audited to AUDIT with `owner_test_mode=true`).** Entitlements: all features on. Quotas and rate meters: not enforced but still counted. Billing/org-lifecycle blocks: never block the owner. RBAC: owner holds every permission string including `purchase`. Concept-badged rooms: fully reachable and functional. Self-approval: owner may approve their own approvals (normally a second actor). Accept: a test per bypass; each writes an audit event.

**P3-T3 Things test mode does NOT bypass.** Truth labels; fail-closed provider behavior; frozen files; spend caps (the owner sets them, see P7-T1); the rule that a score alone never yields `PURCHASE_READY`. Accept: tests assert these still hold in test mode.

**P3-T4 Demo Dataset toggle.** Admin switch that loads a labeled SAMPLE dataset so every room is testable before vendor keys exist. Stored in separate rows tagged `is_sample=true`; hidden by default; never mixed into real aggregates or exports. Accept: toggling on/off leaves real data untouched.

### PHASE 4 — Data foundation (identity layer into the product)

**P4-T1 Pack-count diagnostic (from prior run).** For Lane A, report counts of pairs capped at `CANDIDATE` split by: supplier pack unknown / marketplace pack unknown / true mismatch, and list which pack columns were read. Required sources: `sourcing_opportunities` (`units_per_wholesale_case`, `case_to_sellable_unit_conversion_status`, `supplier_sellable_unit_pack_count`, `marketplace_sellable_unit_pack_count`, `pack_normalization_confidence`), `amazon_identifier_crosswalk.pack_match_state`, `amazon_catalog_records.pack_count/unit_count`, `ss_product_observations.pack_count_claimed`. Fix the reader if any source is unread. Accept: report + rerun counts; still no padded matches; idempotent rerun.

**P4-T2 Ingest contract.** Per `docs/DATA_CONTRACT.md`, add Foundation tables (additive migrations): `identity_pairs` (pair_id, lane, source_id, asin, match_state, match_score, evidence_json, run_id), `resale_score_inputs` (as spec'd in the identity blueprint §7), `ingest_runs`. Ingest job type `pipeline.ingest_identity` registered in the handler registry. Accept: job idempotent; row counts equal the pipeline outputs.

**P4-T3 Data rights register.** Create `docs/DATA_RIGHTS.md` listing every data source (SellerSprite exports, PalletFly, Prime National, Costco, Bright Data, DataForSEO, Keepa, SP-API) with: allowed use (internal / redistributable to subscribers), terms link, and status. Mark any source whose terms bar redistribution as `INTERNAL_ONLY` and enforce it: `INTERNAL_ONLY` rows are excluded from customer-tenant views. Amazon SP-API-derived data is `INTERNAL_ONLY` until counsel clears it. Accept: enforcement test.

**P4-T4 Freshness policy.** Every observation carries `observed_at` and a per-field max age (config). Stale data shows CACHED with age; beyond max age becomes UNKNOWN for gate purposes. Accept: unit tests.

### PHASE 5 — Golden Goose vertical slice (the flagship, built first)

**P5-T1 Score spec.** `ASK OWNER`: name of the resale score (default display name "Resale Score", code name `resale_score`). Implement `foundation/resale_score.py`, versioned `resale-score-1.0.0`, pure function, config-driven weights. Default components (each 0–1, missing = unavailable, never 0): net profit per unit vs the $5 floor (`MIN_NET_PER_UNIT=5.00`, config), demand (est. monthly sales), BSR stability, competition (seller count, buy box type), review/rating plausibility, price stability, match confidence, sourcing ease. Uncertainty is a separately labeled penalty. ROI% is informational, not a gate. Accept: tests cover missing-component behavior and determinism.

**P5-T2 Decision endpoint.** Expose `golden_goose_decision.py` (10 gates, 5-step precedence) through new routes: `POST /golden-goose/evaluate`, `GET /golden-goose/queue`, `GET /golden-goose/{id}`, `POST /golden-goose/{id}/decision`. Gates take their values from real inputs (identity → product/variation/pack; economics engine → economics_complete, cost_known, fees_known; policy exclusion → eligibility). Accept: route tests; `overall_score` can never produce `PURCHASE_READY`.

**P5-T3 Golden Goose Top-5.** Job `golden_goose.monthly_top5`: per category or all categories, selects the top 5 by `resale_score` **only among** opportunities at `QUALIFIED_FOR_REVIEW` or better, `policy_exclusion_flag=0`, economics COMPLETE, net/unit >= floor. If fewer than 5 qualify, return fewer and show each blocked candidate's blocking gate. Persist snapshots with scorer version and inputs hash. Scheduled monthly plus on-demand button. Accept: deterministic for identical inputs; never padded.

**P5-T4 Wire the rooms.** `GoldenGoose.jsx` (Queue · Review · Decisions · History) and `ProductFinder.jsx` (Lookup · Product Set · Saved Sets · Coverage) read from the new routes; remove inline sample arrays from the default path (keep them only behind the Demo Dataset toggle). Notices switch to real basis. Coverage matrix must show real gate coverage. Accept: extend `verify-acceptance.cjs` with round-trip assertions (create decision, reload, persists). Deploy to staging.

**P5-T5 Product Finder search.** Add filters: net/unit floor, category, price band, BSR range, match state, gate state, source (Costco/PalletFly/SellerSprite). Server-side pagination and sort on Postgres indexes. Accept: 100k-row SellerSprite catalog queries return < 1 s p95 on staging.

### PHASE 6 — ChromeConnect

**P6-T1 Job protocol.** Tables: `browser_jobs` (id, org_id, site, task_type, params_json, state, needs_owner_reason, created_at, claimed_by, evidence_ref), `browser_evidence` (job_id, url, observed_at, screenshot_sha256, extracted_json, provenance='OBSERVED'). States: `QUEUED · CLAIMED · NEEDS_OWNER · RUNNING · SUCCEEDED · FAILED · BLOCKED_SIGNIN · BLOCKED_POLICY · CANCELLED`. Register handler types `chromeconnect.*` in `jobs_handlers.py` (unregistered types fail closed). Runner auth: per-runner token, revocable in Admin.

**P6-T2 Runner.** Separate package `chromeconnect_runner/` (Python, Playwright, persistent context in the `t2` profile dir). Behavior: outbound HTTPS poll for jobs, claim, execute an adapter task, post evidence, heartbeat. Kill switch: a local `STOP` file and an Admin "Pause all browser jobs" toggle. Per-domain concurrency 1. Polite pacing and honor site terms; **no CAPTCHA solving, no fingerprint spoofing, no credential entry**. Screenshots stored as hashes plus optional blob store. Accept: runner claims a no-op job and posts evidence.

**P6-T3 Site adapter interface.** Each adapter declares: `origin`, `signed_in_check`, `login_url`, `allowed_tasks`, `selectors` (data-driven JSON so fixes need no code change), `extract()` returning fields with per-field provenance, `max_pages_per_run`. Sign-in gate (1.4) runs before every task. Adapters: `costco` (public catalog/prices; member pricing needs sign-in), `prime_national_distribution` (UPC/wholesale list, signed-in), `palletfly` (reference export), `sellersprite` (export download, signed-in), `amazon_public` (product page reads for spot verification only, low volume), `amazon_seller_central` (**owner's own account, read-only report downloads, human present; prefer SP-API/reports over UI scraping**; `ASK OWNER` before enabling), `vendor_dashboards` (key creation pages: navigate and stop for the owner). Accept: each adapter has recorded-page fixture tests plus a live smoke task gated behind the sign-in gate.

**P6-T4 Evidence-first extraction.** Every extracted field stores `source_url`, `observed_at`, `selector_version`, `confidence`. Extraction failure produces UNKNOWN with a reason, never a guess. A layout change (selector miss) marks the adapter `DEGRADED` and shows in Monitoring. Accept: mutation test — break a selector, assert UNKNOWN + DEGRADED.

**P6-T5 Costco discovery job.** `chromeconnect.costco_scan(category, max_items)` populates `costco_discovery_candidates` equivalents in the pipeline (via the ingest contract), tagged `RETAIL_DISCOVERY_ONLY`. Respect the category exclusions (beauty, cosmetics, jewelry, apparel, watch, grocery, luxury, food, perfume, purse). Accept: 25-item live run with sign-in gate exercised, then identity layer runs on results.

**P6-T6 ChromeConnect room.** New Admin sub-room "ChromeConnect": runner status, job queue, **Needs You** queue (NEEDS_OWNER items with screenshot and a "I signed in" button), adapter health, pause-all, evidence viewer. Accept: owner can resolve a sign-in wait from the UI on staging.

**P6-T7 ChromeConnect for QA.** OpenCode itself uses ChromeConnect to verify its own work: after every deploy, load the staging URL, walk the route list, capture console errors, failed network calls, and screenshots at 390/768/1440 px, save to `qa/<date>/`. Run the sign-in gate on the staging site first. Accept: `qa/` report generated per deploy.

### PHASE 7 — Providers and credentials

**P7-T1 Spend caps and arming.** Admin > Provider Adapters gets Arm/Disarm per provider, each with owner-set daily and monthly spend caps and a hard stop at the cap. `ASK OWNER`: cap values for each provider (default: $5/day each, all disarmed). Every live call is metered to `usage` with cost and correlation ID. Accept: exceeding the cap raises a typed error and disarms.

**P7-T2 Credential intake (one prompt block per provider; ask only when the card needs it).**
```
PROVIDER: <name>   NEEDED FOR: <rooms>   COST MODEL: <known pricing note or "verify current pricing">
STEPS FOR OWNER: 1) ChromeConnect opens the dashboard (sign-in gate runs) 2) owner creates the key 3) owner pastes it into Admin > Providers > <name> (stored in the secret store, never echoed)
VERIFY: run the adapter's read-only health call; report OK/FAIL with no key material in output
```
Providers to onboard, in order: (1) **market data vendor pilot** — the 100-row `pilot_asin_list.csv` only, via one of DataForSEO Merchant Amazon, Bright Data Amazon Scraper, or Keepa (`ASK OWNER` which; verify current pricing first, do not trust numbers in old notes); (2) **DeepSeek LLM** (Master Brain and AutothinK); (3) **Amazon SP-API** (owner's own seller account, INTERNAL_ONLY data); (4) **Amazon Ads API** (approval required; sandbox first); (5) **image generation** for Creative Studio; (6) **email** for invites (SMTP/transactional); (7) **Stripe test mode** for billing.

**P7-T3 Provider health.** Read-only health check per adapter surfaced in Monitoring and Provider Adapters. Accept: one green/red/unknown state each, never silent.

### PHASE 8 — Wire the remaining rooms (batches; each room = its own card with the same Done definition)

**Definition of Done for any room:** primary actions round-trip to the backend; state persists across reload and sign-out; every notice reflects actual basis; empty, loading, and error states exist; role/permission enforced server-side; audit event on every mutation; harness assertions added; deployed to staging; ChromeConnect QA screenshots clean.

| Batch | Room | Backend work | Notes |
|---|---|---|---|
| 8A | Keyword Tracker | 21 routes exist; wire 4 tabs | Highest ready-to-wire. Move nav badge off Concept. |
| 8A | Profitability Dashboard | economics engine + contract + compute | Exports keep their basis (observed/assumed/unknown). |
| 8A | Shared Data Layer | inventory, retention, provenance, audit | Add DATA_RIGHTS enforcement view. |
| 8B | Commerce Ops | approvals quartet, OrgBalance, AuditEvent | Green signals never imply purchase authorization. |
| 8B | Command Center | composed read model: jobs, approvals, audit, dashboard | Handoffs carry UNKNOWN state. |
| 8B | Monitoring | health endpoint + provider/adapter/runner health | Include ChromeConnect status. |
| 8C | Listing Guardian | new `listing_observations`, rules, alerts | Read-only; never edits a listing automatically. Data via SP-API or ChromeConnect read of own listings (`ASK OWNER`). |
| 8C | Competitor Monitor | ASIN watchlists + snapshot job via vendor | Diff view; alerts. |
| 8D | ListingForge | drafts, revisions, Rufus-readiness score via LLM | Revert restores draft only; nothing publishes. |
| 8D | Creative Studio | asset jobs via image provider | Nothing published from here. |
| 8D | SocialPulse | draft calendar, no auto-post | Nothing posts autonomously. |
| 8E | AdPilot | Ads API adapter, keyword harvesting, bid calculator | Sandbox/read-only first; all writes need approval. Reuse `BrandMemory` context. |
| 8E | Memory Bank (F10) | new knowledge model with revision history and reversible unlearn | Replace the `ui_preferences` misuse. |
| 8E | Master Brain (F9) | Foundation route: routing log, cost per route, control surfaces | Confidence values labeled internal estimates. |
| 8F | Administration, Customer Workspace, Beta-Ops | already have backend | Verify every tab against real data. |

### PHASE 9 — AutothinK (agent product)

**P9-T1 Agent loop.** Implement as a durable-job handler `autothink.run`: plan → choose tool → call tool → observe → decide → stop. Hard limits per run: max steps, max tokens, max spend, wall-clock. State checkpointed each step; resumable; full transcript in `jobs_audit`.

**P9-T2 Tool registry.** Tools map 1:1 to allow-listed Foundation endpoints and `chromeconnect.*` tasks. Read tools run freely; write tools (draft, save, submit) require the same approval system; **no tool can purchase, publish, post, or change a live listing**. Each tool declares input schema, cost class, and whether it needs a signed-in browser (which triggers the sign-in gate).

**P9-T3 Grounding contract.** Every output claim cites a source (tool result ID) or says UNKNOWN. A post-check rejects any claim without a citation. "How Outputs Are Grounded" card shows the live rule.

**P9-T4 First agent: Gate Resolver.** Takes a Golden Goose item at `RESEARCH_REQUIRED` and tries to resolve each UNKNOWN gate (pack count, variation, brand permission claim, sourcing route) using allowed tools; returns resolved gates with evidence and remaining unknowns. Never flips a gate without evidence. Accept: on 10 real items, zero fabricated resolutions (owner spot-check sample).

**P9-T5 Composer and Output Detail.** Wire Runs · Composer · Output Detail to `POST /jobs-durable` and `GET /jobs-durable/runs/{run_id}`. Accept: run appears live, can be cancelled, and reloads.

### PHASE 10 — Production hardening

Cards (each with tests): **P10-T1** billing on Stripe *test mode* (entitlements, plans, portal), production keys only after owner approval. **P10-T2** transactional email for invites and lifecycle notices. **P10-T3** observability: structured logs, error tracking, uptime check, alert to the owner. **P10-T4** backups: nightly Postgres dump to encrypted off-site storage plus a **restore drill** documented and run once. **P10-T5** security pass: dependency audit, CSP review (remove `style-src 'unsafe-inline'` only if feasible), CSRF review, secrets scan of git history, per-tenant isolation tests (no cross-org reads), rate limiting on auth and heavy endpoints. **P10-T6** CI: build + all harnesses + backend suites on every push; deploy only from green main. **P10-T7** legal surfaces: Terms, Privacy, data-use notice; **counsel review is required before subscriber-facing use of any Amazon-derived data** (see DATA_RIGHTS). **P10-T8** accessibility and mobile pass (keyboard nav, contrast, 390 px layouts) across all rooms. **P10-T9** staging vs production separation with separate databases and secrets.

### PHASE 11 — Owner full-test pass

**P11-T1 Generate `docs/OWNER_TEST_GUIDE.md`.** One section per room: URL, prerequisites, exact click path, expected result, what real data it uses, how to tell it worked, and a PASS / FAIL / UNKNOWN checkbox. Include: "Golden Goose: run monthly Top-5 for one category and for all categories"; "SourceScout: look up a Kirkland item, confirm identity state and net/unit vs the $5 floor"; "ChromeConnect: force a signed-out site and complete the Needs You flow"; "AutothinK: run Gate Resolver on one item"; "Approvals: self-approve in test mode and confirm the audit trail".

**P11-T2 ChromeConnect walkthrough.** Automated pass through every route on staging: screenshots at three widths, console and network error capture, dead-link check. Output `qa/<date>/REPORT.md`.

**P11-T3 Honest completion report `docs/RELEASE_REPORT.md`.** For every room: WORKING / WORKING-WITH-LIMITS / BLOCKED, with the reason (missing credential, provider approval pending, data-rights hold). No room is reported WORKING without a passing round-trip test. List every remaining SAMPLE surface.

### PHASE 12 — Later (not part of "done")
Marketing site; custom Chromium shell with Northstar as the home page and ChromeConnect built in (ChromeConnect Runner protocol carries over); browser overlay on Amazon and Costco pages (Xray-style); ad-builder agents that source copyright-cleared imagery (license metadata stored per asset); public API; team seats.

---

## PART 4 — ITEMS THE OWNER MAY NOT HAVE CONSIDERED (all covered above; confirm priorities)
1. **Two repos and two `northstar.db` files** with different schemas (P0-T2).
2. **Data rights:** SellerSprite, PalletFly, Prime National and Amazon-derived data may not be redistributable to subscribers (P4-T3, P10-T7).
3. **Amazon and site terms for browser automation:** ChromeConnect is scoped to the owner's own sessions, read-only, human-paced, no challenge-solving (P6-T2, P6-T3).
4. **Spend runaway:** vendor and LLM calls need hard caps (P7-T1).
5. **Backups and restore drills** (P10-T4).
6. **Staging vs production** separation (P10-T9).
7. **Data freshness:** stale observations must degrade to UNKNOWN (P4-T4).
8. **Selector rot:** scrapers break; adapters are data-driven and self-report DEGRADED (P6-T4).
9. **Demo data toggle** so every room is testable before keys exist without lying about it (P3-T4).
10. **Runner security:** revocable tokens, pause-all kill switch, no inbound ports (P6-T1, P6-T2).
11. **Support and onboarding:** email, invite flow, status page (P10-T2, P10-T3).
12. **Purchase capital controls:** approvals ledger already exists; add a per-month purchase budget field before real buys (Commerce Ops, 8B).

## PART 5 — KICKOFF PROMPT (paste this first)
```
Read PART 1 of docs/NORTHSTAROS_MASTER_BUILD_PLAN.md and adopt it as binding. Then execute cards in order starting at P0-T1. Print only the REPORT FORMAT after each card. Use ASK OWNER blocks for anything missing. Use the ChromeConnect SIGN-IN GATE on every site with an account. Do not skip a card's Accept line. Do not touch frozen files. Begin.
```
