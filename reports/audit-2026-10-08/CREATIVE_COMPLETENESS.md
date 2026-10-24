# CREATIVE_COMPLETENESS — evidence-backed audit of all required creative work

**Audit date:** 2026-10-08 · **Baseline commit:** `2482048` · **Method:** line-level code inspection of every routed screen + shared components + design tokens.
**No screenshots were captured by this audit** (the newest repo screenshots are 2026-10-04). Visual findings below are code-derived, with line references; browser-level visual confirmation is listed as remaining work.

---

## A. Brand and product identity

### A.1 Suite identity and product hierarchy
- Suite identity is present and consistent: `northstar-os-ui/src/components/TopNav.jsx` (brand block), `SuiteRail.jsx` footer `"v2.0 — Internal Use"` (`:83`), `Icon.jsx` icon set.
- Hierarchy is coherent: Command / Research / Grow / Operate / Systems / Workspace (`src/data/nav-config.js:5-39`).
- **Finding C-A1 (P2):** The suite presents **19 rooms** in nav. The Phase-1 spec names services that do not appear anywhere in nav: **Operations Hub** (closest: Commerce Ops), **Ledger** (closest: Profitability Dashboard), **Prospector** (closest: SourceScout), **OfferChisel** (closest: ListingForge), **Town Crier** (closest: SocialPulse), **Auctioneer** (closest: AdPilot). `DEAD_SURFACE_MANIFEST.md` §C explicitly maps these as "legacy name for X", but **no customer- or operator-facing document states the rename**. Two of them (The Watch, RankLedger, Rival Board) are parked and invisible in the shipped app.
  - Impact: an operator who read the spec cannot find the service they were promised; a support conversation cannot reference a name that exists in no UI.
  - Fix direction: publish a canonical name/alias table in the UI (Settings → About) and in `README`/docs.

### A.2 AutothinK naming and positioning
- The room is titled "AutothinK" (`internal/AutothinK.jsx:223`) with subtitle "Research run workspace". The legacy page is `pages/Autothink.jsx` (unrouted).
- The copy is honest and internally consistent: "A research run never fabricates claims — every output cites its source or says UNKNOWN." (`:207`).
- **Finding C-A2 (P2):** The claim "every output cites its source" is **not yet true** — the local and hosted lanes emit no citations at all (see `AUTOTHINK_AUDIT.md` §Retrieval). Copy overstates current behavior.
- **Finding C-A3 (P3):** Naming inconsistency inside the product: the route is `/autothink`, the room title is "AutothinK", the legacy file is `Autothink.jsx`, the API namespace is `/api/autothink`. Four spellings of one product.

### A.3 Logos, icons, favicon, typography, colour, asset consistency
- Typography and colour are driven by tokens (`src/styles/tokens.css`, `src/styles/app.css`); Libre Baskerville (serif) + DM Sans (UI) per `AGENTS.md`.
- `Icon.jsx` is a central icon component used by nav/top-nav.
- **Finding C-A4 (P2):** No audit evidence of an automated asset-consistency check. `generated_images/` holds branding logos; there is no manifest tying logo files to routes/favicon. Favicon presence is not asserted by any test in the audited suites.
- **Finding C-A5 (P3):** `northstar-os-ui/screenshots/` (1,114 files, mostly Chrome-Connect `page-*.yml` snapshots from 2026-09-30 → 2026-10-04) is committed to the repo. This is a working scratch directory, not a curated asset set, and it bloats the tree.

### A.4 Customer-facing capability claims / no unsupported claims
- The readiness system (`src/data/readiness.js`) is genuinely good and is the strongest positive finding in this audit: `ready` (green) is reserved for rooms that genuinely work locally; `sample`/`concept`/`provider` are non-green and titled ("Renders sample data only — no live backend wired yet.").
- **Finding C-A6 (P1):** Three rooms do **not** use it:
  - `ProductFinder.jsx` — no `DataNotice` on the default lookup view; hardcoded prices/ranks/seller counts/mArgins shown with only `title` tooltips ("observed 2h ago", "cached snapshot") at `:112, :150`.
  - `internal/Admin.jsx` — `CONFIG_ROWS` hardcodes `"Environment: Production"`, `"Data Provider: Local (sample)"`, `"Live Calls: Disabled"` (`:67-72`) and renders 4 static "safety gates — all off" (`:74-79, :125`); only `tone="internal"` disclaimers.
  - Creative Studio's "Assets in library 87" (`:753`) is a static sample sum, labeled "Sample inventory" but rendered as a headline number.
- **Finding C-A7 (P2):** Underlying model/provider details are kept internal as required — `provider-adapters` shows env var **names** only (`ProviderAdapters.jsx:37,45,85,89`). This is compliant.

---

## B. Genuine new interface (presentation rebuild)

### B.1 Old shell removal — **CONFIRMED**
- Live shell: `TopNav` + `SuiteRail` + `MobileBottomNav` + `CommandPalette` + `ToastContainer` (`App.jsx:154-213`).
- `DEAD_SURFACE_MANIFEST.md` §B lists removed components (SideNav/Sidebar/Dock/RightRail/Header, PinnedDrawer, EnvBadge, OrgSelector, PreviewBanner, RouteGuard, and the foundation page cluster). `foundation/tests/test_frontend_gate.py::test_v3_shell_invariants` asserts the retired `Sidebar.jsx` is gone and that no v3 room imports the legacy client `services/api.js`.
- The old dark/neon console is not present in `styles/app.css` or `tokens.css`.
- **Verdict: this is a real rebuild, not a recolor.**

### B.2 Navigation usability
- Persistent navigation is retained (SuiteRail, always visible on desktop; role-filtered) **and** the command palette is additive — this matches the requirement that persistent navigation must not be replaced by a command interface.
- All nav routes resolve to real `<Route>` entries (verified: no dead deep links from nav).
- **Finding C-B1 (P2, soft drift):** `OrgsList.jsx:655` sample-roster "Open" navigates to `/beta-ops/orgs/${row.id}` using fictional ids (`0001`, `0521`, `0838`, `0788`) — lands on "No foundation organization with this id — nothing is fabricated." Honest, but it is a dead-end control.
- **Finding C-B2 (P2, security-adjacent):** `customer/Workspace.jsx:16-24` links customers to internal operator rooms. `App.jsx:72-75` only gates `/beta-ops*` and `/admin`; the internal rooms are reachable by any authenticated customer by URL. The pages will render honest "unavailable" states (they fail their auth'd reads), so this is a UX/IA defect more than a data-exposure one — but it must be closed.

---

## C. Screen completeness (every in-scope screen)

Method: per-file inspection for layout/hierarchy, states, components, controls, a11y, placeholders.

### C.1 Rooms that are genuinely complete
| Room | Evidence |
|---|---|
| Golden Goose | Real persisted queue/review/decisions; honest empty and error states; `DataNotice` marks fictional sample rows (`internal/GoldenGoose.jsx:409`) |
| Profitability Dashboard | Backend-authoritative economics; `EngineValue` renders UNKNOWN for nulls; **zero sample data**; `NotConnected` honest empties for portfolio/fee/inventory |
| Listing Guardian | Real local reads; honest empty states throughout (`:128,144,159,186,210`) |
| Competitor Monitor | Real reads; loading/auth/error/empty all present |
| Monitoring | 4 live reads; unavailable badge; honest empties |
| Commerce Ops | Real queue + approvals; honest empties |
| Keyword Tracker | Real reads; empty states |
| Shared Data Layer / Provider Adapters / Master Brain / Memory Bank | Real reads; honest empties; credentials shown as names only |
| Spreadsheet Lab | Genuinely functional CSV parse + export; honest error and empty states |
| Command Center | 7 live reads; real activity; **no fabricated numbers** |
| Admin / Beta-Ops (majority) | Foundation-backed; destructive controls disabled |

### C.2 Rooms with incomplete creative work
**Creative Studio** (`internal/CreativeStudio.jsx`, 783 lines) — localStorage only, no backend.
- `DataNotice tone="sample"` present (`:317`) — good.
- Sample seeds: 3 briefs, 6 assets, 5 variants, 4 collections (`:103-128`).
- Dead controls: "Save Storyboard" toast-only (`:516`); "Upload Asset" toast-only (`:655`); collection "Open" toast-only (`:770`).
- "Download Bundle" is `disabled` with an honest title (`:741`) — good pattern.
- No loading/error states exist because nothing loads (acceptable for a local store, but the room has no stale-data story).
- a11y: most selects/textarea labeled via `htmlFor` (`:393,402,408,416,422,428,489,495,501,508`); `<div className="label">Reference assets…</div>` (`:436`) is not a real label.

**SocialPulse** (`internal/SocialPulse.jsx`, 674 lines) — localStorage only, no backend.
- `DataNotice tone="sample"` (`:215`), `tone="unknown"` for analytics (`:634`) — good.
- **Broken control:** "New Campaign" (`:347`) cannot create — `campaigns` is destructured without a setter (`:136`).
- Dead: "Generate Variants" (`:210`), "Schedule" (`:211`), copilot suggestions (`:331, :498`), list "Open" (`:420`), "Upload Asset" (`:540`). Unused `setAssets` (`:138`).
- Calendar is a static September-2026 grid (`MONTH_CELLS :116-123`), not date-driven — only manually-reminded posts appear.

**AdPilot** (`internal/AdPilot.jsx`, 375 lines).
- **Dead control:** "Bulk Actions" at `:149` has **no `onClick` at all**.
- **Metric/label mismatch:** tab badge `count: 8` (`:10`) vs 5 rendered campaign rows (`:18-24`).
- **Fake charts:** `.meter-fill` widths hardcoded 98/95/84% (`:183-190`).
- Sample metrics presented as a table: budgets $300–800, spend, ACoS 12.3–31.2%, impressions 24,500/18,200/12,100/9,800/7,600, clicks 1,820/1,340/890/720/540 (`:182-186, 233-239, 284-289, 313-319, 340-344, 365-369`). Mitigated by `tone="sample"` (`:152`) and honest `title` attributes ("Sample window", "not verified tracking"), but these are the highest-risk skim-able numbers in the suite.
- Row "Open" ignores which row was clicked (`:172`).

**ListingForge** (`internal/ListingForge.jsx`, 378 lines).
- **5 dead buttons with no `onClick`:** `:249` "Save Revision", `:250` "Request Health Check", `:312` "Use Template", `:345` "Upload Assets", `:366` "Restore as Draft".
- **Label mismatch:** badge `count: 24` (`:10`) and pill "24 across 6 ASINs" (`:183`) vs 4 rendered rows.
- **Fake meters:** health bars hardcoded 92/76/88% (`:284,289,294`).
- Editor inputs use `defaultValue` with unassociated divs (`:232,246`).

**SourceScout / Product Finder** (`internal/ProductFinder.jsx`, 281 lines) — **fully static**.
- Hardcoded: 4 products (`:13-18`) with prices/ranks/offers/margins; 3 saved sets; **10 hardcoded decision-gate values** (`GATES :42-53`); 5 coverage rows.
- The Decision Rail presents these 10 gate values as a live decision surface (`:128-141`); `unverifiedGates` (`:83`) is computed from a `const`.
- **The default view carries no `DataNotice`**; sample notices appear only on subviews (`:210, :236, :257`).
- No loading/empty/error states at all (static page).
- This is the single largest creative-completeness gap among the non-creative rooms: the highest-stakes surface (sourcing + purchase gating) is the least honest.

**Spreadsheet Lab**, **Profitability Dashboard**, and the Systems rooms have no sample data — correct.

### C.3 Shared components
- `DataTable` (`components/Shared.jsx:22-51`) requires `thead/tbody` and renders an `emptyText` row — good. Defects: action columns declared `label: ''` render an empty `<th></th>` (`:29`); rows keyed by array index (`:38`); no `<caption>`, no `scope` on headers.
- `DataNotice` (`:71-86`) supports `sample|cached|concept|internal|assumption|unknown` and renders a "SAMPLE DATA" pill — the mechanism is good; three rooms simply don't use it.
- `PageLayout` (`:110-130`) derives a readiness pill from `readinessForRoute` — good.

### C.4 Accessibility defects (representative, with lines)
| Defect | Location |
|---|---|
| Clickable `<div>` brand with no role/keyboard | `TopNav.jsx:21` |
| Palette input with no `aria-label`; results list with no `role="listbox"`/`aria-activedescendant` | `CommandPalette.jsx:30-57` |
| Empty `<th>` for action columns | `Shared.jsx:29` + every consumer |
| Search input placeholder-only | `MemoryBank.jsx:76` |
| Analysis textarea unlabeled | `SpreadsheetLab.jsx:98-104` |
| Read-only checkboxes with unassociated labels | `internal/GoldenGoose.jsx:184,192` |
| Usage meter div with no `role="progressbar"`/aria values | `customer/PlanUsage.jsx:83` |
| Decorative SVG placeholder with no `alt`/`aria-hidden` | `ProductFinder.jsx:101-103` |
| Calendar cells non-interactive, `title`-only | `SocialPulse.jsx:263,269` |
| `<div className="label">` used as a label | `CreativeStudio.jsx:436` |

---

## D. Complete customer and administrator journeys

| Journey | State | Evidence |
|---|---|---|
| Landing / service selection | IMPLEMENTED | `public/BetaLanding.jsx` |
| Invite acceptance | IMPLEMENTED (harness-covered) | `public/BetaInviteAccept.jsx`; `verify-invite-flow.cjs` 11/0 |
| Login | IMPLEMENTED, **NOT EXERCISED with real credentials** | `public/SignIn.jsx`; `verify-live-signin.cjs` **BLOCKED** (needs `NS_TEST_EMAIL`/`NS_TEST_PASSWORD`) |
| Onboarding / workspace setup | PARTIAL | `customer/Setup.jsx`, `Workspace.jsx`; legal acceptance recording disabled |
| Research → review → save → compare → evidence | PARTIAL | SourceScout static; Golden Goose real; no cross-room comparison surface |
| AutothinK entry points and task/results | PARTIAL (local lane works, hosted broken) | `AUTOTHINK_AUDIT.md` |
| Settings / account / permissions | PARTIAL | `customer/AccountStatus.jsx` real session identity; no settings surface |
| Help / support / policies / legal | PARTIAL | `customer/Support.jsx` real submit; `customer/Legal.jsx` accept disabled (honest) |
| Admin / beta-ops | IMPLEMENTED | `admin/*` 4 files + harness 33/0 |
| Billing / usage / entitlement | PARTIAL | `plan-usage`/`entitlements` real; **PlanUsage meter 68% and $299.00 billing rows are hardcoded** (`:83, :96-100`) and labeled sample; Stripe parked |

---

## E. Classification of findings

### Objective defects (must fix)
1. P0-01 live provider calls on a plain GET (technical, but it breaks the creative promise "no live data without an explicit command").
2. Dead/inert controls: `AdPilot.jsx:149` (no onClick), `ListingForge.jsx:249,250,312,345,366`, `SocialPulse.jsx:347` (broken create), `SocialPulse.jsx:210,211,331,420,498,540`, `CreativeStudio.jsx:516,655,770`, `Monitoring.jsx:235`, `KeywordTracker.jsx:58,59`, `CompetitorMonitor.jsx:133,134`, `ProfitabilityDashboard.jsx:169,183`, `OrgsList.jsx:655`.
3. Missing `DataNotice` on `ProductFinder.jsx` default view and `internal/Admin.jsx` config/safety panels.
4. Metric/label mismatches: `AdPilot` 8 vs 5, `ListingForge` 24 vs 4.
5. Fake static meters: `AdPilot.jsx:183-190`, `ListingForge.jsx:284-294`.
6. Accessibility defects listed in §C.4.
7. Customer-role access to internal rooms (`Workspace.jsx:16-24` + `App.jsx:72-75`).
8. Product Designer Studio unaudited.

### Unmet approved requirements
- `noncreative_reads` silent-empty (breaks "unknown is not zero") — see `TECHNICAL_COMPLETENESS.md`.
- AutothinK "every output cites its source" copy vs no citations.
- Performance targets: **no approved target exists** → missing requirement, not a defect.

### Subjective design proposals (NOT defects; recorded separately, require owner approval)
- Add a canonical alias table to the UI so spec names map to shipped names.
- Replace the static SocialPulse calendar with a date-driven month grid.
- Curate `northstar-os-ui/screenshots/` into a small, named evidence set and stop committing Chrome-Connect scratch output.
- Add `<caption>`/`scope` to `DataTable`.
- Consider a persistent "data freshness" strip so cached-vs-live is visible without hovering.

---

## F. Verdict

**All required creative work complete? — NO.**

What is complete and verified: the presentation-layer rebuild itself (shell, tokens, nav, deep links, readiness labelling discipline, build integrity, most rooms' state handling).

What is not: 1 service unaudited; 3 creative rooms still shells; ~18 dead or broken controls; 3 rooms presenting hardcoded metrics without a sample notice; 2 rooms whose own labels contradict their rendered rows; a documented a11y backlog; and copy in AutothinK that overstates a capability (citations) that does not exist.
