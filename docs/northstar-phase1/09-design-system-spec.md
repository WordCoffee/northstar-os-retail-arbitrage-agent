# 09 — Design System Specification

Evidence states: INFERRED (I) from Phase 0 `11` and owner directive. This is the target design direction; wireframes/implementation follow in Phase 1B.

## 1. Direction

An **operating system for Amazon sellers** — professional, data-dense, understandable, operationally useful. NOT a gaming interface or demo dashboard.

- Keep: dark operational aesthetic; restrained cyan as action/accent; high information density; clear service identity.
- Correct (from Phase 0 `11`): tiny text, excessive glow, low contrast, empty dead space, decorative controls, duplicate navigation, persistent right rail, weak hierarchy, ambiguous terminology, fixture-like status cards, non-clickable lookalikes.

## 2. Color tokens

| Token | Value (proposed) | Use |
|---|---|---|
| `--bg-canvas` | `#0a0e16` | page canvas (obsidian, less purple) |
| `--bg-surface` | `#111826` | cards/panels |
| `--bg-elevated` | `#182236` | popovers/modals |
| `--border-subtle` | `#232e44` | borders |
| `--border-strong` | `#33415e` | active borders |
| `--text-hi` | `#eef2f8` | primary text |
| `--text-mid` | `#a5b4cc` | secondary |
| `--text-low` | `#6b7a99` | muted |
| `--accent-cyan` | `#00c8ff` | actions/links (restrained) |
| `--accent-cyan-weak` | `rgba(0,200,255,.12)` | hover fills |
| `--success` | `#2fd07a` | positive |
| `--warning` | `#e6b64c` | caution |
| `--danger` | `#e5586b` | negative |
| `--info` | `#5b8cff` | informational |

- Provenance badges: reuse a small palette (live=green, cached=amber, imported=blue, estimated=purple, mocked=gray, stale=dark amber, unavailable=outline) — consistent across all services.

## 3. Typography

- Body: Inter 13.5–14px (up from ~11–12 in SPA/desk). Data/mono: JetBrains Mono 12–12.5px.
- Scale: 12 / 13 / 14 / 15 / 16 / 18 / 22 / 28 px. Headings 15/18/22/28.
- Line-height 1.45–1.6; min contrast ≥ 4.5:1 for text (WCAG AA).

## 4. Spacing + grid

- 4px base scale; section 24px; card padding 16–20px; gutter 16px.
- 12-col grid; breakpoints 640 / 960 / 1280 / 1600.
- Density: default `compact` mode with density toggle (more rows, tighter padding) — high density is a feature.

## 5. Navigation

- Left sidebar (collapsible to rail) = primary nav; top bar = global search, environment indicator, account.
- NO persistent right rail — Pinned becomes a collapsible drawer (Phase 0 finding).
- Command palette (Ctrl+K) for deep actions.
- Breadcrumbs in detail views.

## 6. Tables

- Dense, sortable, filterable, virtualized for large sets; sticky header; row hover; column menus; export actions.
- Status pills + provenance badges inline; never decorative (always data-backed).

## 7. Cards / charts / forms

- Cards: minimal shadow, 1px border, hover reveal of primary action. No glow-by-default.
- Charts: area/line for time series (price/rank/ACoS), bars for comparisons, sparklines in tables. Axis labels legible (≥11px).
- Forms: labeled, validation inline, focus ring (2px accent), disabled/loading states explicit.

## 8. Drawers / modals / toasts / palette

- Drawers: right-drawer for detail/pinned; dismiss + escape.
- Modals: confirmation modals for consequential actions; approval modals show cost estimate + diff.
- Toasts: role=status, auto-dismiss except errors.
- Command palette: role=dialog, keyboard-first.

## 9. State patterns

| State | Pattern |
|---|---|
| Loading | skeleton rows (not spinners everywhere) |
| Empty | actionable empty state (primary CTA) |
| Partial data | show known fields; mark unknown explicitly (null-not-zero) |
| Stale data | amber "stale as of <t>" banner + refresh action |
| Provider failure | error banner + retry (bounded) + "last success <t>" |
| Permission denied | clear "requires <role>/approval" state |
| Success | confirmation toast + next-step hint |

## 10. Provenance + confidence indicators

- Every data-dense row can reveal provenance (source, captured_at, confidence, verification_state, staleness) via hover/tooltip or a details column.
- Confidence shown as a labeled chip (high/medium/low/unknown), never a bare percentage.

## 11. WCAG / keyboard requirements

- All interactive elements keyboard-focusable; visible focus ring; skip-to-content; aria labels; dialog focus traps; reduced-motion support; contrast AA.
- Touch targets ≥ 40px on mobile.

## 12. What this resolves

- Phase 0 `11` issues (small text, glow, contrast, dead space, persistent rail, decorative controls, duplicate nav, ambiguous terms).
- Owner directive design corrections verbatim.
