# Local lanes installed — transcription, Piper voice, vision QC

**Date:** 2026-10-22 · **Branch:** `feature/v4.1-mesh` · **Lane:** local · **Spend:** $0

Installed in the order recommended: transcription → Piper voice → vision QC.
Each one is wired into the pipeline, not just present on disk, and each was
verified with a live run.

---

## 1. Transcription — `Northstar_backend/local_transcribe.py`

faster-whisper **1.2.1** + ctranslate2 **4.8.3** are importable in the backend's
own Python 3.14 (no second interpreter needed).

**CPU / int8 on purpose.** A teardown is a check; it must never be the reason a
render fails. `WHISPER_DEVICE=cuda` exists and is never automatic.

```
python local_transcribe.py --file NS_NARRATION_PIPER.wav
  text: "North Star Piper narration lane, offline neural voice."
  model: base · device: cpu · compute_type: int8 · seconds: 1.6
  vram_used: false
```

That is a round trip: Piper spoke the sentence, Whisper read it back word-for-word
— **1.6 s while ComfyUI held 13.4 GB of VRAM**, and the lane used none of it.

## 2. Piper voice — a real neural voice, offline

`en_US-lessac-medium` (60 MB) downloaded to `C:\Users\T2Hol\models\piper`.
`local_voice.py` now **auto-discovers** piper — `PIPER_EXE`, then `PATH`, then the
external-tools venv; and `PIPER_MODEL`, then `PIPER_MODEL_DIR`, then that folder's
first `*.onnx`. So dropping a voice file in the folder is the whole configuration.

```
python local_voice.py --engines
  piper: available true   sapi: available true (2 voices)   preferred: piper

python local_voice.py --say "..."
  piper -> NS_NARRATION_PIPER.wav (145,452 bytes)
  pcm_s16le · 22050 Hz · mono · 3.30 s
```

Piper is now the preferred engine; SAPI stays as the always-there fallback.
`generate_video(narration=...)` therefore speaks with the neural voice with no
change to the call site.

## 3. Vision QC — built to stress the GPU as little as possible

`Northstar_backend/local_vision.py` + `POST /api/design-studio/lanes/qc`.
Asks the local VL model whether a render matches the brief and answers in
structured JSON: `matches_brief`, `issues[]`, `confidence`, `description`.

Four rules, all of them about not disturbing the render lanes:

| Rule | Behaviour |
|---|---|
| **CPU when the GPU is busy** | reads free VRAM first; pins `num_gpu: 0` unless free ≥ `VISION_QC_GPU_HEADROOM_MB` (7000). Unknown VRAM → CPU. |
| **Never lingers** | every call sends `keep_alive: 0`, so the QC model unloads the moment the verdict arrives. |
| **Small frames** | downscaled to 768 px on the long side before they become vision tokens. |
| **A verdict or nothing** | unparseable reply → `verdict: "unparsed"` with the raw text; transport failure → the real reason. No invented verdicts. |

Live run, CPU mode at 2,598 MB free VRAM:

```json
{"verdict": "ok", "matches_brief": true, "issues": [], "confidence": 1.0,
 "description": "A clean studio product photograph of a matte kraft stand-up
                 pouch on a seamless warm bone backdrop, no text or labels.",
 "mode": "cpu", "model": "qwen2.5vl:7b", "max_side": 768, "seconds": 36.9,
 "vram_free_mb_before": 2598, "vram_free_mb_after": 15801, "eval_count": 50}
```

36.9 s on CPU is the honest price of not touching the GPU. That is the right trade
for a QC check; when the GPU is genuinely idle the lane will use it.

---

## Studio surface

`GET /api/design-studio/lanes/status` now reports **narration**, **transcription**
and **vision_qc** alongside cutout / upscale / main_check / prepress.

```
/status  /qc  /cutout  /upscale  /readiness  /main-check
```

## Provider suite

Three entries updated or added in `shared/provider-suite.json` (19 tools now):
`piper_tts` (installed, preferred), `faster_whisper` (installed, wired, CPU),
`local_vision_qc` (new). Local lane: **5 usable** with gates off, 11 with media
armed.

## Audit

`tools/creative_audit.py` now covers `local_*.py` too (31 modules) and treats a
swallowed exception as *reviewed* only when the author stated **why** —
`# noqa: BLE001 - reason`. A bare `noqa` no longer excuses it. Backlog: 105
findings, and two new tests pin that rule.

## Verification

```
pytest test_local_voice test_local_transcribe test_local_vision test_creative_audit
       + design_studio_lanes + provider_suite                     65 passed
```

## What is still not local

| Gap | Note |
|---|---|
| Model-based upscale | LANCZOS only; RealESRGAN aborted the server previously — needs a tiled graph proved on a small input first |
| Compose/typography | shipped 2026-10-16, still not re-run against a real plate + quad preset |
| Narration timing | the mux uses `-shortest`; nothing yet fits the script to the clip length or generates a longer clip to match |
| Vision QC policy | the lane returns a verdict; nothing yet *blocks* a render on it — that is a product decision, not a code gap |
