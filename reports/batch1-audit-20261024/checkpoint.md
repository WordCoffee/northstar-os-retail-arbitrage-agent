# Batch 1 — checkpoint

**State:** implementation and executable checks complete for the defects that do
not need a live browser; the operator's UI generation run is **blocked** by a
controller outage (D1). Nothing in G1–G6 is claimed.

## Done in this batch

1. **Backend honesty** — `/api/chat/sessions/{sid}/artifacts` now reports
   `present` (row), `file_present` (backing file) and `state`
   (`ok | missing_file | missing_metadata | missing_asset`), account-scoped the
   same way the file route is. Three new tests; `18 passed`.
2. **Transcript** — new `AssetMedia` component renders the server's state
   verbatim instead of hiding an `<img>` with a DOM hack; a decode failure gets
   its own note and never retries.
3. **Workbench** — separate labels for a missing file, an unstored asset and a
   vanished record; Download only offered when something is there.
4. **Effects wired to real events** — `is-streaming` on a live assistant turn,
   `chat-dock` naming the service that is actually executing (ComfyUI, label
   compositor, dieline builder, …) with its pct, and a one-shot `chat-comet`
   that is set only from a `done` event of a live turn (a reload cannot replay
   it). Reduced-motion already suppresses all three.
5. **Voice honesty** — `Talk to Bojo (live voice)` is gone. Dictation is a real
   mic button; `Speak replies aloud` is an explicit toggle that reads the new
   answer once, never listens in the background, and cannot replay the previous
   answer when switched on. The duplex loop is retained behind
   `LIVE_VOICE_ENABLED = false`.
6. **Display scale** — duplicate control removed, scoped to Simple/AutothinK,
   rebuilt as a segmented control; the zoom moved off the `100dvh` frame onto a
   `.app-scale` wrapper laid out at `viewport / scale`.
7. **Controller** — tab selection is sticky and `(current)` is parsed, so a
   duplicate app tab can no longer make typing and screenshots land on different
   tabs. 78 controller tests pass. Committed in the **Default Project
   (Chrome Connect)** repo as `05c7df9`, local only, no policy/allowlist change.

## Checks

```
npm run build                     -> 0 errors
node verify-shell-v3.cjs          -> 28 passed, 0 failed   (HARNESS_BASE_URL=:8101/ui/)
python -m pytest test_chat_plan.py -q -> 18 passed
node test/chromecontrol-tests.js  -> 78 passed, 0 failed
```

## Not done / next

- Restore Chrome Connect (D1), then re-run **the same G1 scenario** from the
  composer, not from an API.
- Re-shoot the home screen at 100% and 130% on desktop and 390×844 to prove D2/D3
  with measured rects, not with prose.
- Reproduce D5 (rail rename) and fix it.
- Only then continue G2–G6 with the brief's evidence set per item.

The correct status line for this batch is: **implementation and executable
checks complete; awaiting a working Chrome Connect MCP server for UI-verified
product tests.**
