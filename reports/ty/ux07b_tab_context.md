# ux-07b — the tab summary reaches the chat turn body

Branch `ty/ux-07b-tab-context` from `a5608616`. Unit: the open workspace tab must be
sent with each chat turn, using the summary ux-07 already publishes.

## What exists (read, not duplicated)

- `src/shell/tabRoutes.js:177` `tabSummary()` returns
  `{kind, tabId, serviceId, label, path, search, view, query, openTabs, tabCount, scrollTop, capturedAt}`.
- `src/shell/ShellLayout.jsx:108-114,175` publishes it three ways: `data-tab-summary` on the
  shell frame, `globalThis.__northstarWorkspaceTab`, and a `northstar:workspace-tab` event.
  `/home` and every non-workspace location publish `tabId: ''`.
- Nothing in `src/chat/` read it; `ChatSurface.jsx` sent only `canvas`.

## Body shape — before (ChatSurface.jsx:616-624)

```js
await streamTurn(sid, {
  content, think: thinking !== 'off', media, thinking, mode, style,
  attachments: attachments.map((a) => a.id),
  canvas: workspaceRef.current?.summary?.canvas || undefined,
}, onEvent)
```

No tab field at any point, so the model could not be told which page was open.

## Body shape — after

```js
await streamTurn(sid, buildTurnBody({
  content, think: thinking !== 'off', media, thinking, mode, style,
  attachments: attachments.map((a) => a.id),
  canvas: workspaceRef.current?.summary?.canvas || undefined,
  tab: readPublishedTab(),
}), onEvent)
```

`src/chat/turnBody.js` (new, pure, no React/DOM at import time):

- `tabContextFromSummary(summary)` → `{id, route, title, state}` or `undefined`.
  - `id` = `tabSummary.tabId` (the service id)
  - `route` = `path + search` (filters are part of the page being discussed)
  - `title` = `label`
  - `state` = `{view?, query?, openTabs?: [ids], tabCount?}` — no scroll offset, no
    `capturedAt`, no page content. The shell never had page content to send.
- `readPublishedTab(doc?, glob?)` → reads `[data-tab-summary]` first (written during the
  shell's render, so it is freshest after a tab switch), then
  `globalThis.__northstarWorkspaceTab`. Malformed JSON is ignored.
- `buildTurnBody({...})` adds `tab` only when present, and `canvas` only when present.

Absence contract: when no workspace tab is open (e.g. `/home`), `tabContextFromSummary`
returns `undefined`, `buildTurnBody` omits the key, and `JSON.stringify` therefore carries
no `tab` — not `null`, not `{}`. A test asserts `'tab' in wire === false`.

Example wire body on `/product-finder/B0ABCDEFGH?view=offers`:

```json
{"content":"what is this?","think":true,"media":"image","thinking":"standard",
 "mode":"standard","style":"balanced","attachments":[],
 "tab":{"id":"product-finder","route":"/product-finder/B0ABCDEFGH?view=offers",
        "title":"Product Finder",
        "state":{"view":"offers","query":{"view":"offers"},
                 "openTabs":["listings","product-finder"],"tabCount":2}}}
```

## Files changed

- `northstar-os-ui/src/chat/turnBody.js` — new: summary narrowing, published-summary read,
  turn-body builder.
- `northstar-os-ui/src/chat/ChatSurface.jsx` — import + send `tab: readPublishedTab()` via
  `buildTurnBody` (2 hunks, no other behaviour touched).
- `northstar-os-ui/src/chat/turnBody.test.js` — new: 5 tests (below).
- `reports/ty/ux07b_tab_context.md` — this file.

No change to `src/shell/**`: the published shape was sufficient, so the diff stays in the
consumer. No new dependencies added to `package.json`.

## Commands run (in the worktree's `northstar-os-ui`)

```
> npm ci
added 66 packages, and audited 67 packages in 3s
5 vulnerabilities (3 moderate, 2 high)
```

```
> npm run build
✓ built in 1.51s
```

```
> npx vitest run src/chat src/shell
RUN  v5.1.0 C:/.../state/worktrees/ux-07b/northstar-os-ui
 Test Files  4 passed (4)
      Tests  26 passed (26)
   Duration  425ms
```

Note: `vitest` is NOT in `package.json` (ux-07's `src/shell/tabRoutes.test.js` already
imports it), so the instructed `npx vitest` resolves it ephemerally — v5.1.0 via npx, not
added to the manifest. The run emits two pre-existing Vite warnings (`esbuild` option
deprecated by `vite:react-babel`); they are warnings, both test files and the build pass.

## What still does not reach the model

The UI half is done; the model still does not see `tab`. `Northstar_backend/chat_router.py`
`TurnIn` (line 797) declares `canvas` (line 811) but no `tab`, and the turn handler forwards
only `options={..., "canvas": body.canvas}` (line 1167). Pydantic's default `extra='ignore'`
means the new field is accepted without a 422 and then silently dropped — so no regression,
but no context either.

To finish the chain the backend needs (outside this lane's `src/chat/**` + `src/shell/**`
write paths, so not done here):

1. `tab: Optional[Dict[str, Any]] = Field(default=None)` on `TurnIn`.
2. Forward it into `turn_event_stream(options=...)` next to `canvas`.
3. Have the prompt assembly (`chat_tools.py:1809` reads `ctx["canvas"]` the same way) inject
   a short line such as "The operator is on Product Finder (/product-finder/…, filters view=offers)".

Also unchanged: the `northstar:workspace-tab` event is not subscribed by the chat surface;
the turn reads the published attribute/global at send time instead, which is the contract
`ShellLayout.jsx:106` documents for it. A turn sent in the same tick as a navigation, before
the shell's effect, would still read the render-time attribute and be correct.
