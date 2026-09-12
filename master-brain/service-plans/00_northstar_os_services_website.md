# Northstar OS — Services Suite Website: Master Plan & Architecture

> **Status:** Approved for construction (Autonomous Zone — build/test only; no live call,
> no credential value, no real spend.)
> **Date:** 2026-09-12
> **Derives from:** `master-brain/northstar-os-master-plan.md` (§4 Services Suite, §2
> Master Brain), profile `t2-holdings-tyrone-johnson` (brands/thresholds/voice), and the
> three UI design guides (`Northstar_UI_Design_Guide.md`,
> `Northstar_OS_UI_Design_Guide.md`, `Northstar_AutothinK_UI_Design_Guide.md`), which
> this doc **consolidates** into one canonical design system.

---

## 1. GOAL

Build the **complete Northstar OS website** — a unified, hash-routed single-page-app
shell hosting one hub plus four full service apps, each backed by its dedicated agent:

| # | Service (public) | Agent (internal) | State |
|---|---|---|---|
| 1 | **SourceScout** | Retail Arbitrage Agent | Existing tested dashboard — wrap & extend |
| 2 | **ListingForge** | Listing Optimizer Agent | New build |
| 3 | **AdPilot** | Amazon Ads Agent | New build |
| 4 | **SocialPulse** | Social Media Agent | New build |

Plus the second surface — **Northstar AutothinK** (premium "build-anything" chat
workspace) — polished and reachable from the same shell.

The website must **mimic but not copy** Helium 10 / Jungle Scout: borrow the power-user
workflow contract (dense sortable/filterable tables, left-nav service hub, facet filters,
bulk-operation panels, per-service dashboards behind one shell) but never their names,
logos, trademarked features, or exact layouts. Northstar's identity is its own.

## 2. DESIGN SYSTEM — "THE ANALYST'S DESK" (canonical)

Neo-skeuomorphic: a high-end physical workspace meets digital precision.

### 2.1 Tokens (canonical — implemented once in `css/tokens.css`)

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#1A1A1A` | App background (charcoal) |
| `--bg-elevated` | `#232323` | Panels, cards |
| `--bg-sunken` | `#141414` | Sidebar wells, table header |
| `--panel-surface` | leather texture gradient | main card borders |
| `--aluminum` | brushed-aluminum gradient | sidebar / topbar |
| `--gold` | `#D4AF37` | Profit / success accents |
| `--steel` | `#4682B4` | Navigation / primary |
| `--crimson` | `#8B0000` | Critical alerts ("red wax") |
| `--ink` | `#EAE4D8` | Primary text (warm paper-white) |
| `--ink-dim` | `#9C948A` | Secondary text |
| `--hairline` | `#3A3A3A` | Borders |
| `--font-head` | `'Playfair Display', 'Merriweather', serif` | Headers |
| `--font-body` | `'Roboto Mono', 'IBM Plex Mono', monospace` | Data / body |

### 2.2 Signature components

1. **The Ribbon** (top nav) — gold-accented bar; global stats (Total Profit, BSR
   Health); global search styled as a magnifying glass with a glowing rim.
2. **The Drawer** (left sidebar) — vertical list of "notebooks"; active notebook
   "opens" onto the work surface. Notebooks map to services + hub.
3. **The Work Surface** (main center) — high-density tables; each row is a "physical
   card" (paper texture + subtle drop shadow) that can be pinned.
4. **The Bulletin Board** (right sidebar) — digital corkboard for pinned actionable
   notes ("Price war on B08X", "Stock out in 5 days").
5. **The Paperclip Assistant** — sits at the screen edge; on a Profit Spike or Rank
   Drop it "holds up" a tiny digital note with the insight.
6. **Rotary Knobs** — metal-look knobs for adjusting thresholds (Profit Target,
   Inventory Levels, ROI gate).
7. **Ink-Plot charts** — line charts styled like ink plots on graph paper.

### 2.3 Icon system — "Polaris"

Minimalist 2px-stroke, glowing on active. Icons: Compass (Niche Finder), Crosshair
(Target ASIN), Battery (Inventory), Lightning Bolt (Auto-Repricing), Prism (Profit &
Revenue), Synapse (AI Core). Plus service icons per §4.

### 2.4 North Star logo

Stylized 8-pointed star, hollow center; rotates slowly and pulses with a soft steel-blue
glow.

## 3. CODE ARCHITECTURE — ONE SHELL, HASH-ROUTED SPA

```
Northstar_backend/static/northstar-os/
├── index.html            ← the shell (Ribbon + Drawer + Work Surface + Bulletin Board)
├── css/
│   ├── tokens.css        ← §2.1 canonical tokens (consolidates the 3 design guides)
│   ├── shell.css         ← shell layout (Ribbon/Drawer/Work Surface/Bulletin Board)
│   ├── paperclip.css     ← Paperclip Assistant + note styling
│   └── services.css      ← shared service-view styles (tables, cards, knobs, pills)
├── js/
│   ├── engine.js         ← shared: hash router, drawer nav, bulletin board, paperclip,
│   │                       global search, rotate-knob component, ink-plot charting, demo-data loader
│   ├── hub.js            ← suite hub (service cards + global KPIs)
│   ├── sourcescout.js    ← SourceScout service logic (wraps existing engine)
│   ├── listingforge.js   ← Listing Studio, Scoring, Compliance, A+/Media, Keyword Bridge
│   ├── adpilot.js        ← 4-tier campaigns, harvester, bid optimizer, bulk CSV
│   └── socialpulse.js    ← Content Studio, Calendar, Creative Prompts, Outreach, Voices
├── fixtures/
│   ├── demo-products.json        ← labeled demo product rows (SourceScout)
│   ├── demo-keywords.json        ← labeled demo search terms (AdPilot)
│   ├── demo-listings.json        ← labeled demo listings (ListingForge)
│   ├── demo-posts.json           ← labeled demo social posts (SocialPulse)
│   └── demo-notes.json           ← pinned bulletin notes
└── tests/
    └── test_shell.cjs            ← jsdom contract tests for the shell + services
```

### 3.1 Routing map

| Hash | View | Module |
|---|---|---|
| `#/hub` | Suite hub — service cards, global KPIs | `hub.js` |
| `#/sourcescout` | Retail Arbitrage Agent app | `sourcescout.js` (hosts existing engine) |
| `#/listingforge` | Listing Optimizer Agent app | `listingforge.js` |
| `#/adpilot` | Amazon Ads Agent app | `adpilot.js` |
| `#/socialpulse` | Social Media Agent app | `socialpulse.js` |
| `#/autothink` | AutothinK link-out (opens `autothink/ui/index.html`) | shell |

Unknown hashes fall back to `#/hub`. `hashchange` drives view mounting; no page reload.

### 3.2 Data honesty contract (repo-wide rule, carries into UI)

- Demo/mock data is **always labeled** (`demo` badge, `data-kind="demo"` attribute).
- Missing values render as `—` / "unknown", never fabricated zeros.
- Every live-gated control shows an Authorization Gate state, never silently fires a
  network call. This mirrors the hard stop zone — UI never tricks the user into a live
  action.

### 3.3 gated-live-path convention

Each service has at least one control whose *code path is fully built* but whose
execution requires explicit approval. Pattern: `data-live-gate="off"` + off-preflight
banner + typed "authorization required" tooltip. The gate flips only via operator config,
never from the UI when off.

## 4. SERVICE SPECS — per-service plan docs

Each service has its own architecture doc (this directory):

| Doc | Service |
|---|---|
| `01_listingforge.md` | Listing Optimizer Agent |
| `02_adpilot.md` | Amazon Ads Agent |
| `03_socialpulse.md` | Social Media Agent |
| `04_sourcescout.md` | Retail Arbitrage Agent (wrap & extend) |
| `05_autothink_surface.md` | AutothinK surface |

Each doc contains: screens → components → data contracts → labeled demo fixtures →
gated-live paths → test contract → step-by-step build order.

## 5. TEST STRATEGY

- **jsdom contract tests** (`tests/test_shell.cjs`) mirroring the existing
  `Northstar_backend/test_ui_display.cjs` pattern (986 assertions currently green) —
  the SourceScout wrap must keep that contract green.
- Node test runner: `node Northstar_backend/static/northstar-os/tests/test_shell.cjs`.
- Every phase ships its tests with the commit; only real assertion counts are reported.
- Python suite untouched by this work (surface-only); full regression run at phase ends.

## 6. PHASE PLAN (step-by-step build order)

1. **Phase 0 — Foundation.** `tokens.css`, `shell.css`, `index.html` shell, `engine.js`
   (router + Drawer + Bulletin Board + Paperclip + knobs + charts), `hub.js`, demo
   fixtures, `test_shell.cjs`.
2. **Phase 1 — SourceScout wrap.** Host existing dashboard in `#/sourcescout`, apply
   Analyst's Desk tokens, keep engine/IDs/data-view intact → re-run
   `test_ui_display.cjs` before/after (must stay green) → extend (sourcing filters,
   worksheet export, live-pull status).
3. **Phase 2 — ListingForge.** Full service app per `01_listingforge.md`.
4. **Phase 3 — AdPilot.** Full service app per `02_adpilot.md`.
5. **Phase 4 — SocialPulse.** Full service app per `03_socialpulse.md`.
6. **Phase 5 — AutothinK surface.** Polish per `05_autothink_surface.md`; shell links to
   the AutothinK workspace.

## 7. OPERATING BOUNDARIES (unchanged constitution)

- **Autonomous Zone:** everything above — writing/running tests, commits, state updates.
- **Hard Stop:** any live outbound call (Costco/Unwrangle/OpenWebNinja, Amazon Ads API,
  Meta/Instagram APIs, Claude/image-gen APIs), reading/writing credential values, git
  push/remote ops, real-money actions. Code paths are built; execution is gated.