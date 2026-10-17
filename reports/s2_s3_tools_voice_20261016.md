# S2 (Tools + ComfyUI progress) & S3 (Voice PTT) — Execution & Verification Report

**Date:** 2026-10-16 (evening session) · Branch `feature/overnight-remediation-20261009`
**Stack:** locked by `research/master_plan_v2_sweep_20261016/REPORT.md` (commit `7861b4e`).
**Protocol:** one unit at a time → tests after each → live smokes → backend restarted into the new build.

---

## 1. What is NOW LIVE (and how it was proven)

| Unit | Files | State |
|---|---|---|
| S2 tool registry | `Northstar_backend/chat_tools.py` (new) | 5 tools: `system_status`, `list_templates`, `design_brief`, `create_dieline`, `generate_image`; outputguard-style validate→repair→honest-error; unknown keys dropped; args fenced-JSON tolerant |
| S2 tool loop | `chat_router.py` (rewritten) | Ollama-native `tools`; tool_call streaming merge (indexed fragments); worker-thread execution with live `tool-progress`; bounded `MAX_TOOL_STEPS=4`; `tool-start/progress/end/asset` SSE frames; persistence to `chat_tool_calls` + `chat_attachments` (+ parts) exactly once on every exit path |
| S2 ComfyUI bridge | `studio_generation.py` (patched) | `/ws` listener bound to the submitting `client_id`; `progress`/`executing`/`execution_start` → `on_progress(pct,label)`; polling lane unchanged as source of truth; `release_models()` remains opt-in (GGUF unload-crash caveat respected) |
| S2 chat UI | `src/chat/CreativeChat.jsx`, `api.js`, `chat.css` | live tool chips (name · % or phase · indeterminate bar), artifact cards (image preview + download links), history replay from `parts_json` |
| S3 voice PTT | `chat_voice.py` (new), `chat_voice` client | `POST /api/chat/voice/transcribe` (ffmpeg → 16 kHz mono → local whisper-cli), `GET /voice/status`; parser strips `<|endoftext|>` tokens, timestamps, loader noise; annotation-only output ("(eerie music)") → honestly empty |
| S3 chat UI | `CreativeChat.jsx` | mic button → **Stop recording** (distinct) → local transcription into composer; "Heard nothing" honesty line; no audio leaves the machine |
| Infra fix | `llm_adapter.py` | `think` now explicit on the wire (False = thinking truly off — a model defaulting to thinking was burning the whole budget); `tools` param; `num_gpu` cap; error text carries the Ollama body |
| Wiring | `main.py`, `requirements.txt` | chat + voice routers guarded + mounted; `python-multipart`, `websockets` declared; **backend restarted** (pid 22124) → routes live |

## 2. Evidence (all real runs)

| Gate | Result |
|---|---|
| Unit/integration suites | **71 passed** (`test_chat_core` 15, `test_chat_tools` 13, `test_chat_voice` 4 incl. **real whisper live smoke**, design-studio suites 39) |
| LIVE render + progress | Real ComfyUI render (klein-4B, 512², draft): progress frames `queued → running → 25% → 50% → 75% → 100% sampling → finishing`, **358 KB PNG in 6 s** |
| LIVE tool roundtrip | qwen3:4b via Ollama native tools → **2 tool_calls merged by index** → validation → server execution `list_templates → ok=True, 9 templates` |
| LIVE voice | Real `whisper-cli.exe` on synthesized audio → pipeline ok; non-speech honestly reduced to empty transcript |
| Backend live | UI 200, `/api/chat/health` **401 (mounted + auth-enforced)**, `/api/chat/voice/status` **401**, clean boot log ("Northstar OS ready") |
| UI build | `npm run build` 0 errors (pre-existing chunk warning only) |

## 3. Hardware constraints discovered (exact evidence, for the record)

1. **27B full offload vs desktop+ComfyUI memory:** `cudaMalloc failed … unable to allocate CUDA0 buffer of size 9676124160` — with ~5.9 GB free VRAM the production 27B cannot fully offload.
2. **27B partial offload (num_gpu=24):** `failed to allocate buffer of size 5921697792 … CUDA_Host` — the CPU-resident layers need ~5.9 GB pinned RAM; this box has 15.4 GB total, mostly claimed.
3. **Mitigations shipped/handed over:** `CHAT_NUM_GPU` env knob (partial offload when VRAM allows), lean chat context (`CHAT_NUM_CTX=16384`), and **`qwen3:4b` pulled** as the small tool/voice lane model. Operator options for 27B chat: close GPU/RAM-heavy desktop apps before a session, restart ComfyUI to drop its cache, or run chat on the small model while rendering.
4. Encoder pairing note: klein-4B must pair with `qwen_3_4b_fp8_mixed.safetensors` (the default pairing is for 9B).

## 4. Explicitly NOT done in this pass (honest scope)

- **[PAUSE-AUTH] REA / Chrome Connect Packify pass** — REQUIRES the operator at the browser: login handshake, bounded per the REA runbook, operator-present. Staged, not started (the directive's own pause gate).
- **Master Brain living-file + policy scheduler** — designed (mtime watch + atomic `os.replace` + foundation jobs), not built this session.
- **AT-0/AT-1** — `reasoning_effort` corrected to think-budget mapping (`think` + `num_predict`; partial-offload knob); DSpark/DFlash pilot deferred (DGX-Spark-class recipes vs this 16 GB box).
- **Phase 2–4** (Qdrant escalation, SEO telemetry, Argos glossary, Playwright infographics, syndication adapters, brand-voice drift checker, expan A/B + feedback loop) — shortlisted with licenses in the sweep report; build order ready, not started.

## 5. Operator quick-test

1. Open `/ui` → top-right toggle → **Simple** → Creative Studio = chat.
2. Ask: *"list the dieline templates, then draft a brief for a 130×210 stand-up pouch"* → watch tool chips stream.
3. With the media engine armed, ask for a backdrop render → progress bar in-chat → image card.
4. Click **● Voice**, speak, **Stop recording** → transcript lands in the composer.
