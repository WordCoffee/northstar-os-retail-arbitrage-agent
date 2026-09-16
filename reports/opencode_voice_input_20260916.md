# Voice Input for OpenCode — Implementation Report

**Task:** Use voice to give prompts in OpenCode
**Date:** 2026-09-16
**Status:** Built + verified (operator live voice test pending)

## What was built

### Part 1 — Standalone voice-to-clipboard (works now, no OpenCode changes)

| File | Purpose |
|---|---|
| `scripts/voice-to-clipboard.js` | Records mic via `sox.exe` (stops on ~0.8s silence, 25s cap), transcribes with `whisper-cli.exe` (`ggml-base.en`), copies result to clipboard via `clip.exe`. `--json` mode for machine use; `--file <wav>` test hook; `NS_SOX_PATH` / `NS_WHISPER_CLI` / `NS_WHISPER_MODEL` / `NS_WHISPER_VAD` / `NS_VOICE_MAX_SECONDS` env overrides |
| `scripts/voice-to-clipboard.bat` | Windows launcher (drop a shortcut to it, assign a global hotkey) |
| `package.json` | Added `npm run voice` (clipboard mode) and `npm run voice:json` |

### Part 2 — OpenCode CLI plugin (seamless in-TUI voice)

Location: `C:\Users\T2Hol\.config\opencode\voice-input\` (`package.json`, `index.ts` server stub, `tui.ts` CLI plugin, `README.md`)
Registered in `~/.config/opencode/cli.json` → `"plugins": ["C:/Users/T2Hol/.config/opencode/voice-input"]`.

**Keybinds:** `Ctrl+X` then `V` · `Ctrl+Alt+V` · Command palette → *Voice input: record and send a prompt*

**Flow:** keybind → "Listening…" toast → speak, pause → whisper transcribes locally → confirm dialog shows the text → **Send** submits it to the active session via `client.session.prompt({ sessionID, text })`; **Cancel** keeps it on the clipboard (always copied as fallback).

## Verification (real commands, real output)

| Check | Result |
|---|---|
| Binaries present | `whisper-cli.exe`, `ggml-base.en.bin`, `ggml-silero-v6.2.0.bin`, `sox.exe` (SoX_ng 14.7.1.2), `clip.exe`, Node v24.15.0 |
| Script help | `node scripts/voice-to-clipboard.js --help` → OK |
| Whisper pipeline (synthetic WAV) | `--file ... --json` → `{"ok":true,"text":"(dramatic music)"}` pre-filter; post-filter → correctly rejected non-speech: `{"ok":false,"error":"No speech detected — test WAV produced no transcript."}` |
| Live mic capture | `sox -d ... trim 0 2` → 2.05s recorded from default device, 64044-byte WAV, exit 0 |
| Plugin TS syntax | Node 24 parse check → clean (only expected `ERR_MODULE_NOT_FOUND` for runtime-resolved `@opencode/plugin`) |
| Plugin loads in OpenCode | Log: first setup failed `Keymap.Provider is missing` (keybinds registered in `setup`). Fixed by registering keybinds inside `context.ui.slot({ append: "app" })`. Post-fix reconciliation: `plugins=12`, **zero failures** |
| State file | `00_STATE.json` updated (history entry + `last_updated`), JSON valid |

## Key implementation note

OpenCode's TUI keymap provider is not mounted during plugin `setup` — keybinds must be registered inside a rendered slot (`context.ui.slot({ append: "app", render: () => { context.keymap.layer(...) } })`) or setup fails with `Keymap.Provider is missing`. Captured in the plugin's code comment and README.

## How to use

1. **Restart the OpenCode TUI** (or reload plugins) so the CLI plugin loads.
2. Press `Ctrl+X` `V` (or `Ctrl+Alt+V`), speak after the toast, pause.
3. Confirm the dialog → the voice prompt is sent to the session and the agent responds.
4. Standalone (outside OpenCode): `npm run voice`, or double-click `scripts/voice-to-clipboard.bat`; assign a global hotkey for one-press dictation anywhere.

## Scope / safety

- 100% local, offline transcription (whisper.cpp) — no API keys, no costs, no live/paid calls.
- No secrets touched, no `.env` reads, no pushes (local commit only: `f286c25`).
- The pre-existing web voice components (`components/chat-voice.js`, `universal-voice.js`, `server/voice-transcribe.js`) were left untouched and are unrelated to OpenCode input.

## Next steps

- Operator live voice test (mic, keybind, confirm dialog, prompt send).
- Optional: global-hotkey shortcut to `voice-to-clipboard.bat` for dictation outside OpenCode.