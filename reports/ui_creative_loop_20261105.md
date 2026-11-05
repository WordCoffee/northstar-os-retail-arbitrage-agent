# Creative Services + Frontend UI/UX — continuous-improvement loop

**Date:** 2026-11-05 · **Scope:** three self-directed cycles over Design Studio, the asset
dashboard and the Tys operator surface. No Amazon, spend, credential read or cloud inference.

---

## Cycle 1 — Live Tys Assistant operator panel

`TysOpsPanel.jsx` (new) polls `/api/admin/tys/state`, `/tasks` and `/memory/stats` every 5 s and
shows, read-only:

* queue total and per-status counts;
* lane availability (inspect / coding / graphics / browser / creative);
* orchestrator model and identity;
* semantic-memory state, chunks, tokens, live facts and fallback reason;
* the last eight work orders with status, cursor/step progress, next action, owner, stop reason and
  up to three blockers.

The panel is mounted on `/admin` and `/improvement`. `/improvement` was added to
`SIMPLE_KEEP_ADVANCED`: in Northstar it previously rendered the chat shell instead of the room, so
the operator's own automation state was unreachable.

**Live verification (Playwright, localhost):** panel rendered at `127.0.0.1:8101/ui/improvement`;
`/state`, `/tasks` and `/memory/stats` all returned **200**; the panel showed queue 19, semantic
memory and three tasks with progress/blockers. Screenshot: `screenshots/tys_ops_panel.png`.

## Cycle 2 — Studio export and guardrail polish

* **Asset dashboard:** per-file sizes plus total package size; `download json` on every package card;
  manifest panel gained **Copy JSON** and **Download**; no-match/empty states remain explicit.
* **Video & UGC:** visible **human-feature guardrail** rule with the owner's exact warning and the
  audited `human_features_ack` override.
* **Design Studio:** section buttons expose `aria-pressed` and explicit `type="button"`; the active
  section remains visually primary.
* **Tys live badge:** a pulsing dot with `prefers-reduced-motion` support (micro-animation, no motion
  for users who ask for none).

## Cycle 3 — Asset-dashboard filter

Package filter by **run id, kind or date** with an explicit no-match message. This makes a
commercial-size package list navigable without scrolling through every run.

---

## Verification

| Run | Result |
|---|---|
| `npm run build` | 0 errors (1.55–1.76 s) |
| `npm test` | UI + contrast + Galactic verifier pass |
| `test_frontend_gate.py` | **25 passed** |
| Live panel | Playwright: three admin endpoints 200; queue, memory and task rows rendered |
| Backend baseline | untouched; last full run **6105 passed / 0 failed** |

## Commits

| Commit | Change |
|---|---|
| `27d1fb63` | live Tys panel + `/improvement` reachable in Northstar |
| `5691846d` | manifest sizes/download/copy, guardrail rule, section a11y |
| `9c89eb81` | package filter |
| `c5e5658d`, `89aed46c` | state fragments recorded |

State fragments: `20261105_ui_tys_panel`, `20261105_studio_polish`,
`20261105_dashboard_filter` (registry now 102 keys).

## What is deliberately not changed

* No run/cancel/submit control in the Tys panel: it is an operator **view**, and mutations stay on
  the existing admin API with its own gates.
* Video generation remains unarmed in the UI; the guardrail is explained but no render button was
  added. The backend endpoint and the audit remain the enforcement point.
* No new route was created; the route-count contract and the 25-test frontend gate stay green.
* Heavy lanes (B2/B3/B4/A14B) remain as recorded in `docs/HEAVY_LANES.md`; this loop did not arm them.

## Next queue (not started)

1. Playwright visual regression for the Tys panel and the asset dashboard at 1280/768/390 px.
2. Poll backoff and visibility-aware pause for the Tys panel (stop polling when the tab is hidden).
3. Manifest hash verification display when a package manifest carries `sha256` entries.
4. Design Studio section rail: keyboard arrow navigation and a compact mobile rail.
