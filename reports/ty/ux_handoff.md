# UX rebuild — handoff

**State:** U0–U2 complete (unit-verified). **U3 blocked** by the dev-server safety gate; U4–U15 not
started. Final report for this run: `reports/ty/ux_20261102.md`.

## Done

- **U0** — `ns-ux-baseline` at `a2d12f5e`; baselines in `ux_queue.json` (backend 5763/30 at 10:59;
  e2e 41/2/1 at 11:20 with both failures pre-existing; UI unit 82/0).
- **U1** — `src/lib/shellMode.js` owns the vocabulary: ids stay `simple`/`advanced`, display names
  are **Northstar** / **Advanced view**, `normaliseMode` migrates `northstar|standard|default|
  advanced view|autothink`. ModeContext reads through it; visible strings in `MasterBrainShell` and
  `ShellModeToggle` say Northstar; comments swept; `AGENTS.md` appended (647 chars, append-only).
- **U2** — `src/data/serviceRegistry.js`: 34 services (nav catalogue + 10 routed rooms marked
  `source: 'app-route'`), each with `scene`, `theme`, `workspaceType`, `tools`, `entitlementKey`.
  `src/lib/serviceGate.js`: `canUseService` open in dev with a named reason, production branch
  (credit / explicit entitlement) exercisable via `enforceBilling`.

Tests at handoff: `cd northstar-os-ui && npm run test:ui` → **94 passed, 0 failed**; `npm run build`
→ **✓ built in 1.31s**.

## Blocker

`scripts/dev-start.ps1` exits 2 before starting anything:

```
REFUSING dev bypass - one or more exposure conditions detected:
 - tailscale funnel status is non-empty
 - tailscale serve config targets port 8000
```

`tailscale serve status` shows `https://msi.tail4b3dfd.ts.net → http://127.0.0.1:8000` (tailnet
only). Until that is closed, there is no backend, no e2e, and **no honest way to mark a UI unit
VERIFIED**. Queued in `needs_you.md #1`.

## Next session

1. Read `reports/ty/ux_queue.json`; next unit is **U3 (the shell, [MAX-GRADE])**.
2. If the tunnel is still live, do not start the stack another way — build what is unit-testable,
   keep marking `verification` honestly, and stop before claiming a screen works.
3. If it is closed: `scripts/dev-start.ps1` (background), then `npx playwright test
   --project=chromium-desktop` and `--project=chromium-mobile`.

## Files a next session must not break

- `src/lib/shellMode.js` — ids are load-bearing (`html[data-shell-mode="simple"]`, stored key).
- `SIMPLE_KEEP_ADVANCED` in `App.jsx` — keeps `/design-studio`, `/account`, `/legal` as real pages
  in Northstar.
- `src/data/serviceRegistry.js` — the single place to add a service.
- `AGENTS.md` — append-only.

## Hazards

- Kill servers with `Get-CimInstance Win32_Process` filtered by CommandLine; a `powershell -NoExit`
  window died with the old stack once.
- Playwright routes live under `/ui/`; wait for `**/ui/home`, not `/home`.
- Token figures are estimates (chars/4), not billing.
