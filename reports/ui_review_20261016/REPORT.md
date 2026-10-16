# UI design review + pass v2 — 2026-10-16

Operator ask: substantial visual updates across the product, hyper-focused on
the content/data-generating services (ListingForge, Design Studio, AdPilot,
SocialPulse, AutothinK), "design the UI to be smart". Screenshots taken with a
local-only CDP tool (`tools/_design_shots.mjs` — raw Chrome DevTools Protocol,
localhost only, no Playwright, session cookie injected via CDP; the browser
never sees credentials). Shots live in `reports/ui_review_20261016/shots/`
(15 pages, 1600×1000).

## The big find (fixed first): the UI was being rate-limited into looking broken

The alpha gate fix earlier made cookie sessions first-class, but the **rate
limiter still gave every cookie user the anonymous 30 req/min bucket** — a
page load fires 10–30 calls, so normal browsing tripped 429s: panels sat on
UNKNOWN, the engine banner said "not connected" while the API said armed, and
deep links flashed the sign-in guard (exactly what the review screenshots
caught). `rate_limiter.py` now resolves the cookie session like the gate does:
owner/platform-admin → 300/min, member → 120/min, anonymous stays 30/min.
Verified: 60/60 rapid cookie calls → 200s, zero 429s (previously capped at 30).
Also: the studio's engine probe now keeps its last known state instead of
downgrading to "not connected" on a transient blip.

## What the pass changed (all shipped in this commit series)

| Area | Before → After |
|---|---|
| **Suite rail** | Duplicate "NorthstarOS" brand block repeated the topbar; every row carried a loud status pill (LOCAL/PARTIAL/CONCEPT…). Now: a single "WORKSPACE · Platform Admin" context block, and status **dots** (green=local, amber=partial, red=LLM-gated, gray=internal) with the full readiness sentence on hover. The rail reads like navigation, not a status dashboard. |
| **Studio evidence** (`MasterBrainPanel`, on 10 pages) | A tall card of four verbose UNKNOWN paragraphs above the fold on every service page. Now: a compact four-cell strip — one line each, dot + state ("UNKNOWN — no file imported"), honest summary line, and a **Details** button that expands the full sources/freshness/limits/rows. Saves ~200 px on every service page; ListingForge/AdPilot tables are now visible without scrolling. |
| **Design Studio header** | The page title rendered twice (outer page + inner studio). Now: one page header + a slim toolbar row (Simple/Advanced · context line · Master canvas / Export Bundle / New Brief). The workspace notice was updated to the armed-engine truth and tightened. |
| **Tables** | Data-first styling: micro uppercase headers, tabular numbers, right-aligned numerics, row hover, calmer dividers — applied to Campaign Health, Listings, Session history, etc. |
| **Cards & notices** | Softer borders/shadows, warm paper surface, card-head dividers, compact notice variant, softer active filter-chip state. |
| **Video tab right panel** | Still showed the stale "PROVIDER REQUIRED — not connected" card while the tab body showed the armed banner. Now mirrors the live engine state. |

## Evidence

- `shots/02-listingforge.png` — new rail + evidence strip + listings table + "Studio snapshot" numbers.
- `shots/06-adpilot.png` — strip + Campaign Health table + Budget Watch.
- `shots/03-design-studio.png` — single header + toolbar.
- `shots/05-video.png` — armed video banner + provider card fix.
- Full set (15 pages) re-shot after the pass; 04/05/06/07/08/09… all render with real content.

## Suggested next design moves (not done yet — honest backlog)

1. **ListingForge Editor tab**: give the listing builder a two-pane layout —
   form left, live "listing health" right (score, keyword coverage, forbidden
   words) with the local brain exposed as one-click actions (title/bullets).
2. **Command Center hero**: add a KPI tile strip (catalog coverage, approvals,
   runs) from the reads it already performs.
3. **AdPilot numeric tones**: color ACoS/failed metrics inline (31.2% critical row).
4. **SocialPulse calendar**: replace the day-name list with a real week grid.
5. **AutothinK room**: embed the (now saved, scrollable) chat directly in the
   room's Composer tab instead of linking out to the galaxy UI.
6. Topbar cleanup: fold the floating "?" help affordance into the bell menu.

## Screenshot tool

`tools/_design_shots.mjs` — run with `NS_EMAIL`/`NS_PW` env vars set; optional
`NS_ONLY=a,b` to re-shoot a subset. Pacing + verify-and-retry handles the
sign-in flash race. Local-only by construction.
