# Lane UI defects — builder lane E

Date: 2026-11-11 · Repo: `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`
Scope: two queued defects found by the block3 lane. Both fixed. One further
defect was found in the same harness and fixed (Job 1, item 3); one was found
outside this lane's manifest and is reported, not touched (see §4).

All browser work was **headless Chromium/WebKit against 127.0.0.1:8101 only**.
`state/vision/PAUSE` was active: no visible browser was opened or driven, the
owner's Chrome was not touched. No Amazon host, no spend, no credential, no GPU.

---

## 1. Job 1 — `fix-tabbar-a11y` · FIXED

### What the component actually is

`northstar-os-ui/src/shell/TabBar.jsx` is the WAI-ARIA **tabs** widget, and it is
tested as one: `role="tablist"` -> `role="tab"` -> `role="tabpanel"`
(`ShellLayout.jsx:159-176`), `aria-selected`, `aria-controls="wst-panel-<id>"`,
roving tabindex, ArrowLeft/ArrowRight/Home/End with automatic activation.
`tests/e2e/workspace-tabs.spec.ts` asserts 15+ of those properties by role, so
dropping the tabs semantics would mean rewriting a shipped, passing contract.

It therefore keeps the tabs pattern. What was wrong was that the tablist **owned
a control that is not a tab**: the per-tab close button. `TabBar.jsx:76-110`
wrapped each tab in `role="presentation"` together with the × button, and axe
flattens the presentational wrapper, so the × landed as a direct child of the
tablist.

Measured, before the fix (`npx playwright test tests/e2e/a11y/tabbar_a11y.spec.ts`):

```
1) the tab strip has no critical or serious axe violations
  Error: tab strip a11y violations: [
    { "id": "aria-required-children", "impact": "critical", "nodes": 1,
      "targets": [".wst-list"],
      "evidence": ["Fix any of the following:\n  Element has children which are not allowed: button[aria-label]"] },
    { "id": "color-contrast", "impact": "serious", "nodes": 1,
      "targets": [".wst-hint"],
      "evidence": ["... insufficient color contrast of 4.34 (foreground #6f6e5f, background #f0ebe1, 7.9pt) ..."] } ]
```

I also checked the two obvious alternatives in an isolated axe probe before
choosing (same run, `page.setContent`, wcag2a+wcag2aa):

| candidate | result |
|---|---|
| current markup (presentational wrapper + real close button) | `aria-required-children` critical |
| close button nested inside `role="tab"` | `aria-required-children` critical |
| close button wrapped in `role="group"` inside the tablist | `aria-required-children` critical |
| close affordance `aria-hidden` + `tabindex="-1"` | clean |

A tablist may own **only** tabs, so there is no valid markup that keeps an
announced `<button>` inside the strip next to its tab.

### The fix

* `TabBar.jsx:123-136` — the × stays exactly where it is visually and keeps its
  `data-testid`, but it is now a **pointer affordance**: `aria-hidden="true"`
  (line 127), `tabIndex={-1}` (line 128). It is out of the accessibility tree, so
  it is out of the tablist's owned set.
* `TabBar.jsx:143-146` — new visually-hidden instruction (`#wst-keys-sr`),
  referenced from `TabBar.jsx:92` (`aria-describedby="wst-keys-sr"`): *"Use the
  left and right arrow keys to switch workspace tabs; press Delete to close the
  focused tab."* Delete was already implemented (`TabBar.jsx:64-74`); it is now
  the announced path, because the pointer path is not.
* `TabBar.jsx:15-25` — the file header records the rule and the measured
  violation so the next editor does not reintroduce it.
* `tabs.css:94-102` — the second violation the harness found: `.wst-hint` was
  `--ink-faint` (#6f6e5f) on `--paper-warm` = **4.34:1** at 10.5px. Now
  `--ink-mid` (#5a5a4a) = **5.9:1**.

### New permanent harness

`tests/e2e/a11y/tabbar_a11y.spec.ts` (new file, 3 tests, both viewports):

1. scoped axe run on the tab strip -> zero violations of any impact;
2. structural contract: the tablist is labelled and horizontal, owns exactly
   `['tab','tab']` (walking the tree the way the a11y tree does: presentational
   wrappers flattened, `aria-hidden` subtrees skipped), every tab has
   `aria-controls`, exactly one tab in the Tab order, and each close affordance
   is `aria-hidden` + not focusable, with `aria-describedby` naming the Delete
   path;
3. the keyboard still works — ArrowLeft/ArrowRight switch and move focus,
   Delete closes the focused tab.

After the fix:

```
$ npx playwright test tests/e2e/a11y/tabbar_a11y.spec.ts --project=chromium-desktop --project=chromium-mobile --reporter=list
  ok 1 [chromium-desktop] › the tab strip has no critical or serious axe violations (1.2s)
  ok 2 [chromium-desktop] › the tablist owns tabs and nothing else (680ms)
  ok 3 [chromium-desktop] › the keyboard still switches and closes tabs (3.3s)
  ok 4 [chromium-mobile]  › the tab strip has no critical or serious axe violations (3.6s)
  ok 5 [chromium-mobile]  › the tablist owns tabs and nothing else (2.1s)
  ok 6 [chromium-mobile]  › the keyboard still switches and closes tabs (5.5s)
  6 passed (18.2s)
```

The shipped ux-07 contract is intact:

```
$ npx playwright test tests/e2e/workspace-tabs.spec.ts --project=chromium-desktop --reporter=list
  ok 1 a workspace route opens one selected tab
  ok 2 switching tabs preserves input, scroll and loaded data (no remount)
  ok 3 tabs switch from the keyboard and aria-selected follows the panel
  ok 4 closing the active tab lands on a survivor; closing the last tab goes home
  ok 5 the shell tells Bojo which tab is open and what state it has
  5 passed (3.4s)
```

---

## 2. Job 2 — `fix-ux-scorecard-scroll` · FIXED (both sides)

### Was the shell regressed, or was the assertion stale?

**The assertion was stale — and it hid a real shell defect underneath.** Both
halves are in the evidence file `state/evidence/ux_layout_chromium-desktop.json`
/ `..._chromium-mobile.json` written by the spec.

The home surface resumes the most recent session for the focus and opens a
non-empty log on its newest turn; that is deliberate (`ChatSurface.jsx` — "Resume
the last session this focus was using, else the most recent one", then the
auto-pin effect). On this account the resumed session ("Hi Bojo") has 4 turns,
so `/ui/home` does **not** show the empty state at all, and the old gate

```
expect(layout.stream_scroll_top, 'the empty state must not be scrolled away on load').toBe(0)
```

measured a **resumed transcript** and demanded it be at scrollTop 0. Measured
deterministically, 7 samples from 150 ms to 6 s after load:

```
{ at: 150,  msgs: 4, empty: false, top: 612, sh: 844, ch: 232 }
{ at: 6000, msgs: 4, empty: false, top: 612, sh: 844, ch: 232 }
```

and the old spec failed with `Expected: 0 / Received: 612` (first run of the day,
3 failed) but *passed* on the next run because the session fetch had not landed
inside the spec's fixed 600 ms wait — i.e. it passed by measuring the empty state
before the transcript arrived. A gate that flips on a race is not describing the
product.

### The shell defect it was hiding (real, fixed)

Once the spec was made to reach the empty state deliberately (via the product's
own **New chat**), the mobile measurement showed the greeting still scrolled off:

```
chromium-mobile, after New chat, BEFORE the fix:
  { "empty_state": true, "stream_height": 305, "stream_scroll_height": 377,
    "stream_scroll_top": 72, "greeting_visible": false }
```

Cause: removing a 15 991px transcript clamps the old scroll offset to the new
maximum (72) instead of zeroing it, so the greeting sat 72px above the fold —
the same class of defect as the original "greeting scrolled out of view".
`northstar-os-ui/src/chat/ChatSurface.jsx:504-517` now returns an empty stream to
the top instead of merely declining to pin it:

```js
if (messages.length === 0) {
  if (el.scrollTop !== 0) el.scrollTop = 0
  return
}
```

After: `{ "empty_state": true, "stream_height": 305, "stream_scroll_height": 377,
"stream_scroll_top": 0, "greeting_visible": true }`.

### The assertion, rewritten (not deleted)

`tests/e2e/ux_scorecard.spec.ts:340-457` now measures **both** legitimate resting
states of the stream and says which rule applies to which:

* resumed transcript (`messages > 0`) -> must be **pinned to its newest turn**
  (`scrollHeight - (scrollTop + clientHeight) <= 2`);
* empty state -> must be at **scrollTop 0** with the greeting inside the stream
  viewport and a stream height >= 200px. This half is reached through the
  product's own **New chat** control (opening the collapsed session rail first on
  a phone), so it runs on every project instead of only when the account happens
  to have no sessions.

Both halves are written to `state/evidence/ux_layout_<project>.json`
(`resumed_transcript`, `on_load`, `clicked_new_chat`, `after_new_chat`).

```
$ npx playwright test tests/e2e/ux_scorecard.spec.ts --reporter=list   # both projects
  ok  1 [chromium-desktop] ux: first_run          ok  7 [chromium-mobile] ux: first_run
  ok  2 [chromium-desktop] ux: creative           ok  8 [chromium-mobile] ux: creative
  ok  3 [chromium-desktop] ux: research           ok  9 [chromium-mobile] ux: research
  ok  4 [chromium-desktop] ux: service coverage   ok 10 [chromium-mobile] ux: service coverage
  ok  5 [chromium-desktop] ux: tab state          ok 11 [chromium-mobile] ux: tab state
  ok  6 [chromium-desktop] ux: scene readability  ok 12 [chromium-mobile] ux: scene readability
  12 passed (1.4m)
```

Before the change the same command reported `3 failed` on chromium-desktop
(`ux: creative`, `ux: research` — both `aria-required-children` on `.wst-list`,
i.e. Job 1 — and `ux: scene readability` — `Expected: 0 / Received: 612`).

---

## 3. Gates re-run after both fixes (real commands, real counts)

| gate | command | result |
|---|---|---|
| production build | `cd northstar-os-ui && npm run build` | `✓ built in 1.42s`, 0 errors |
| unit suite | `cd northstar-os-ui && npm run test:ui` | `tests 231 / pass 231 / fail 0` |
| workspaces e2e | `npx playwright test tests/e2e/workspaces --project=desktop-chromium --project=iphone-12-webkit` | `56 passed (42.8s)` |
| ux scorecard | `npx playwright test tests/e2e/ux_scorecard.spec.ts` | `12 passed` |
| new a11y harness | `npx playwright test tests/e2e/a11y/tabbar_a11y.spec.ts` | `6 passed` |
| ux-07 tabs | `npx playwright test tests/e2e/workspace-tabs.spec.ts --project=chromium-desktop` | `5 passed` |
| shell chrome + workbench | `npx playwright test tests/e2e/shell-chrome.spec.ts tests/e2e/workbench.spec.ts --project=chromium-desktop` | `11 passed` |

Files touched (nothing outside the write manifest):
`northstar-os-ui/src/shell/TabBar.jsx`, `northstar-os-ui/src/shell/tabs.css`,
`northstar-os-ui/src/chat/ChatSurface.jsx`,
`tests/e2e/ux_scorecard.spec.ts`, `tests/e2e/a11y/tabbar_a11y.spec.ts` (new).

No `git add`, no `git commit` — the director commits.

---

## 4. Found, not fixed (outside this lane's manifest)

`tests/e2e/chat_composer_stability.spec.ts:25` navigates to
`http://127.0.0.1:8101/ui/design-studio` and waits for `[data-testid="chat-input"]`,
which never attaches: `/ui/design-studio` renders the Design Studio page with **no
chat surface at all** (probe: `chatShell: false, chatInput: false, textareas: 0`, no
page errors). The composer now lives in `pages/internal/CreativeStudio.jsx:733`
via `<CreativeChat />`, i.e. on `/ui/creative-studio` (probe: `chatShell: true,
chatInput: true`). So this is a stale route in a spec, not a UI regression, and it
predates this lane (spec last changed in `23465d16`, 2026-10-28; no UI file in
this lane's diff could unmount a component).

Fix belongs to whoever owns that spec: either point it at `/ui/creative-studio`,
or decide the Design Studio page should carry a composer again. Cost to the
suite today: 1 failing test in `tests/e2e/chat_composer_stability.spec.ts`
(the scrollbar-gutter assertions themselves were never reached).

## 5. What a verifier should re-run

`tests/e2e/a11y/tabbar_a11y.spec.ts` (both projects) — it is the only check that
can see the tablist's owned roles, and it is the one that fails the moment a real
button is put back inside `.wst-list`.
