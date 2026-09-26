# 11 — UX / Design-System Audit

Evidence states: STATICALLY_CONFIRMED (S) unless noted. This is an inventory + issue list, NOT a redesign.

## 1. Three design systems exist

| System | Source | Tokens | Status |
|---|---|---|---|
| Analyst's Desk (legacy primary) | `static/northstar-os/` | `css/tokens.css`, `tokens.v2.css`, `chrome.v2.css` + 10 more | Functional SPA shell, fixtures |
| SIGNAL (React/Vite SPA) | `northstar-os-ui/` | `src/styles/tokens.css` (obsidian #070b14, cyan #00f0ff, coral #ff6b6b, glassmorphism), `app.css` | Experimental parallel surface |
| Workbench | `static/index.html` | inline + `shared/design-tokens.json/.css` (sync-guarded by test_ui_display.cjs:3018-3030) | Legacy power tool |

`shared/design-tokens.json/.css` is the only token file with a drift guard (a contract test fails if the embedded CSS differs).

## 2. Design-token inventory (SIGNAL SPA, representative)

- Colors: `--obsidian:#070b14`, `--cyan:#00f0ff`, `--coral:#ff6b6b`, `--lime:#39ff14`, `--violet:#a855f7`, glass borders `rgba(148,197,255,.14)` (tokens.css).
- Typography: Inter (body), JetBrains Mono (data), Google Fonts (index.html).
- Glassmorphism: `backdrop-filter: blur(18px)` cards, obsidian gradient canvas.
- Breakpoints: 920px / 1100px / 860px (app.css); Analyst's Desk has its own responsive.css.

## 3. Component inventory (SIGNAL SPA)

Cards (`.card`), metric tiles, tables, forms (`.field`), buttons (`.btn` + primary/ghost), badges (demo/gated/live/ok), icons (inline SVG set `Icon.jsx`), nav groups/items, header, sidebar, right rail (pinned), action dock, toasts, paperclip assistant, gate rows, status pills, sliders, progress bars, switches.

## 4. Known UX issues (from source; see `13` for risk register)

| Issue | Evidence | Severity |
|---|---|---|
| Persistent Pinned rail is globally hard-coded in the SIGNAL SPA | `App.jsx` always renders `<RightRail/>`; `RightRail.jsx` has no collapse control | Medium (wasted space) |
| Same Pinned/board concept duplicated in Analyst's Desk | `static/northstar-os/index.html:830-834` | Low |
| Three nav surfaces overlap (sidebar groups + action dock + quick actions) | Sidebar/Dock/Hub Quick Actions | Low/Medium (duplicate nav) |
| Neon/glow can be excessive | `text-glow`, `shadow-glow`, pulse animations used broadly | Low (aesthetic) |
| Text density vs spacing imbalance | large padding on `.card` (16-18px) for data-dense tables | Low |
| Skeleton views (Watch/Rank/Rival) present schema placeholders as content | `index.html:734-797` | High (misleading) |
| `0.00` costs presented as numbers | Prospector table (see `05`) | High (data integrity, not just UX) |
| "live" badges on cache-first pages | SPA Hub/Prospector badges | High (misleading) |
| No keyboard-first nav test | no a11y tests; SPA uses aria-labels | Unknown |

## 5. Accessibility snapshot

| Surface | Strength | Gaps (inferred, not tested) |
|---|---|---|
| Analyst's Desk | aria-labels, aria-current/hidden managed, role=dialog/aria-modal on palette+onboarding, aria-live toasts, prefers-reduced-motion | no a11y test suite |
| SIGNAL SPA | aria-label on inputs/buttons, aria-expanded/aria-current in Sidebar | no focus-trap for toasts, no keyboard nav for dock/sidebar groups beyond native buttons |
| Workbench | large monolith, aria unknown | not tested |

## 6. No onboarding/tour infrastructure (except Analyst's Desk)

- Analyst's Desk has a first-entry onboarding modal + dots (`index.html:852-888`) and `prefers-reduced-motion` (per `00_STATE.json`).
- No per-service tour, no skip/don't-show-again persistence beyond session, no replay from Help, no role-based tours, no completion analytics.
- Recommendation: the tour/help system should be a Phase-1 platform feature (see `14`), with per-user/per-service completion stored in the DB.

## 7. Duplicate navigation / ambiguous labels

- Duplicate: sidebar groups vs action dock vs Quick Actions cards.
- Ambiguous: "Balance" and "Available" in Ledger (credits) — currently same number because nothing consumes credits (see `05`).
- Decorative controls: some badges/status pills are presentation-only (see `12` for "Authorization Posture").

## 8. Counting methods

- Component/token inventory from source reads (S). No screenshots, no visual tests executed.
