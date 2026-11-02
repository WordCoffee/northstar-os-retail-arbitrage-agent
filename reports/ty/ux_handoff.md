# UX rebuild — handoff

**State:** U0–U2 done. **U3 built and desktop-verified; the iPhone/WebKit profile still fails the
nav entry and tab flows, so U3 is `verification_pending`, not done.** U4+ wait behind it.

## Done

- **U0** — `ns-ux-baseline` at `a2d12f5e`; baselines in `ux_queue.json`.
- **U1** — `src/lib/shellMode.js`: ids stay `simple`/`advanced`, display names **Northstar** /
  **Advanced view**, legacy values migrate. `AGENTS.md` appended (647 chars).
- **U2** — `src/data/serviceRegistry.js` (34 services) + `src/lib/serviceGate.js`.
- **U3 (pending mobile)** — `src/shell/WorkbenchShell.jsx` + `WorkspaceTabs.jsx` + `workbench.css`,
  route `/workbench`, top-nav entry, `tests/e2e/workbench.spec.ts`.

## Evidence at handoff

| Check | Result |
|---|---|
| `npm run test:ui` | **94 passed, 0 failed** |
| `npm run build` | **✓ built in 1.34s** |
| `npx playwright test tests/e2e/workbench.spec.ts --project=chromium-desktop` | **5 passed (5.2s)** |
| `… --project=chromium-mobile` | **2 passed, 3 failed (4.3m)** |

Mobile failures by name: *the workbench opens from the top nav and shows the shell*; *a second
service opens as a tab and the first keeps its state*; *closing a tab never leaves the shell empty*.

## Next session: finish U3 on the phone profile

Likely causes, in order of probability:

1. The top-nav **Workbench** button is not reachable at 390 px (the phone chrome hides it), so both
   the nav test and everything downstream fail at the first step. Fix by exposing the entry in the
   mobile nav/tools sheet, or by driving the route directly in the mobile spec *after* the entry is
   proven separately.
2. The tab picker (`wb-picker`) may sit under the bottom sheet / mobile nav at 390 px; check
   `elementFromPoint` on `wb-open-*` before assuming the click works.
3. WebKit lacks something the shell assumes (`matchMedia` is guarded; `sessionStorage` is wrapped).

Once mobile is green: tag `ns-ux-U3` **done**, then start U4 (theme system + glass kit).

## Rules that must not slip

- `simple`/`advanced` ids are load-bearing (`html[data-shell-mode="simple"]`, `ns-shell-mode`).
- `AGENTS.md` append-only.
- Tabs must stay mounted when hidden; that is the state-preservation contract.
- `.wb-shell`/`.wb-tabbar` z-index layering exists because the fixed cosmic canvas covers clicks.
- Dev servers: `scripts/dev-start.ps1` only (gate is clear now; the operator exited Tailscale).

## Server state at handoff

dev-start.ps1's wrapper process exited (its PowerShell host ended) but the two children it spawned are still listening: backend 127.0.0.1:8000 and UI 127.0.0.1:8101. `dev-start.pids` may be stale; verify with `Get-NetTCPConnection` before starting another stack.
