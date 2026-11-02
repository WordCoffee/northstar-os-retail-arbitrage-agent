# UX rebuild — handoff

**State:** U0 and U1 complete. U2 next.

## Done

- **U0** — `ns-ux-baseline` tagged at `a2d12f5e`; baselines recorded in `ux_queue.json` from this
  session's runs (backend 5763/30; e2e 41/2/1, both failures pre-existing by stash attribution;
  UI unit 82/0). Queue, decisions, needs-you and this file created.
- **U1** — Naming rule landed. `src/lib/shellMode.js` owns the vocabulary: internal ids stay
  `simple`/`advanced`, display names are **Northstar** / **Advanced view**, and `normaliseMode`
  migrates legacy stored values (`northstar`, `standard`, `default`, `advanced view`, `autothink`).
  `ModeContext` reads through it; the visible strings in `MasterBrainShell` and `ShellModeToggle`
  now say Northstar; comments in the touched files were swept; `AGENTS.md` gained the naming rule
  as a 647-char append (no rewrite). 7 new unit tests in `src/lib/shellMode.test.js`; suite 82/82;
  build green.

## Blocker that shapes the session

`scripts/dev-start.ps1` is **refused by the safety gate** — `tailscale serve` proxies
`127.0.0.1:8000` on the tailnet, so the dev login bypass would be shared. Queued in
`needs_you.md #1`. Consequence: **no dev server, no backend suite, no Playwright** until it is
closed. UI units are code+unit-tested and marked `done` with a `verification` note; nothing is
claimed VERIFIED without a browser run.

## Next session must know

- Read `reports/ty/ux_queue.json` first; continue at U2 (registry), then U3 (shell).
- Work order: `reports/ty/ux_work_order.md`.
- `ModeContext` now imports from `src/lib/shellMode.js`. Do not rename the internal ids.
- `SIMPLE_KEEP_ADVANCED` in `App.jsx` controls which paths keep their real page in Northstar;
  `/design-studio` is in it (added earlier today so the studio is reachable at free tier).
- Playwright: `chromium-desktop` + `chromium-mobile` (WebKit/iPhone 12, binary installed).
  Base URL `http://127.0.0.1:8101`, routes under `/ui/`.
- UI unit tests: `cd northstar-os-ui && npm run test:ui` (node --test over `src/lib/*.test.js`).

## Open hazards

- Killing old `uvicorn`/`vite` also killed a `powershell -NoExit` window; use
  `Get-CimInstance Win32_Process` filtered by CommandLine.
- Token numbers are estimates (chars/4), labelled as such.
- `AGENTS.md` must stay append-only.
