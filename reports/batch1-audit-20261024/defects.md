# Batch 1 — defects

Every entry is something actually observed in this session, with the command or
screenshot that shows it.

## D1 — Chrome Connect MCP server exits and the tool catalog loses every `chromeconnect_*` tool

**Severity:** blocking (all UI evidence).
**Observed:** during the first G1 run the control returned normally (`run_id
steps_read_screenshot_…`), then the next call found the MCP server absent
(`search("chromeconnect") === []`). It returned once, then dropped again and has
stayed down.
**Proof it is down, not slow:** `Get-CimInstance Win32_Process -Filter "Name='node.exe'"`
lists only the Vite dev server (pid 2364) and its npm wrapper — there is **no**
`chromecontrol-mcp-server.js` process at all.
**Impact:** typing in the composer and clicking Northstar's own buttons is the
only admissible way to test the product; without the controller there is no
admissible path. G1–G6 are BLOCKED, not failed.
**Not caused by this batch's edits:** the first drop happened before any edit in
this session; the module still loads and its suite passes
(`node test/chromecontrol-tests.js` → 78 passed).
**Fix owner:** controller. Needs a supported restart of the MCP server (the
harness owns the stdio lifecycle). Do not "work around" it with a second browser
driver — that would bypass the allowlist/blocklist.

## D2 — Display Scale rendered twice

**Observed:** screenshot `product-tests/G1/g1-02-plan-card.png`; page text read by
the controller: `… Simple 90% 100% 115% 130% 90% 100% 115% 130% Operator …`.
**Cause:** `<DisplayScaleControl />` was mounted twice in `TopNav.jsx`.
**Fix:** one control, rendered only when the shell mode is `simple` (Simple and
AutothinK share the frame), and rebuilt as a segmented control instead of a raw
`<select>` — the raw select had no CSS at all, which is why it rendered as
`100%▾` twice.
**State:** fixed in source; build + shell gate green. Re-shoot pending (D1).

## D3 — Display scale fought the frame height

**Cause:** `zoom: var(--ui-scale)` sat on `.app`, the same element that carries
`height: 100dvh`. A viewport-sized element inside a zoomed subtree renders at
`100dvh × scale`, so at 130% the composer hangs off the bottom of the screen and
the exposed document shows as a band under the app (`probe-desktop.png`
precedent).
**Fix:** the frame (`.app`) is now sized outside the zoom and clips it; a new
`.app-scale` wrapper carries `zoom` and is laid out at `viewport / scale`, so
`scale × (viewport / scale) = one viewport` at 90/100/115/130%. Advanced mode
keeps the old frame (`display: contents`).
**State:** fixed in source; **not yet measured in the browser** (needs the
controller).

## D4 — UI claimed a "live voice" conversation that does not exist

**Observed:** composer button `title="Talk to Bojo (live voice — records locally,
transcribes with whisper.cpp)"`, plus "Talk to Bojo" as its aria-label.
**Reality:** dictation works (whisper.cpp); continuous listen→answer→speak is not
shipped.
**Fix:** the button is now `Dictate a message` (real recording, real transcript)
and a separate `Speak replies aloud` toggle that reads the *new* answer once,
never listens in the background, and never replays the previous answer when
switched on. The duplex loop is retained behind `LIVE_VOICE_ENABLED = false` and
is not rendered.
**State:** fixed in source; build + gate green.

## D5 — Renaming a session from the rail does not open the input

**Observed:** `click .chat-rail-row.active .chat-rail-edit` returned `ok: true`,
and the immediately following `type .chat-rail-rename | TEST-20261024` failed
because `[class="chat-rail-rename"]` does not exist.
**Consequence:** the step-0 requirement "start a NEW session named TEST-<date>"
is only half met — the session exists (created by the first prompt) but is titled
with the prompt text.
**State:** open. Needs one UI run to reproduce with a screenshot of the rail (D1
blocks it).

## D6 — Controller marks a successful UI turn as FAILED

**Observed:** the G1 run that typed the prompt returned
`status: FAILED, stop: success_unmet:typed_text_not_in_transcript` while the page
it had just read contained the prompt, the plan card and the draft button.
**Impact:** evidence-integrity. A real pass can be recorded as a failure, and a
failure could be argued away. The check needs to compare against the composer
value / persisted message, not a truncated body dump.
**State:** open (controller).

## D7 — Four different "missing artifact" situations collapsed into one

**Cause:** `/api/chat/sessions/{sid}/artifacts` reported a single `present` flag
(does the asset ROW exist) and the transcript rendered one broken-thumbnail path.
A row whose file was deleted still claimed `present: true`.
**Fix:**
- backend: `present` (row) + `file_present` (backing file) + `state`
  (`ok | missing_file | missing_metadata | missing_asset`), account-scoped exactly
  like the file route;
- transcript: a new `AssetMedia` component renders the server's `state` verbatim,
  and a decode failure of its own says "the file could not be loaded" — it never
  retries, so a 404 cannot become a request loop;
- workbench: labels `file missing` / `not stored (no file)` / `record missing`
  separately and only offers Download when something is actually there.
**Tests:** `python -m pytest test_chat_plan.py -q` → 18 passed, including the new
`missing_metadata`, `missing_file` and `ok` cases.
**State:** fixed and unit-tested; UI rendering of the states is untested until
D1 clears.
