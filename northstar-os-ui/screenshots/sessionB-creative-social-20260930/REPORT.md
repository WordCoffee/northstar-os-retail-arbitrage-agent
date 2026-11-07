# Session B — Creative Studio + SocialPulse screenshot capture

- Branch: `feature/creative-social-local`
- Session B commits present (all ancestor of HEAD): `05a4ea2`, `a5936ce`, `124d564`, `e5e7b26`
- Captured: 2026-09-30
- Folder: `northstar-os-ui/screenshots/sessionB-creative-social-20260930/` (new, untracked; NOT staged/committed)

## Server command used
Documented path in `docs/LOCAL_RUNBOOK.md` §UI is `npm --cwd northstar-os-ui run dev`.
`--cwd` is not a valid npm flag (E404), so the equivalent documented script was run
from the UI package directory:

```
cd northstar-os-ui && npm run dev     # -> vite --port 8101 --strictPort
```

Ready in ~1.1s at `http://localhost:8101/ui/`. Backend (:8000) was not running;
the app's own local dev identity shim was used via the repo harness pattern
(`verify-smoke.cjs`): set `ns-dev-session` in localStorage, `window.__NORTHSTAR_LOCAL_DEV__ = true`,
and stub the foundation `fetch` routes (`/ui-mode`, `/me`, `/environment`, `/preview/active`).
No room data was fabricated — every room populated itself from its own built-in
browser-persisted sample records (`ns-creative-*`, `ns-social-*`).

## Captures (all completed)

| # | File | Viewport | Dimension | Route (path) | Tab / state captured |
|---|------|----------|-----------|--------------|----------------------|
| 1 | creative-studio-desktop-primary.png | 1440×900 | 1440×900 | `/ui/creative-studio` | Briefs tab — seeded work briefs + Active Brief |
| 2 | creative-studio-desktop-populated-workflow.png | 1440×900 | 1440×1322 | `/ui/creative-studio?view=variants` | Variants & History — 5 local variant records + history log |
| 3 | creative-studio-desktop-provider-required.png | 1440×900 | 1440×1131 | `/ui/creative-studio?view=composer` | Image Composer — "PROVIDER REQUIRED" boundary, readiness 0/4, empty preview |
| 4 | creative-studio-mobile-primary.png | 390×844 @2x | 780×2422 | `/ui/creative-studio` | Briefs tab (mobile shell) |
| 5 | socialpulse-desktop-calendar-or-planning.png | 1440×900 | 1440×1002 | `/ui/socialpulse` | Calendar — September 2026 planning grid + snapshot |
| 6 | socialpulse-desktop-queue.png | 1440×900 | 1440×900 | `/ui/socialpulse?view=queue` | Workflow — Board (Drafts→Scheduled) |
| 7 | socialpulse-desktop-composer-or-approvals.png | 1440×900 | 1440×1261 | `/ui/socialpulse?view=composer` | Composer — Draft Post + Platform Preview + AI Copilot |
| 8 | socialpulse-desktop-provider-required.png | 1440×900 | 1440×900 | `/ui/socialpulse?view=analytics` | Analytics — UNKNOWN provider metrics + "provider not connected" |
| 9 | socialpulse-mobile-primary.png | 390×844 @2x | 780×3524 | `/ui/socialpulse` | Calendar (mobile shell) |

All nine are non-empty valid PNGs (IHDR-verified) with distinct content hashes.

## Required-capture status
- Completed as specified: 1, 2, 3, 4, 5, 6, 7, 9
- Substituted (no dedicated "provider-required" panel in SocialPulse): #8 uses the
  Analytics view — the room's honest provider-required surface (Reach/Engagement/
  Followers/Posts-published all read `UNKNOWN`, "provider not connected"). SocialPulse
  has no `ProviderBoundary` component; its composer carries the same boundary as a
  DataNotice.
- Blocked: none.

## Honesty notes
- Creative Studio Production Queue starts empty (no requests) — not captured as a
  "populated" view because no request exists without operator action. The
  populated-workflow capture uses Variants & History instead.
- SocialPulse calendar shows only the one seeded post with a manual reminder string.
- No generation, publishing, analytics, or provider response was fabricated.

## Git
`git status --short` shows the new folder as untracked only; no tracked source or
docs file was changed by this task. Pre-existing modifications to other files were
present before capture and were not touched.
