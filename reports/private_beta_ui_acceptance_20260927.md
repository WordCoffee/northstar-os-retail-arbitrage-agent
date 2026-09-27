# NorthstarOS Private-Beta UI Acceptance Pass (2026-09-27)

Scope: final acceptance of the private-beta UI. No broad redesign; no live providers enabled. Recent commit/test claims were treated as **reported** until independently reproduced against the running UI, fresh screenshots, and the backend suite.

Legend: **VERIFIED** = independently reproduced · **REPORTED** = claimed/evidenced but not fully reproduced here · **FAILED** = reproduced failure · **UNKNOWN** = insufficient evidence.

---

## 1. Build / test reproduction

| Check | Command | Result | Status |
|---|---|---|---|
| UI build | `cd northstar-os-ui && npm run build` | 82 modules, 0 errors (js 429.40 kB, css 37.36 kB) | **VERIFIED** |
| Smoke suite | `node verify-smoke.cjs` | 40 passed, 0 failed | **VERIFIED** |
| Role-guard suite | `node verify-guards.cjs` | 8 passed, 0 failed | **VERIFIED** |
| Acceptance harness (new) | `node verify-acceptance.cjs` | 26 passed, 0 failed | **VERIFIED** |
| Backend package tests (committed baseline `a2238ec`) | `python -m pytest costco_non_kirkland/tests -q` | 180 passed, 0 failed (at commit time) | **REPORTED** |
| Backend package tests (current working tree) | `python -m pytest costco_non_kirkland/tests -q` | **FAILS collection** — untracked WIP file `test_brightdata_schema_test.py` has a SyntaxError | **FAILED** (out-of-scope untracked WIP) |
| Backend package tests (excluding WIP file) | `python -m pytest costco_non_kirkland/tests -q --ignore=costco_non_kirkland/tests/test_brightdata_schema_test.py` | 181 passed, 0 failed | **VERIFIED** |

---

## 2. Visual acceptance

Method: fresh desktop (1440×900) and mobile (390×844) captures via `capture-acceptance.cjs` (role-stubbed). Artifacts `screenshots/55*` (desktop), `56*` (mobile).

- **SourceScout (frozen benchmark):** unchanged and rendering correctly at desktop and mobile — identity strip, Decision Rail (8 of 10 gates unverified), Market Evidence, Economics (UNKNOWN/NOT CALCULATED), provenance. No regression; left untouched. **VERIFIED**
- **SocialPulse, Creative Studio, Listing Guardian, Keyword Tracker, Monitoring, Admin, Beta-Ops:** identities distinct, hierarchy intact, truth labels present, no banner+table+dead-space regressions. **VERIFIED (desktop)**
- **Mobile widths:** Monitoring, Beta-Ops, SourceScout, Customer Workspace render acceptably (grids collapse, tables scroll). SocialPulse queue board overflowed phone width and was **fixed** (see P1). Some fixed-grid rooms remain cramp-prone on phone width (P2). **REPORTED (mobile)** — one P1 fixed, P2s listed below.

---

## 3. Functional acceptance (running UI)

`verify-acceptance.cjs` — 26/26. Covered:
- **Deep links** (platform_admin): SocialPulse composer/queue, Creative variants, Guardian history/diffs, Keyword coverage, Monitoring health, Beta-Ops, Beta-Ops eligibility, Admin, SourceScout — all render their expected markers.
- **Primary actions:** SocialPulse "Draft Post" → composer; Guardian "New Rule" → escalations; SourceScout "Saved Sets" → saved; Beta-Ops "Export Report" → reports. Toast-only actions (Creative "New Brief", Keyword "Track New", Monitoring "Configure Alerts") fire without navigation.
- **Sample-control honesty:** SocialPulse "Send to Approvals" toast includes "nothing publishes automatically"; Beta-Ops lifecycle confirm is **disabled**; Monitoring "Configure Alerts" does not navigate.
- **Role guards (running UI):** signed-out / customer / operator are redirected off `/beta-ops` and `/admin` → `/home`; platform_admin loads both. **VERIFIED**
  - Note: an authenticated **customer** can deep-link into internal rooms (`/product-finder`, `/listings`). This is **by design** — Customer Workspace "Entitled Services" exposes those rooms with **Open** actions. Invitee (signed-out) lands on the shell (`/home`) per the established guard baseline. No authorization defect found.

---

## 4. Data & provider safety

- **UI/GET zero live provider calls:** the routed app's only network calls are foundation session bootstrap (`/api/v1/foundation/ui-mode|me|environment|preview/active`). Rooms use static sample data + toasts/navigation; no provider fetches. Pages that call `providers()`/`autothinkRun()` (`pages/Account.jsx`, `pages/Hub.jsx`, `pages/TownCrier.jsx`, `pages/OfferChisel.jsx`, `pages/Autothink.jsx`, `foundation/pages/*`) are **not routed** in `App.jsx`. **VERIFIED**
- **SellerSprite unavailable / fails closed:** removed from adapter registry, importer, schema/detection, CLI, sign-in, and guard allowlist; `provider_factory("sellersprite")` raises `ProviderRetired`; `plan_enrichment` returns `retired_provider`; retired sign-in/detection rejected; CLI `import-sellersprite` absent and `--provider sellersprite` rejected. Confirmed by tests (P6/P7/P8 in `test_provider_imports.py`, `RetiredProviderTests`). **VERIFIED**
- **SellerAmp status (from code):** **REPORTED — offline only.** `SellerAmpProvider` is disabled-by-default and returns `provider_not_configured` / `requires_explicit_approval`; `SellerAmpImporter` parses local CSV/JSON only. There is **no live API client, credential use, browser automation, or network path**. Not described as live integration. **REPORTED**
- **Truth states not conflated:** UNKNOWN vs UNVERIFIED distinct (SourceScout); cached/observed/historical tags muted (Guardian/Keyword/Beta-Ops audit); Monitoring health green reserved for live-probe-backed checks. **VERIFIED**
- **No paid calls / no catalog mutation:** no live provider calls made; production cache/catalog assets were not altered (only new `screenshots/` and report artifacts written). **VERIFIED**

---

## 5. Repository hygiene (newly tracked 58-file package)

- No credentials, API keys, tokens, cookies, browser profiles, emails, or personal data in the committed package; risk-word matches are policy text (e.g., "never log secrets", env-var **names** only). `preflight()` explicitly never prints credential values. **VERIFIED (committed package)**
- **Concurrent/uncommitted work detected (out of scope, not touched):** the working tree now contains a parallel "Bright Data" workstream — modifications to `brightdata_costco_enrichment.py` (+144), `cli.py` (+25), `test_brightdata_preflight.py`, plus new untracked `tests/test_brightdata_schema_test.py` (broken), `config/brightdata_costco_collector.json`, `Northstar_backend/_urlprobe.py`, `provider_research_*`, and DB/snapshot churn. These were **not** committed or deleted. **REPORTED**
- Minor: mojibake em-dash in the untracked `config/brightdata_costco_collector.json` (`"Costco products �?" Collect by URL"`). **REPORTED (P2)**

---

## 6. Defects

### P1 — fixed in this pass
1. **SocialPulse queue board overflows at phone width.**
   Repro: open `#/socialpulse?view=queue` at 390px — the 4-column CSS grid (`repeat(4, 1fr)`) compressed to ~90px/column and clipped the 4th column.
   Fix (`d068611`): `gridTemplateColumns: 'repeat(4, minmax(170px, 1fr))'` + `overflowX: 'auto'`. Re-verified: build clean, smoke 40/40, guards 8/8, acceptance 26/26, mobile re-shot shows readable columns with horizontal scroll.
   Path: `northstar-os-ui/src/pages/internal/SocialPulse.jsx`.

### P2 — actionable, not fixed
2. **Other fixed-grid rooms cramp at phone width.** Creative Studio Assets/Variants (`repeat(3, 1fr)`) and Guardian Diffs (`320px 1fr`) do not collapse at 390px. Repro: `#/creative-studio?view=assets` at 390px. Paths: `CreativeStudio.jsx`, `ListingGuardian.jsx`.
3. **ProviderAdapters uses green-ish `pill-forest` for sample "Active"/"Configured" adapter states** — borderline truth-state conflation; prefer muted unless live-verified. Path: `northstar-os-ui/src/pages/internal/ProviderAdapters.jsx:43,103-107`.
4. **Untracked WIP test file blocks plain backend test collection.** `python -m pytest costco_non_kirkland/tests` fails at collection on `test_brightdata_schema_test.py` (SyntaxError line 63). Exclude or finish the file. Path: `Northstar_backend/costco_non_kirkland/tests/test_brightdata_schema_test.py` (untracked, not part of the committed deliverable).
5. **Legacy unrouted pages remain** (`pages/Account.jsx`, `Hub.jsx`, `TownCrier.jsx`, `OfferChisel.jsx`, `pages/Autothink.jsx`, `foundation/pages/*`, `public/BetaDenied.jsx`, and 9 orphaned pages under `customer/` + `internal/Home|Listings|Portfolio|Sourcing`). Dead code; some contain provider/network calls. Risk of accidental wiring. Remove in a hygiene pass.
6. **Mojibake em-dash** in untracked `config/brightdata_costco_collector.json` (encoding hygiene).

---

## 7. Readiness verdict

- **Desktop: READY for owner acceptance.** All spot-checked rooms render correctly; SourceScout holds as the frozen benchmark; navigation, deep links, primary actions, role guards, sample honesty, and provider safety all verified.
- **Mobile: READY with tracked polish.** The one demonstrated P1 (SocialPulse queue overflow) is fixed; remaining P2 grid-collapse polish is listed, not blocking.
- **Backend: reproducible green** at baseline / excluding out-of-scope untracked WIP.
- **Caveat:** a parallel uncommitted "Bright Data" workstream is active in the repo; it is not part of this acceptance and was neither committed nor altered.

No security issue, live-provider/spend decision, destructive data change, or cross-cutting architecture conflict required stopping.

## Artifacts
- Harnesses: `northstar-os-ui/verify-acceptance.cjs`, `northstar-os-ui/capture-acceptance.cjs`
- Screenshots: `northstar-os-ui/screenshots/55*` (desktop), `56*` (mobile)
- Fix commit: `d068611` — SocialPulse queue mobile overflow
