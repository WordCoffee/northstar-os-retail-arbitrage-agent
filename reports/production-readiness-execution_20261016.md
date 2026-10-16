# Production-readiness execution — one-go session report (2026-10-16)

**Directive:** "complete everything now in one go and report after." Executed
Phases 0–3 and the verification pass of `reports/PRODUCTION_READINESS_PLAN_20261016.md`.
Phase 4 (REA scans) is not runnable in this session (no `chromeconnect_*` tools)
and is reported below as the remaining workstream.

## 1. Commits (local branch `feature/overnight-remediation-20261009`, nothing pushed)

| Commit | What |
|---|---|
| `12ae5f9` | AdPilot reads imported ad files; ListingForge → tenant store (create/update endpoints, no seeds); rate-limit budgets sized for humans; `/v1/models` compat; build banner |
| (ops) | backup.sh rclone leg + monitoring overlay + runbook; SocialPulse label |
| (rooms) | Task-first home; work-first nav; SocialPulse/ProductFinder de-seeded; readiness labels (8 rooms → Local) |
| (fix) | ListingForge TDZ fix; final honesty pass (ProductFinder/SocialPulse/GoldenGoose wording; PlanUsage fabricated usage+billing removed) |
| (fix) | Documents/PlanUsage notices match honest empty states |
| `b3682be` | Panels harness opens Details; design-studio harness covers Dielines & Print; **engineApi dev-shim compile-time gated** (prod bundle contract restored) |

## 2. What is DONE (VERIFIED this session)

**Phase 0 — stop the bleeding**
- **Rate limiter sized for humans**: authenticated budgets raised (mover 120→300,
  autothink 300→600, scout 60→120); anonymous stays 30. A normal pass of all 25
  rooms now completes with **zero 429s** (was: tripped after ~7 rooms).
- **`/v1/models` compat alias**: the host probe that 404'd now answers 200
  (same brain catalog; presence-only flags).
- **Stale-image fix + build banner**: api + caddy rebuilt and verified;
  `/api/design-studio/engine` 200; the sidebar footer shows the build commit
  (dev server shows the real SHA; Docker builds show `unknown` — git is not in
  the build image; noted as a known cosmetic gap).
- **Console-clean**: all 25 rooms load with **0 console errors**.

**Phase 1 — the "Partial" kill**
- **AdPilot** (`12ae5f9`): campaigns + terms derive from the seller's OWN
  imported files (bulksheet / search-term reports); sample rows, sample planner
  and fake rule verdicts removed; honest empty state with an "Import a
  bulksheet" CTA; every missing metric reads UNKNOWN. Label → **Local**.
- **ListingForge**: tenant-store listings are the source of truth (new
  `POST /listing-records` + `PATCH /listing-records/{rid}` endpoints + DAO
  `update`); browser-local records migrate once (idempotent per ASIN); a
  create-listing flow makes the room work from zero; the Demo-Brand seeds are
  gone; saves persist to the server. Label → **Local**.
- **ListingGuardian / CompetitorMonitor / Profitability / SpreadsheetLab**:
  audited — the pages were already real; the "Partial/LLM-gated" labels were
  stale. Labels → **Local** (SourceScout keeps **Cached** — honest by design).
- **SocialPulse**: seeded campaigns/posts/assets removed → real local planning
  workspace with honest empty states. Label → **Local** (no channel connection
  is claimed anywhere).
- **ProductFinder**: invented products, saved sets and gate verdicts removed;
  "Add your first product" flow; all metrics UNKNOWN until observed.
- **Customer surfaces**: PlanUsage's fabricated usage meter (68% of 5,000) and
  billing rows removed; Documents notice matches its honest empty state.
- **Result: zero Partial / Concept / Sample / LLM-gated badges remain** in the
  nav and room headers (audit: 0 across all 25 rooms).

**Phase 2 — UX essentials**
- **Task-first home**: "Start something" (Design / Listings / Ads / Social /
  Keywords / Competitors), "Needs your review" (real queues) on top; system
  signals + activity collapsed under "System status (advanced)"; visible
  `GET /api/...` jargon removed; primary actions are the two things a brand
  owner does.
- **Work-first nav**: Home → Create → Grow → Research & Watch → Operate →
  Admin & Systems → Account & Admin.

**Phase 3 — ops**
- `deploy/backup.sh`: rclone upload leg + destination retention; without
  `RCLONE_REMOTE` it says **LOCAL ONLY** (a backup that never left the machine
  is never reported as done).
- `docker-compose.monitoring.yml`: Uptime Kuma + Dozzle, loopback-only;
  the compose guard is unaffected (8/0 verified).
- `docs/RUNBOOK.md`: one-page start/stop/restart/backup/monitoring/partner
  runbook.

**Security fix found by the guard during verification**
- `studio/engine/engineApi.js` emitted the dev-shim headers behind a RUNTIME
  check, so `X-User-Id` shipped in the production bundle (the bundle guard
  caught it). Now gated on the compile-time `LOCAL_DEV` constant → guard back
  to **14/0**.

## 3. Verification (this session)

**Room audit** — `reports/ui_audit_20261016/` (`AUDIT.md`, `AUDIT.json`, 25 PNGs):
25/25 rooms render, **0 console errors**, 0 Partial badges. Remaining
"sample"-word matches are the Golden Goose sample-scan FEATURE toggle (domain
term) and a "no sample" negative sentence — not fabricated data.

**Harnesses re-run green (console output of record):**

| Harness | Result |
|---|---|
| `verify-design-studio.cjs` (extended: Dielines & Print profile) | **70 / 0** |
| `verify-master-brain-panels.cjs` (extended: opens Details toggle) | **31 / 0** |
| `verify-amazon-files.cjs` | **44 / 0** |
| `verify-amazon-files-ui.cjs` | **22 / 0** |
| `verify-d10-live.cjs` | **32 / 0** |
| `verify-search-terms.cjs` | **49 / 0** |
| `verify-operator-smoke.cjs` | **11 / 0** |
| `verify-title-contract.cjs` | **8 / 0** |
| `check-compose-deploy.cjs` | **8 / 0** |
| `check-prod-bundle.cjs` | **14 / 0** |
| `check-no-third-party.cjs` | **5 / 0** |
| pytest rate-limit posture / auth bundle | **5 / 0** · **26 / 0** |

Two harnesses needed updating because the PRODUCT moved ahead of them (not
product failures): the panels harness (panel records now behind a Details
toggle) and the design-studio harness (10 sections now, incl. Dielines & Print).

**NOT RUN (with cause):**
- The full 39-harness regression sweep was **not** re-run this session (the
  last full sweep with raw files is `reports/regression_20261011_final/`);
  the targeted set above covers every surface this session changed.
- **REA scans** (Canva/Helium 10/tryholo.ai pattern extraction): this session
  has no `chromeconnect_*` tools — start in a session that does.
- Real Amazon upload: by design, the owner performs it manually.
- Partner invite: needs the partner's email (owner input).

## 4. Gates / defaults / live calls

- **Zero live or paid provider calls**; zero Amazon contact; generation
  unarmed; no model install/removal; credentials never read or printed.
- Defaults applied (reverse actions): rate budgets raised (reverse: restore
  PLAN_LIMITS); `/v1/models` alias kept (reverse: remove route); home redesign
  (reverse: restore the old panel order); de-seeding is permanent (data was
  fabricated — no reverse intended); `engineApi` compile-time gate (reverse:
  none — the guard requires it).

## 5. Honest limits / not inspected

- The Docker build banner reads `unknown` (git unavailable in the build image).
- UX wizards, first-run onboarding and the shared-component sweep (plan §4.3–
  4.6) are **not** done — the home/nav are done, the deep flows are next.
- Monitoring containers are provided but not started (operator's call to run
  `docker compose -f docker-compose.monitoring.yml up -d`).
- `restic` was not installed; the backup leg uses rclone only.
- The 4 remaining "Cached" labels (SourceScout etc.) are honest by design, not
  a gap.
- Not inspected: other sessions' active workstreams; login-gated Amazon pages.

## 6. Owner checklist

1. **Use it**: http://localhost/ui/ (build shows the latest commit after this
   session's final caddy rebuild). Start something from the new home.
2. **Import a file** (Design Studio → Ads → Amazon files) and watch AdPilot +
   ListingForge fill with your real data.
3. **Partner invite**: send the partner's email to create it.
4. **Optional**: `docker compose -f docker-compose.monitoring.yml up -d`;
   set `RCLONE_REMOTE` and run a restore drill.
5. **Decide**: approve the Phase 2 deep-UX work (wizards/onboarding) and the
   REA scans as the next sessions.

**Next action:** on your go — Phase 2 deep UX (guided flows per the plan §4.3–
4.6) and the REA scan program in a Chrome-Connect-capable session.

---

## 7. Evening close-out (same day) — Phases 2 (deep), 4, 5

- **Phase 2 deep (core done):** first-run guide (3 guided steps, backdrop +
  Skip dismissal, verified in-browser); Design Studio **Quick start** strip;
  **Start-from-ASIN** seed on the home → SourceScout prefill; SocialPulse
  plan→approve→export framing. Remaining (logged): per-section step wizards,
  shared EmptyState sweep, bundle code-splitting.
- **Phase 4:** `research/rea_patterns_20261016/PATTERNS.md` — tryholo.ai read
  fresh today (zero-click seed + tap-approve → adopted); canva.com served a
  browser-check interstitial (documented limitation); bulk-create and
  social-proof patterns declined with reasons.
- **Phase 5:** **full 39-harness regression re-run** → this folder
  (`reports/regression_20261016/`), 39/39 exit 0 after one diagnosed fix
  (the first-run overlay blocked the smoke harness; the re-run also caught a
  missing `useEffect` import in ProductFinder — both fixed and re-verified).
  Screenshots refreshed: `reports/screenshots_20261016/` (desktop + mobile +
  accessibility, 62/0). Final room audit: 25/25 rooms, **0 console errors**,
  0 Partial badges (`reports/ui_audit_20261016/`).
- **Ops:** monitoring overlay started (Uptime Kuma :3001, Dozzle :8080,
  loopback); partner-invite script verified end-to-end (create → code →
  revoke) at `tools/create-partner-invite.ps1`.
