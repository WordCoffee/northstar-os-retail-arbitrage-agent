# ChromeConnect picker-visibility bugfix (Hybrid)

Date: 2026-09-30 (UTC)
Scope: picker launch step only. No new run, no process kill, no CDP, no
`--profile-directory` / `--user-data-dir`, no Oracle/Amazon policy change.

## Problem

`chrome.exe --profile-picker` returning "launched" was being conflated with the
chooser being visible. Chrome can forward the request into an already-running
instance (or open a plain window) and show nothing. Detection must be based on a
newly appeared visible top-level Chrome window, never on process-start success.

## Decision (operator)

Hybrid: keep **fail-closed** detection (a page-titled new window such as
`"New Tab"` is NOT the chooser and must never yield `picker_window_detected=true`),
but **remove the blocking confirmation gate**. On failed detection the flow stays
at `awaiting_profile_selection` and shows a guidance popup.

## Files changed

- `lib/chromecontrol/profile-flow.js`
  - `launchProfilePicker()` and `showPicker()`: on failed detection, state is now
    `awaiting_profile_selection` (was `awaiting_picker_visibility_confirmation`);
    `next_action` uses the new guidance.
  - `pickerVisibilityPopup()`: reworded to "bring the Chrome profile window
    forward, or open one from the Chrome avatar menu".
  - Added `profileGuidanceNextAction()` helper; exported.
  - Picker launch remains de-elevated (Explorer + throwaway `.lnk`) so the
    chooser can render at all from the elevated agent process.
- `lib/chromecontrol/orchestrator.js`
  - `beginBrowserTask()`: failed detection now sets `awaiting_profile_selection`
    + guidance popup (no blocking gate); doc comment updated.
  - `onPickerVisible()`: also accepts confirmation while at
    `awaiting_profile_selection`.
  - `ownerActionNeeded()`: guidance for `awaiting_profile_selection`.
  - `pickerVisibilityPopup()` reworded; added `profileGuidanceNextAction()`.
- `test/orchestrator-tests.js`
  - Updated the state/gate tests to the new spec; added
    "picker launch success alone is not visibility" (asserts request sent but no
    window detected, `picker_not_confirmed`, and run ID + checkpoint preserved)
    and "picker launch helper uses no kill, no CDP, and no profile args".
- `lib/chromecontrol/picker-window.js`: **unchanged** (fail-closed detection kept).
- No change to `config/chromecontrol.json` (already unpinned).

## Bounded wait / window diff

- Wait after the request: `pickerWaitMs()` (default 2500 ms, within the required
  2–4 s; env-overridable for tests).
- Enumerate visible top-level Chrome windows (title, class, PID, handle only —
  never content, tabs, cookies, history, or private windows).
- Diff handles against the pre-launch baseline. A new window ⇒ foreground it and
  `picker_window_detected=true`. No new window ⇒ `false`.

## Existing-instance forwarding

Handled by the handle diff: if Chrome forwards `--profile-picker` into an
already-running instance, **no new top-level window appears**, so
`detectPickerWindow()` returns `reason:"no_visible_picker_window"`, the result is
`picker_not_confirmed`, state stays `awaiting_profile_selection`, and the
guidance popup is shown. `picker_request_sent:true` alone never yields
`picker_visible`.

## Test results (offline, fully mocked)

- orchestrator: **61 passed / 0 failed**
- chromecontrol: **58 passed / 0 failed**
- browser-control: **21 passed / 0 failed**
- Total: **140 passed / 0 failed**

## Live check

`node scripts/chromecontrol.js show-picker` →
`result: picker_visible`, `picker_window_detected: true`,
`picker_window_foregrounded: true`, `reason: new_chrome_window_picker_title`.

Caveat (honest): a `"New Tab"` window and a `"Playwright Extension Status"`
window were already open during the check, so the newly appeared window carried a
generic `"Google Chrome"` title. Detection reported it as the chooser (generic
title + single new window), but this could not be visually confirmed as the
actual "Who's using Chrome?" screen. A clean confirmation needs Chrome fully
closed before launching the picker.

## Follow-up: generic title tightened + clean live log

- Detection tightened: a single new top-level window with a bare `"Google Chrome"`
  title is now `detected:false` / `reason:"new_chrome_window_unconfirmed"`
  (positive detection requires a named chooser title). Offline test updated/added:
  "a single new generic-titled ('Google Chrome') window is UNCONFIRMED".
- Clean live log (all Chrome windows closed first; BEFORE = []):
  - AFTER = `[{ pid: 60444, class: "Chrome_WidgetWin_1", title: "Google Chrome" }]`
  - `result: picker_not_confirmed`, `reason: new_chrome_window_unconfirmed`
  - state: `awaiting_profile_selection` + guidance
- Finding: the window produced by `--profile-picker` carries the SAME signature
  (`title="Google Chrome"`, `class="Chrome_WidgetWin_1"`) as an ordinary Chrome
  window, so title/class alone cannot distinguish the chooser.
- **Confirmed by owner:** that window IS the real "Who's using Chrome?" chooser.
  Recorded signature: `title="Google Chrome"`, `class="Chrome_WidgetWin_1"`,
  PID 60444. Because it is identical to a normal window, it is deliberately NOT
  added to `PICKER_TITLE_PATTERNS` (that would match every window). Detection
  stays `new_chrome_window_unconfirmed` and the owner confirmation
  (`Picker visible.`) / profile selection remains authoritative.

## Follow-up 2: process-based profile attribution removed

- `orchestrator.js`: `onProfileSelected`, `finishAttachment`, `resumePendingTask`
  no longer read Chrome process command lines or diff processes. The owner's
  selection is authoritative and recorded as `profile_verification_method:
  owner_confirmed`, `connected_profile_dir_name: owner-confirmed`,
  `selected_profile_dir_name: null`. Verification is the extension attaching
  (`extension_attachment`) — never process inspection.
- `defaultExtensionBackend.start()` is now extension-only and guarded by
  `assertExtensionAttachArgs()`: it refuses `--browser`, `--user-data-dir`,
  `--profile-dir-name`, `--profile-directory`, `--cdp-endpoint`,
  `--remote-debugging-port`, `--incognito`; it spawns `@playwright/mcp --extension`
  which only WAITS for the extension in the owner's existing window.
- `profile-detect.js` marked DIAGNOSTIC-ONLY (no longer used for attribution).
- Stale wrongly-attributed `selected_profile_dir_name="Default"` scrubbed from the
  durable row; run + checkpoint preserved.

### What opened the extra window (finding)

- ChromeConnect's attach step spawns exactly:
  executable `node.exe`, script
  `<npx-cache>\node_modules\@playwright\mcp\cli.js`, args `["--extension"]`.
  No `--browser`, no `--user-data-dir`, no profile pin, no CDP, no URL. In
  extension mode the MCP runs a local relay and waits — it does not launch
  `chrome.exe`.
- The only configured component that launches Chrome in a SEPARATE user-data-dir
  is OpenCode's GLOBAL `browser` MCP (`C:\Users\T2Hol\.config\opencode\opencode.json`):
  `npx -y @playwright/mcp@latest --browser chrome --user-data-dir C:\Users\T2Hol\.config\opencode\chrome-t2`.
  Its live children (`cli.js --browser chrome --user-data-dir ...chrome-t2`) are
  running now. `...\chrome-t2` holds its own `Default`/`Profile 6`/`Profile 7`
  (a separate, unsigned-in automation profile).
- The only URL involved is the Playwright extension's own relay page
  (`chrome-extension://mmlmfjhmonkocbjadbfplnigmagldckm/connect.html?mcpRelayUrl=ws://[::1]:<port>/extension/<uuid>&client=...&protocolVersion=2`),
  opened by the extension, not by ChromeConnect.
- CONCLUSION (high confidence): ChromeConnect's attach is not the opener; the
  unsigned-in window is launched by OpenCode's global `browser` MCP
  (`--user-data-dir chrome-t2`). Recommend disabling/removing that global server
  (or pointing it at `--extension`). Not changed unilaterally (user-global config).

### Tests

- Added: "no profile directory is inferred from Chrome process command lines";
  "attach is extension-only and never launches a browser".
- Updated: owner-authoritative end-to-end, verified-connection, and profile-switch
  assertions to expect `owner-confirmed` / `null`.
- Suites: orchestrator **63/0**, chromecontrol **58/0**, browser-control **21/0** = **142/0**.

Oracle navigation NOT resumed.

## Phase 1 inspection (read-only) + CDP decision

**1. Wrapper mode.** `scripts/chromecontrol-mcp.js` reads `config/chromecontrol.json`
(`attach_mode:"extension"`, `extension_profile_dir_name:null`) and calls
`resolveMcpArgs()` → `["--extension"]`. Confirmed: `--print-args` prints
`attach_mode=extension profile=(unpinned)` → `npx -y @playwright/mcp@latest --extension`.
CDP (`--cdp-endpoint=http://127.0.0.1:9222`) is emitted only when `attach_mode==='cdp'`
(`profile-store.js:80`); it is not.

**2. Does attach launch chrome.exe / open a URL?** No (post-fix). `orchestrator.js:651`
`resolveMcpArgs` → `:652` `assertExtensionAttachArgs(args)` guard → `:659`
`spawnMcp(args)`, and `spawner.js:84` `spawn(process.execPath, nodeArgs)` = 
`node <npx-cache>\\@playwright\\mcp\\cli.js --extension`. No `chrome.exe`, no URL.
The only URL anywhere is the Playwright extension's own relay page
`chrome-extension://mmlmfjhmonkocbjadbfplnigmagldckm/connect.html?mcpRelayUrl=ws://[::1]:<port>/extension/<uuid>&client=…&protocolVersion=2`,
opened by the extension itself. Navigation (`openPermittedProviderTab`) runs only
in `continueTask`, never in attach.
Pre-fix the same line spawned `--extension --profile-dir-name Default`.

**3. Empty 9222 → does anything start a browser?** No. `connection.js` `getCapabilities`
→ `checkCdp()` is a read-only probe; `getAttachmentMode` returns `disconnected` /
`no_cdp_endpoint`; `connectExistingBrowser` returns `ok:false` plus an instruction
string; `recoverConnection` only shows a popup. `lib/browser.js` can launch the
separate automation profile but only via `scripts/start-browser*.js`, never from attach.

**4. Code path that opened the extra unsigned-in window.** ChromeConnect's own attach,
via the (now-removed) process attribution: `onProfileSelected` resolved `Default`
from the un-flagged picker process → `extensionBackend.start({profile_directory:"Default"})`
→ the backend **persisted the pin and spawned `@playwright/mcp --extension --profile-dir-name Default`**
→ that pinned MCP drove the Chrome **Default** profile (unsigned-in, ≠ Profile 6).
Fixed by removing attribution and adding the extension-only guard.
Separately, OpenCode's **global** `browser` MCP
(`npx -y @playwright/mcp@latest --browser chrome --user-data-dir C:\\Users\\T2Hol\\.config\\opencode\\chrome-t2`)
is another browser launcher; it is not tied to "Profile selected." but is a second launcher.

**5. CDP dependencies → kept, not removed.** `NORTHSTAR_CDP_HOST/PORT` and
`cdp_endpoint` are depended on by: `lib/config.js`, `lib/chromecontrol/connection.js`
(`cdp_url`, `checkCdp`), `lib/chromecontrol/profile-store.js` (`cdp_endpoint`,
`--cdp-endpoint`), `lib/browser.js` (separate-profile launcher), `lib/chromecontrol/index.js`
(status), `scripts/browser*.js`, `scripts/check-browser.js`, `config/attachment.json`,
and `Default Project/opencode.json` (`mcp.playwright.environment`). Per Phase 2.4 the
settings were therefore **kept and reported**, not deleted. The attach path itself is
CDP-free (guard refuses `--cdp-endpoint`).

**Phase 3 not triggered:** Phase 1 does not show the extension connect page requires
launching Chrome (the extension opens its own relay page in the owner's existing
window), so no `--profile-directory="Profile 6"` pin exception is requested.

## Global browser MCP disabled + attach test

- Disabled only: `C:\Users\T2Hol\.config\opencode\opencode.json` → `mcp.browser.enabled`
  `true` → `false` (config kept; no other global change).
- What it launched: `npx -y @playwright/mcp@latest --browser chrome --user-data-dir
  C:\Users\T2Hol\.config\opencode\chrome-t2` — its OWN Chrome in the separate
  `chrome-t2` user-data-dir.
- Was it the source of the unsigned-in window? **No** — `chrome-t2\Local State`
  last write `2026-09-29 21:42:52`, no lockfile, unchanged at the
  "Profile selected." time. The unsigned-in window came from ChromeConnect's
  attach (`--profile-dir-name Default`, since removed). The global browser MCP was
  a latent second launcher, now disabled (effective next OpenCode restart).
- Harmless attach test: one read-only `playwright.browser_tabs list` returned
  `chrome-extension://mmlmfjhmonkocbjadbfplnigmagldckm/status.html`. No
  connect/approval page appeared (extension already connected); no new window
  (visible windows 1 → 1, PID 60444 = owner's Profile 6 window); no navigation;
  token not used.

## Run preservation

No run was created. The current durable run is `oracle-20260930T003129Z` with
checkpoint `target_url=https://www.oracle.com/cloud/sign-in.html; mode=read_only;
... created_before_picker=true`. NOTE: the request named
`oracle-20260930T000555Z`; that ID appeared earlier in the durable timeline, but
the live durable row (and its checkpoint) is `oracle-20260930T003129Z`. The
existing run/checkpoint were preserved as-is; the ID was not rewritten.
