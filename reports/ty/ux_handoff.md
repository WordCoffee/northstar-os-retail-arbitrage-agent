# UX rebuild — handoff

**State:** U0–U3 done and verified on both targets. **U4 (theme system + glass kit) is the next unit.**
Tag `ns-ux-U3` = `b3cad214`. Dev servers were started through `scripts/dev-start.ps1` after
`tailscale serve status` returned **No serve config**.

## Done

- **U0** — `ns-ux-baseline` at `a2d12f5e`; baselines in `ux_queue.json`.
- **U1** — `src/lib/shellMode.js`: ids stay `simple`/`advanced`, display names **Northstar** /
  **Advanced view**, legacy values migrate. `AGENTS.md` appended (647 chars).
- **U2** — `src/data/serviceRegistry.js` (34 services) + `src/lib/serviceGate.js`.
- **U3** — `WorkbenchShell.jsx` + `WorkspaceTabs.jsx` + `workbench.css`, route `/workbench`,
  top-nav entry, `tests/e2e/workbench.spec.ts`.

## Evidence at U3 close

| Check | Result |
|---|---|
| `npm run test:ui` | **94 passed, 0 failed** |
| `npm run build` | **✓ built in 1.36s** |
| `npx playwright test tests/e2e/workbench.spec.ts --project=chromium-desktop` | **5 passed (8.7s)** |
| `… --project=chromium-mobile` | **5 passed (10.1s)** |
| desktop stress `--repeat-each 3` | **15 passed (14.4s)** |
| mobile stress `--repeat-each 2` | **10 passed (28.3s)** |

The 2026-11-02 failures were **not** an unreachable nav entry. The click on `ns-workbench-open`
already worked at 390 px; the test then asserted the desktop-only `bojo-dock`. Three real defects
were fixed underneath it:

1. `tabsOpen` was `pickerOpen` — one flag drove the tab strip *and* the service picker. On a phone
   the tab strip and its close buttons were `display:none`, so tab/close taps waited 2 minutes.
2. The 390 px top nav overflowed by ~130 px (the four-button display-scale control) and pushed the
   right-hand actions past the clipped edge. The scale control is now hidden at ≤640 px.
3. `AssetDashboard` fetched without the dev identity shim, so it sat in the anonymous 30/min bucket;
   HTTP 429 was swallowed and shown as "no assets found". It now sends `X-User-Id`, honours
   `Retry-After`, and retries behind a 4 s abort ceiling.

Every control the spec taps is hit-tested with `elementFromPoint` first (`ns-workbench-open`,
`wb-add`, `wb-open-*`, `wb-tab-*`, `wb-close-*`). Tabs still stay **mounted when hidden**.

## Next: U4 (theme system + glass kit)

Per the work order: per-service theme tokens as CSS variables, a glass kit (panel, tab, button,
input, tool rail) that reads the tokens, and a service-switch animation hook. Pass = automated
contrast test over every theme at the worst-case background colour + unit snapshots per service.

Practical notes:

- `workbench.css` already defines `--wb-*` placeholders. Move them to per-service token blocks and
  keep the existing class names — U6–U12 layer scenes on top of them.
- The `serviceRegistry.js` entries already carry `themeTokens`; read them rather than inventing a
  second palette source.
- `html[data-shell-mode="simple"]` and the `ns-ux-tabs` storage key are load-bearing. Do not rename.

## Rules that must not slip

- `simple`/`advanced` ids are load-bearing (`html[data-shell-mode="simple"]`, `ns-shell-mode`).
- `AGENTS.md` is append-only.
- Tabs must stay mounted when hidden; that is the state-preservation contract.
- `.wb-shell`/`.wb-tabbar` z-index layering exists because the fixed cosmic canvas covers clicks.
- Dev servers: `scripts/dev-start.ps1` only. `tailscale serve status` must say `No serve config`
  before launching; if it does not, write the exact output to `needs_you.md` and stop.
- `smoke.spec.ts` (2 failures) is stale by design and is fixed in U14 — do not chase it now.
