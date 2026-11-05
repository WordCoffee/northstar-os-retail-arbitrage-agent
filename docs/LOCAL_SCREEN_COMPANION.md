# Local screen companion — see, remember, answer, speak (all on this box)

**Built 2026-11-04.** This is the fully local answer to "an AI that can watch my
screen, track what's going on and talk back to me". Nothing is uploaded. The only
network destination in the whole lane is `127.0.0.1:11434` (Ollama), and that is
enforced in code, not in prose.

## What it does

| Piece | How | Where |
|---|---|---|
| Sees the screen | `PIL.ImageGrab` (built into Pillow on Windows), foreground-window region by default | `Northstar_backend/local_screen.py` |
| Reads the text | RapidOCR on CPU, ~3 s per frame (warm) | same |
| Understands the scene | `qwen2.5vl:7b` through local Ollama, `keep_alive: 0` | same |
| Remembers | SQLite + FTS5, text only, dedupes idle frames | `local_screen_memory.py` |
| Answers | `qwen3:8b` through local Ollama, grounded on the OCR text + scene note | `local_screen.py::ask_screen` |
| Speaks | Piper (preferred) or Windows SAPI, written to a local WAV | `local_voice.py` |
| Hears you | faster-whisper on CPU, or the Windows speech recogniser (zero-install) | `local_ear.py` |
| Runs the loop | one background sampler, pause/stop, bounded failure | `local_screen_agent.py` |
| Serves it | `/api/local-screen/*` (operator-only gate) | `local_screen_api.py` |

## Run it

```powershell
cd Northstar_backend

# what can this box actually do right now?
python local_screen_agent.py --status

# one frame into memory (capture + OCR; no model call)
python local_screen_agent.py --once

# ask about the current screen
python local_screen_agent.py --ask "what is this error?"

# ...and have it said out loud
python local_screen_agent.py --ask "summarise what I am working on" --speak

# watch continuously (5 s), storing a searchable text history
python local_screen_agent.py --watch --interval 5

# hands-free: listen on the mic, answer out loud, repeat
python local_screen_agent.py --live --seconds 6

# search what it saw earlier
python local_screen_agent.py --search "out of memory" --minutes 120
```

`--scope active|primary|all` (default `active`) decides what is read. `active`
crops to the foreground window's region, which is what keeps UI text crisp on a
5120×1600 two-monitor desktop; `all` reads the whole virtual desktop at once and
is noticeably worse for OCR because each monitor is halved before recognition.

## API (operator-only)

All routes are under `/api/local-screen` and require the operator role on a
non-production box (platform admin anywhere; a customer role is always refused).

```
GET  /status                       engines, watcher, memory, voice, ear
POST /sample                       {vision, scope} -> one tick
POST /ask                          {question, speak, voice, vision, scope}
POST /watch/start|stop|pause|resume {interval_s, vision, scope}
GET  /memory/recent?limit&minutes
GET  /memory/search?q&limit&minutes
GET  /memory/stats
POST /memory/purge                 {all} or {older_than_hours}
POST /say                          {text, voice, play}
POST /listen                       {seconds, engine}
GET  /audio/{name}                 serve a locally synthesised WAV
```

## The rules this lane is built on

1. **Loopback only.** `assert_loopback()` runs before every Ollama request and
   raises `CloudRefused` for anything that is not `127.0.0.1`/`::1`/`localhost`.
   There is no upload path, no telemetry, no cloud fallback. A unit test proves a
   refused host is never contacted.
2. **Redaction before storage or prompting.** E-mails, bearer tokens, `sk-`/`ghp_`
   keys, AWS keys, `nsk_` keys, JWTs, `password: ...` assignments and card-like
   digit runs are masked. It is pattern-based and says how many substitutions it
   made; it is not a guarantee.
3. **Text memory, not video.** Frames are not written to disk by default. Set
   `LOCAL_SCREEN_THUMBS=1` if you want one 640 px JPEG per distinct frame.
4. **Locked screen is reported, not read.** A near-black frame returns
   `possibly_secure_desktop: true`; the vision model is never asked about it and
   nothing is stored / answered. This fired for real during the build when the
   workstation locked.
5. **Bounded failure.** Five consecutive capture errors stop the watcher with
   `stop_reason: error_budget_exhausted`. It never retries forever in silence.
6. **One watcher.** `start()` twice returns `already_running` instead of spawning
   a second sampler.
7. **STOP file wins.** If `STOP` exists in the repo root the watcher pauses on the
   next tick and records `stop_reason: stop_file`.
8. **Explicit recording.** Only `--live` opens the microphone. The watcher never
   records audio.
9. **Deletes require a scope.** `purge` refuses to run without `all=True` or an
   explicit cutoff.

## Measured on this box (2026-11-04)

| Step | Cost |
|---|---|
| Capture 2560×1600 (active region), downscale to 1600 px | 0.07–0.27 s |
| OCR, warm engine, 1600 px | 2.8–3.0 s |
| OCR, cold (first call in a process) | 6–9 s |
| `qwen3:8b` answer, thinking off | 17.5 s warm (48 s with qwen3 thinking on — hence `think: false`) |
| `qwen2.5vl:7b` scene note, cold load on GPU | 33.5 s |
| Piper speech, one sentence | ~0.2 MB WAV, sub-second to a few seconds |
| faster-whisper, 4 s of microphone audio | 6.8 s end to end, 0 VRAM (CPU) |

Live answers were correct against a real desktop: a screen full of notes about
screen-recording tools was summarised as "exploring tools for screen monitoring
and AI interaction … Screenpipe … Windows Recall". That run used OCR only
(`vision_used: false`), which is the normal case on a text-heavy screen.

## Deliberate limits (so nobody is surprised)

* **Not a continuous recorder.** It samples on an interval (default 5 s) while the
  watcher runs. It is not a background service, and it does not start itself at
  login. Inference cost is why: a frame is ~3 s of CPU OCR.
* **Vision is slow and optional.** The scene note costs ~30 s including model
  load because `keep_alive: 0` deliberately unloads it. Use it for "what does this
  look like", not for every tick.
* **OCR is not perfect.** Small or anti-aliased text on a scaled screenshot is
  garbled, and the redactor can mask a legitimate long number.
* **One watcher per process.** The API and the CLI are separate processes, so each
  has its own watcher; they share the same memory database.
* **No wake word.** `--live` listens in cycles; there is no always-on keyword
  spotter and no barge-in while it is speaking.
* **Windows only.** Capture, window titles, SAPI and `winsound` are Win32 calls.
* **No UI surface yet.** It is a CLI plus an API. A room panel can call the API as
  it stands.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `LOCAL_SCREEN_MODEL` | `qwen3:8b` | answer model |
| `LOCAL_SCREEN_VISION_MODEL` | `qwen2.5vl:7b` | scene model |
| `LOCAL_SCREEN_MAX_SIDE` | `1600` | OCR frame long side |
| `LOCAL_SCREEN_VISION_MAX_SIDE` | `1024` | vision frame long side |
| `LOCAL_SCREEN_SCOPE` | `active` | `active` / `primary` / `all` |
| `LOCAL_SCREEN_DIR` | `Northstar_backend/data/local_screen` | audio + thumbs root |
| `LOCAL_SCREEN_DB` | `…/data/local_screen/memory.db` | memory database |
| `LOCAL_SCREEN_THUMBS` | `0` | write one JPEG per distinct frame |
| `LOCAL_SCREEN_MAX_ERRORS` | `5` | consecutive failures before the watcher stops |
| `LOCAL_EAR_SECONDS` | `6` | default microphone window |

## Tests

`Northstar_backend/test_local_screen.py` — 48 tests, all offline (no screen, no
model, no microphone). They pin the loopback refusal, the redaction set, the
`keep_alive`/`num_gpu` payload rules, the blank-frame rules, memory dedupe/search/
purge scoping, the watcher's bounded failure and idempotent start, the voice/ear
paths with injected engines, the API responses and the operator gate.
