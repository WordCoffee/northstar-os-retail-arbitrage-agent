# ux-07 — workspace tab bar (rank 8)

Branch `ty/ux-07-tabs`, worktree `state/worktrees/ux-07`, based on `925d34cc`.
Scope: `northstar-os-ui/src/shell/**` plus `tests/e2e/workspace-tabs.spec.ts`. Nothing else changed;
no dependency added.

## What changed

| File | Change |
| --- | --- |
| `src/shell/tabRoutes.js` | NEW. Pure tab rules: which routes are tabs, open/close/re-point, sessionStorage parse/serialise, the Bojo summary. No React, no DOM. |
| `src/shell/useWorkspaceTabs.js` | NEW. The shell hook: open list from sessionStorage, active tab derived from the location, visited set, per-tab scroll memory, activate/close. |
| `src/shell/TabBar.jsx` | NEW. `role="tablist"` / `role="tab"`, `aria-selected`, roving tabindex, ArrowLeft/Right/Home/End + Delete, close buttons as siblings of the tabs. |
| `src/shell/WorkspacePanels.jsx` | NEW. Service id -> lazily imported page, rendered through `<Routes location={tab path}>` and a pinned `UNSAFE_LocationContext` so a hidden tab keeps its own URL. |
| `src/shell/tabs.css` | NEW. `wst-` classes only; tokens from `app.css`. |
| `src/shell/ShellLayout.jsx` | The tab strip between `TopNav` and `.body-layout`; the outlet renders the mounted tab panels plus `<Outlet/>` for non-workspace routes; `data-active-tab`, `data-active-tab-label`, `data-tab-summary` on the shell frame; the Bojo bridge. |
| `src/shell/WorkbenchShell.jsx` | Its private page map is replaced by `TAB_PANELS` from `WorkspacePanels.jsx` (one map, not two). |
| `src/shell/tabRoutes.test.js` | NEW. 12 tests, including pinning the tab routes to `App.jsx` and the panel map to `tabRoutes.js`. |
| `tests/e2e/workspace-tabs.spec.ts` | NEW. 5 browser tests (see below). |

## The tab-state mechanism, in one paragraph

The URL is the active tab: `tabForPath()` maps a pathname to one service (prefix on a segment
boundary, longest route wins) and the shell derives `activeId` from the location, so a tab click and
a browser Back produce the same state. The open list is the only state the hook owns; it is written
to `sessionStorage` (`ns-workspace-tabs`) on commit and re-read on mount. Every open workspace is
rendered by the shell itself, once, from `WorkspacePanels.jsx`, and stays mounted; the inactive ones
are `hidden`, not unmounted, so a page's `useState`, half-typed input and loaded data survive. A tab
mounts the first time it is opened and not before (same rule as the workbench). Because the shared
scroll container is `.main-content` (one element for all tabs), scroll offsets are recorded per tab
from the container's own `scroll` events and re-applied on activation — reading them at switch time
would read the clamp-to-zero caused by hiding the outgoing panel. Each panel is matched with
`<Routes location={tab path}>` under a pinned `UNSAFE_LocationContext`, so `useParams`,
`useLocation` and `useSearchParams` inside a hidden tab still answer for THAT tab and cannot be
re-pointed by the tab in front.

**Tabs are services, not history entries.** Navigating inside a workspace
(`/product-finder/B0…`) re-points its existing tab; it never opens a second tab for the same
service. `/home` is Bojo's home and is deliberately not a tab.

**Last-tab rule (written down):** closing a tab when others remain navigates to the tab on its RIGHT,
or the one on the left when it was last. Closing the LAST remaining tab empties the strip and
navigates to `/home`; the bar disappears. The router is therefore never left on a route whose tab
was just closed.

**Bojo:** the shell publishes one `workspace_tab` summary — tab id, service, label, path, search,
named query filters, the open tabs, tab count and the last recorded scroll offset — as
`data-tab-summary` on `[data-testid="shell-chrome"]`, as `globalThis.__northstarWorkspaceTab`, and as
a `northstar:workspace-tab` CustomEvent. It contains only what the shell can actually see.

## Commands and real output

```
cd northstar-os-ui
npm ci
  added 66 packages, and audited 67 packages in 3s

npm run build
  ✓ built in 1.35s          (0 errors; DesignStudio chunk 401.58 kB, unchanged)

npx --yes vitest run src/shell
  ✓ src/shell/shellRoutes.test.js (5 tests)
  ✓ src/shell/devBanner.test.js (4 tests)
  ✓ src/shell/tabRoutes.test.js (12 tests)
  Test Files  3 passed (3)
       Tests  21 passed (21)
```

Playwright, from the worktree root (the `tests/e2e` tree lives there, not under `northstar-os-ui`):

```
npx playwright test tests/e2e/shell-chrome.spec.ts "tests/e2e/*tab*.spec.ts" --project=chromium-desktop
  Running 6 tests using 1 worker
  6 passed (1.8m)
```

That is the literal command, and on this machine's PowerShell the quoted glob is passed through
verbatim and matches nothing, so it runs `shell-chrome.spec.ts` only (6 tests). The files the glob
was meant to cover were then named explicitly:

```
npx playwright test tests/e2e/shell-chrome.spec.ts tests/e2e/workspace-tabs.spec.ts --project=chromium-desktop
  11 passed (1.9m)          # shell-chrome 6 + workspace-tabs 5

npx playwright test tests/e2e/shell-chrome.spec.ts tests/e2e/workspace-tabs.spec.ts tests/e2e/chat_composer_stability.spec.ts --project=chromium-desktop
  1 failed
  11 passed (2.7m)
```

The one failure is `chat_composer_stability.spec.ts` — `TimeoutError: locator.waitFor: Timeout
45000ms exceeded, waiting for getByTestId('chat-input')` on `/ui/design-studio`. It is **not caused
by this lane**: I stashed every change (`git stash push -u -- northstar-os-ui/src/shell
tests/e2e/workspace-tabs.spec.ts`), ran that one spec on the untouched base commit (`925d34cc`), and
got the identical timeout (`1 failed`), then restored the work. `DesignStudio.jsx` renders no
`ChatSurface`; only `MasterBrainShell` and `WorkbenchShell` do, so the spec's expectation is stale.
Left untouched: it is outside this lane's write path.

The 5 tab tests cover: one selected tab per workspace route with the ux-06 frame intact; a typed ASIN
and a 220 px scroll offset surviving a round trip to another tab (and no request replay); keyboard
ArrowLeft/ArrowRight switching with `aria-selected` and focus following the panel; closing the active
tab landing on a survivor and closing the last tab landing on `/home` with an empty strip; and the
Bojo summary being present, correct and updating on a switch.

## What I did not do

- **The last hop into Bojo's turn is outside this write path.** `src/chat/ChatSurface.jsx` builds the
  turn body and forwards only `workspaceRef.current.summary.canvas` (line 624). The shell now
  publishes the tab summary on the workspace context boundary and on `globalThis`, but making it
  reach the model needs one added line in that file (e.g. `workspace: workspaceRef.current?.summary`)
  and a matching field in `Northstar_backend/chat_router.py`'s turn body. Both are outside
  `src/shell/**`; I did not widen the diff. The published object is shaped for exactly that change.
- No new route, no backend endpoint, no dependency. No tabs for non-workspace routes (admin,
  customer rooms, `/workbench`, `/home`): they render through `<Outlet/>` exactly as before.
- No tab reordering, no pinning, no "reopen closed tab", no cross-reload component state (only the
  open list persists; a reloaded tab mounts fresh, which is what a browser reload does).
- Hidden tabs keep running their own effects. That is inherent to keeping them mounted; nothing in
  the shell pauses them.
- The tab route table is a second copy of the tabbable subset of `App.jsx`. It is pinned by
  `tabRoutes.test.js` (every pattern must be a real `<Route>`, every id a real interactive service,
  exactly one panel per id), because `App.jsx` is outside the write path and exports no route table.
