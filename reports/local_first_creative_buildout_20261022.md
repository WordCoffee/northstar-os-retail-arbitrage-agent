# Local-first creative buildout — narration lane

**Date:** 2026-10-22 · **Branch:** `feature/v4.1-mesh` · **Lane:** local · **Spend:** $0

---

## First, a finding that supports the plan

I grepped every creative module for cloud provider references
(`fal`, `FAL_KEY`, `replicate`, `openrouter`, `gpt-image`, `nano-banana`,
`elevenlabs`, `deepgram`, `suno`) across `design_studio_*.py`, `studio_*.py`,
`mockup_*.py`, `creative_*.py`, `text_fidelity.py`, `package_readiness.py`,
`prepress.py`, `image_prep.py`, `dieline_art.py`, `listing_forge.py`,
`ad_pilot.py`, `social_pulse.py`:

**Zero matches.** The creative pipeline is already local-only by construction —
the cloud lane lives in `model_router` and `model-suite.json`, not in the creative
code. So "build for local, cloud follows" is not a rewrite; it is filling gaps.

---

## The gap that mattered: there was no audio

Every creative lane produced silent output. Video rendered frames and stopped.
Ads had copy but no voiceover. `voicestudio_adapter.py` pointed at a VoiceStudio
service on `:8321` that was not running, while two working local speech options sat
unused on the same machine (Windows SAPI, and Piper in the OpenMontage venv).

### Built

**`Northstar_backend/local_voice.py`** — the local narration lane.

| Engine | When | Notes |
|---|---|---|
| **piper** | `PIPER_EXE` + `PIPER_MODEL` set | real neural voice, still offline |
| **sapi** | always on this box | Windows System.Speech via PowerShell |

- `engines()` reports what is actually present — no pretending.
- `synthesize(text, voice=...)` → WAV bytes, engine name, voice id.
- `mux_audio(video, audio)` → MP4 with an AAC track, ffmpeg `-shortest`.
- Refuses empty text, over-long text, unknown voices, and a dead engine — each with
  the real reason.

**Wired into the video lane:**

```python
studio_generation.generate_video(prompt, narration="Organic Lions Mane powder…")
```

The script is spoken locally and muxed onto the clip. A dead speech engine does
**not** fail the render — the clip returns silent with `audio.ok = false` and the
reason, so a silent clip can never be passed off as a narrated one.

**Surfaced in the studio:** `GET /api/design-studio/lanes/status` now reports a
`narration` lane (engine, per-engine availability, ffmpeg presence).

### Verified live

```
local_voice.py --engines
  piper  available:false  sapi available:true (2 voices)  ffmpeg:true  preferred:sapi

local_voice.py --say "Northstar local narration lane is live."
  sapi -> NS_NARRATION.wav (138,694 bytes)
  ffprobe: pcm_s16le · 22050 Hz · mono · 3.14 s

_attach_narration(NS_CREATIVE_VIDEO.mp4, "Organic Lions Mane powder…")
  ok:true engine:sapi voice:microsoft-david-desktop
  ffprobe on the result: 0,h264,video,2.041667 · 1,aac,audio,1.996916
```

A real narrated MP4, produced with no provider key and no spend.

---

## Tests

```
pytest test_local_voice.py                                        12 passed
pytest (7 creative/studio suites)                                112 passed, 1 skipped
```

The narration tests pin the honesty contract: empty text, over-long text, unknown
voice, dead engine, missing ffmpeg, and the two video paths (with and without
narration) — including that a broken speech engine still returns the silent clip.

---

## Still missing for a *complete* local system

| Gap | State | Effort |
|---|---|---|
| Transcription wired into the backend | `faster-whisper` 1.2.1 is installed in the OpenMontage venv, not in the backend's Python | small: same shape as `local_voice` |
| Model-based upscale | LANCZOS only; RealESRGAN aborted the server previously | needs a tiled graph proved on a small input first |
| Vision QC lane | `qwen2.5vl:7b` installed and captioning, but nothing in the pipeline calls it | medium: a "does this match the brief?" lane |
| Compose/typography | shipped 2026-10-16, not re-run in the recent passes | needs a real plate + quad preset |
| Piper voice | engine supported, no model file on disk yet | one model download (~60 MB) |

Recommended order: **transcription** (small, unblocks the reference-video path),
then the **Piper voice** (one file, big quality jump for narration), then
**vision QC**.

## What this does not claim

SAPI narration is serviceable, not ElevenLabs. The lane is honest about which
engine spoke, so nothing downstream can mistake a desktop voice for a studio one.
