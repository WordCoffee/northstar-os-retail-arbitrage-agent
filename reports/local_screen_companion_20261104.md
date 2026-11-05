# Local screen companion — build report (2026-11-04)

## Request

A fully local option that can **view the screen, track what's going on, and
respond in live voice** — no cloud round-trip, no provider key.

## Shipped

| File | Role |
|---|---|
| `Northstar_backend/local_screen.py` | capture (PIL.ImageGrab, foreground-window region), RapidOCR, redaction, `qwen2.5vl:7b` scene note, grounded answer on the local text model, loopback gate |
| `Northstar_backend/local_screen_memory.py` | SQLite + FTS5 memory of screen text; dedupe by frame hash; search / recent / stats / scoped purge |
| `Northstar_backend/local_screen_agent.py` | `sample` / `ask` / `say` / `play`, one background `Watcher` (pause, resume, STOP file, bounded failure), `--live` hands-free loop |
| `Northstar_backend/local_ear.py` | offline speech input — faster-whisper via `sounddevice`, or the Windows System.Speech recogniser with zero install |
| `Northstar_backend/local_screen_api.py` | 14 routes under `/api/local-screen`, operator-only gate |
| `Northstar_backend/test_local_screen.py` | 48 offline tests |
| `docs/LOCAL_SCREEN_COMPANION.md` | operator doc: commands, API, rules, measured costs, limits |
| `Northstar_backend/main.py` | guarded import + `include_router` (`_HAS_LOCAL_SCREEN`) |

Installed: `sounddevice 0.5.6` (MIT) so the accurate whisper ear works. Nothing
else was needed — capture, OCR, whisper, Piper and both Ollama models were
already on the box.

## How it works

```
desktop --ImageGrab--> frame --RapidOCR--> text --redact--> SQLite (FTS5)
                          \                                    |
                           \--> qwen2.5vl scene note            |
                                     \                          v
                                      +------> qwen3:8b answer (grounded)
                                                        |
                                                   Piper / SAPI -> WAV -> speaker
microphone --whisper/CPU--> question --------------------^
```

## Live evidence from this machine

* Engines: capture `PIL.ImageGrab`, OCR `rapidocr`, Ollama 10 models,
  `qwen3:8b` + `qwen2.5vl:7b` installed, 15,767 MB VRAM free → vision on GPU.
* Capture 2560×1600 active region → 1600 px in **0.07–0.27 s**.
* OCR **2.8–3.0 s** warm, 6–9 s cold (engine load).
* Real question against a real desktop — *"Summarise what I am working on."* —
  answered in **17.5 s**: the screen was full of notes on Screenpipe / Windows
  Recall / Ollama, and the answer named them correctly, with
  `grounded_on.ocr_chars = 2163`.
* `qwen3:8b` with thinking on took **48 s** and truncated the answer; the lane now
  sends `think: false`.
* Vision path: `qwen2.5vl:7b` scene note on GPU, **33.5 s** cold (`keep_alive: 0`).
* Voice out: Piper produced a **202,284-byte WAV** and played it.
* Voice in: 4 s microphone capture → faster-whisper **6.77 s**, CPU, `no speech
  detected` in a quiet room — the pipeline works, honestly, without inventing a
  sentence.
* Blank-screen guard fired for real when the workstation locked mid-build:
  `possibly_secure_desktop: true`, no window title, nothing stored, and `ask`
  refused instead of asking a model about a black frame.

## Privacy and safety

* **Loopback only, enforced in code.** `assert_loopback()` runs before every
  Ollama request; a non-loopback `OLLAMA_HOST` raises `CloudRefused` and
  `engines()` reports the lane ungated. A test proves a refused host is never
  contacted.
* **Redaction** of e-mails, bearer tokens, `sk-`/`ghp_`/`nsk_`/AWS keys, JWTs,
  `password: ...` and card-like digit runs before storage or prompting; the count
  is reported.
* **Text-only memory** — no frames written to disk unless
  `LOCAL_SCREEN_THUMBS=1`.
* **Mic only in `--live`**; the watcher never records audio.
* **Bounded failure** — 5 consecutive capture errors stop the watcher with a
  reason; no silent infinite retry. `STOP` pauses it.
* **Scoped purge** — delete requires `all=true` or an explicit cutoff.
* API gate: platform admin anywhere, operator-and-above only off production; a
  customer tenant role is refused (401/403), proven by test.

## Verification

* `pytest test_local_screen.py` → **48 passed** (offline; no screen, model or
  microphone touched).
* `pytest test_local_vision test_local_voice test_local_transcribe
  test_creative_audit test_local_screen` → **98 passed**.
* `import main` → `app.openapi()` reports **14 `/api/local-screen` paths**.
* `tools/creative_audit.py` → 178 findings overall. The five new modules add
  **4 low-severity** items only: 3 functions 62–79 lines and the shared
  `engines()` name (repo convention). **Zero** CRE-SILENT, CRE-UNGATED,
  CRE-NOTEST in the new code.

## Not done

* **No UI panel.** The API is complete; a room panel is a follow-up.
* No always-on wake word or barge-in while speaking.
* No login autostart; the watcher is started deliberately.
* It is not a continuous recorder like Screenpipe — it samples on an interval.
* Windows-only (Win32 capture, window titles, SAPI, `winsound`).

## One thing the operator must do

`00_STATE.json` was **not** updated: every edit to it was rejected with
`Permission denied: edit` in this session (the file appears to be permission-
protected). The ready-to-paste block is in the appendix below; add it before
`"phases_completed"`.

## Appendix — state block

```json
  "local_screen_companion_20261104": {
    "what": "Fully local screen awareness + live voice: capture, OCR, SQLite/FTS5 memory, local text answer, Piper/SAPI speech. No cloud, no provider key.",
    "modules": "local_screen.py, local_screen_memory.py, local_screen_agent.py, local_ear.py, local_screen_api.py; registered in main.py (guarded)",
    "live": "capture 0.07-0.27 s; OCR 2.8-3.0 s warm; ask 17.5 s (qwen3:8b, think off); vision 33.5 s cold; piper WAV 202,284 B; whisper 4 s mic -> 6.77 s",
    "privacy": "loopback-only enforced, redaction before store/prompt, text-only memory, mic only in --live, scoped purge",
    "tests": "test_local_screen.py 48 passed; related suites 98 passed; 14 routes registered",
    "not_done": "no UI panel, no wake word, no autostart, interval sampling only, Windows-only",
    "docs": "docs/LOCAL_SCREEN_COMPANION.md"
  },
```
