# Local Video / Audio Services — Discovery & Implementation Plan

Date: 2026-10-08. Status: **PROPOSED** — nothing here is implemented or run yet.
Paid/cloud video paths remain disabled. This plan reuses the existing shared
creative stack (queue, provenance, registry, storage) and does not build a
parallel stack.

## 1. Infrastructure audit (what already exists)

| Area | Existing | Status |
|---|---|---|
| Job queue / worker | `Northstar_backend/creative/jobs.py` (single heavy worker, cancellation, persistence, stage progress) | **WORKING** |
| Provenance | `creative/provenance.py` (JSON sidecars, SHA-256, license notices) | **WORKING** |
| Model/workflow registry + router | `creative/registry.py`, `creative/router.py` | **WORKING** (image lanes) |
| Media storage / export | `creative/storage.py` (local + S3), `creative/bundles.py` (zip) | **WORKING** |
| Runtime | ComfyUI 0.38.0 — has **Wan / Hunyuan video nodes** and **audio VAE/`SaveAudio` nodes** | **AVAILABLE** |
| STT (speech→text) | `server/voice-transcribe.cjs`, `functions/api/transcribe.js`, `components/voice-*.js` | **WORKING (specialist)** |
| Video generation (local) | none installed | **MISSING** |
| Video editor / timeline / captions | none | **MISSING** |
| TTS / narration | none installed (STT only) | **MISSING** |
| Music / SFX generation | none installed | **MISSING** |
| Audio mixing | none | **MISSING** |
| ffmpeg / ffprobe | **not on PATH** | **MISSING prerequisite** |
| Cloud video (fal Wan/Kling/Veo) | `creative/video.py` (catalog, cost, request builder, armed submit) | **INFRASTRUCTURE-ONLY, GATED, OFF** |

Disk free at planning time: **35.4 GB** (tight — see §4).

## 2. Candidate models and exact commercial permissions (verified 2026-10-08)

| Role | Model | License | Commercial | Verdict |
|---|---|---|---|---|
| Image→video (primary) | **Wan-AI/Wan2.2-TI2V-5B** (also T2V/I2V-A14B, S2V-14B) | **Apache-2.0** | allowed | **APPROVE** — 720p@24fps, runs on 4090-class |
| Image→video (alt) | Lightricks/LTX-Video | LTXV Open Weights License | allowed **only under $10M/yr revenue**; else paid | **CONDITIONAL** — not the default |
| Image→video (alt) | stabilityai/stable-video-diffusion-img2vid-xt | Stability AI Community License | allowed under **$1M/yr revenue**, registration required, revocable | **CONDITIONAL** |
| Narration / TTS | **hexgrad/Kokoro-82M** | **Apache-2.0** | allowed | **APPROVE** (primary) |
| Music | **ACE-Step/ACE-Step-v1-3.5B** | **Apache-2.0** | allowed | **APPROVE** (primary) |
| Music | facebook/musicgen-* | weights **CC-BY-NC-4.0** | **prohibited** | **REJECT** |
| Voice cloning | (any) | varies | not verified | **OUT OF SCOPE** until verified |

Notes: Wan/ACE-Step/Kokoro licenses verified from their Hugging Face/GitHub
primary sources. LTX and SVD are revenue-gated and therefore quarantined from
production routing by default (consistent with the image-side policy).

## 3. Implementation plan (phased)

### Phase V1 — image-conditioned short clips (local)
- New capability `video` in `creative/router.py`; lane `wan-ti2v-5b` (family
  `wan`, Apache-2.0). Registry entries for the Wan diffusion model, text encoder,
  and VAE.
- New `creative/video_stages.py` (or `stages_video.py`): build a ComfyUI
  `WanImageToVideo` graph (image + prompt → latent → KSampler → VAEDecode →
  `SaveAnimatedWEBP`/frames), driven by the same `comfy_client` runtime.
- **Model-specific frame-count/duration handling:** each lane declares
  `fps`, `frame_step` (4n+1), `max_frames`, and native resolution (Wan TI2V-5B:
  24 fps, 121-frame / ~5 s default at 1280×704). The builder clamps requested
  duration to the model's native frame grid and records the actual frame count.
- Output: a sequence of frames + an intermediate video; provenance sidecar.

### Phase V2 — clip quality validation & selective regeneration
- Per-clip objective checks (no diffusion re-run): decode, frame count/fps,
  duration, resolution, black/frozen-frame detection, optional CLIP/SSIM drift
  vs the source frame.
- A `video_plan` object lists clips; failing clips are flagged and only those are
  regenerated (bounded retries, recorded). Rejections are recorded, never hidden.

### Phase V3 — timeline assembly + branding (ffmpeg)
- **Prerequisite:** install a free ffmpeg/ffprobe build (LGPL/GPL; commercial use
  permitted). No paid tooling.
- `creative/video_assemble.py`: concat clips in order, apply transitions (hard cut
  default), overlay the deterministic brand lockup (reuse `exact_text`), burn
  captions, and export H.264 MP4 + a poster frame. Emits provenance.

### Phase V4 — narration (TTS)
- `kokoro-tts` lane (Apache-2.0). Script text → WAV per segment. Deterministic
  text (same rule as images: the model never invents brand copy).

### Phase V5 — captions
- Deterministic: derive captions from the script text with timings (preferred,
  exact). Fallback: STT of the narration via the existing `voice-transcribe`
  service (already working) to time-align. Both produce an SRT; ffmpeg burns them.

### Phase V6 — approved music / SFX
- `ace-step-v1` lane (Apache-2.0) for original music; SFX from an approved,
  commercially-licensed local library (owner-provided or CC0). No MusicGen.

### Phase V7 — audio mixing + final export
- ffmpeg: narration as primary; music ducked under narration (sidechaincompress),
  −14 LUFS normalization; brand overlay + captions burned; final MP4 + metadata.

### Phase V8 — shared queue / provenance integration
- All of V1–V7 run as shared tasks (`video_generate`, `video_assemble`) through
  `creative/jobs.py` (single heavy worker, cancellation via `/interrupt` for the
  ComfyUI stage, stage progress), writing `creative/provenance.py` sidecars with
  model/license/params/frame counts and output SHA-256. Approved-component policy
  and explicit routing apply; LTX/SVD stay quarantined.

## 4. Disk / resource planning

- Wan2.2-TI2V-5B weights + VAE + text encoder: ~10–12 GB.
- ACE-Step v1: ~8.3 GB. Kokoro: ~0.36 GB. ffmpeg: ~0.1 GB.
- Total ~19–21 GB against **35.4 GB free** — feasible but must be sequenced;
  remove nothing from user data.

## 5. Definition of done (not met yet)

Video is **not** complete until a real local job produces a verified finished
video containing the requested clips, narration, captions, and branding — with a
provenance sidecar and passing objective checks. Independent stage tests do not
count as completion.

## 6. Paid/cloud posture

`creative/video.py` remains gated and OFF (`FAL_KEY` absent, `MEDIA_GEN_LIVE`
unset). This plan uses only local, commercially-compatible components.
