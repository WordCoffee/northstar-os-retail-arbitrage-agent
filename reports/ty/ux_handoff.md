# UX rebuild — handoff

**State:** U0 complete. U1 next.

## Done

- **U0** — `ns-ux-baseline` tagged at `a2d12f5e`; baseline recorded in `ux_queue.json` from this
  session's runs (backend 5763 passed / 30 failed; e2e 41 passed / 2 failed / 1 did not run, both
  failures pre-existing by stash attribution). Queue, decisions, needs-you and this file created.

## Blocker that shapes the session

`scripts/dev-start.ps1` is **refused by the safety gate** — `tailscale serve` proxies
`127.0.0.1:8000` on the tailnet, so the dev login bypass would be shared. Queued in
`needs_you.md`. Consequence: **no dev server, no backend suite, no Playwright runs** until it is
closed. UI units are built and unit-tested, then marked `verification_pending`.

Starting a server by another route (launch_alpha, bare uvicorn) would sidestep the gate that
exists for this exact condition. Not doing that.

## Next session must know

- Read `reports/ty/ux_queue.json` first; continue at the first unit not `done`/`quarantined`.
- The work order is saved at `reports/ty/ux_work_order.md`.
- The repo already has: `DesignStudio.jsx` with a section picker and an Asset Dashboard,
  `ModeContext` (`ns-shell-mode`), `SHELL_MODES = ['simple','advanced']`, and a guard
  `SIMPLE_KEEP_ADVANCED` in `App.jsx` that keeps `/design-studio`, `/account`, `/legal` as real
  pages in the default mode.
- Playwright: two projects (`chromium-desktop`, `chromium-mobile` → WebKit/iPhone 12). WebKit is
  installed. Base URL `http://127.0.0.1:8101`, routes live under `/ui/`.
- `test-results/` and `playwright-report/` are gitignored.
- Model: DeepSeek V4.1 Flash this session. Every `[MAX-GRADE]` unit needs the extra self-review
  pass and the U14 independent verifier.

## Open hazards

- Killing the old `uvicorn`/`vite` processes also killed a `powershell -NoExit` window; use
  `Get-CimInstance Win32_Process` filtered by CommandLine, as the order says.
- `report/ty/ux_queue.json` token numbers are estimates (chars/4), labelled as such.
