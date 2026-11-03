# Creative services: the scan, what I improved, and the work order

**Date:** 2026-11-03 · **Task:** "fully scan the creative services… Northstar should be able to fully
create A+ content, social media, Amazon and product content, including all styles of generation —
YouTube Shorts, TikTok videos, and Amazon ad videos."

## 1. Scan (measured, per surface)

| Surface | Built | Proven by | Gap for "fully create" |
|---|---|---|---|
| **A+ content** | `aplus_render.py`: Amazon module geometry (tiles/bands/premium), text fit + tracking, contrast floor, band-variance check, `assert_perfect`, page composition, A+ pack for change files | **64 tests**; front-end parity tests assert canvas sizes and tile offsets match the Python geometry | none blocking. Needs a copy/brief pack per module style |
| **Product / listing images** | spec registry + main-image rules, canvas export (PNG, real PDF), asset pipeline, FLUX 3 via `studio_generation` | **2 live renders** (24.4 s / 25.6 s); text-safe path OCR-verified `text_free`, 0 boxes | **style prompt packs** (white-bg, lifestyle, flat-lay, macro, scale-shot) not systematised |
| **Ad stills** | `ad_formats.py`: 1:1 / 9:16 / 16:9 with placements (amazon-main, meta-feed, ig-story, reels, tiktok, shorts, sponsored-brand, display) | tests | placement *safe zones* missing for stills |
| **Social copy** | `social_pulse.py`: captions, hashtags, CTA, content calendar, review-request email, influencer outreach, caption scoring, brand voice | module tests | no **asset** generation alongside the copy (carousel frames, story frames) |
| **Vertical video** | `shorts.py` — image-to-video on Wan 2.2 TI2V 5B (on disk: 3.55 GB + umt5 + wan vae), frame-gated, returns WEBM + decoded frames; `POST /shorts` | lane code + package/verdict path | **single sampler call ≤ 81 frames (~2.7 s @ 30 fps)**. No stitching, no MP4/H.264, no captions, no audio |
| **YouTube Shorts / TikTok / Reels** | **NEW** `video_formats.py` + `GET /video-formats` + plan-driven `/shorts` | **9 tests**; live: 5 contracts; `seconds=30 → 422 video_needs_stitch (12 clips × 77 frames)` | real lengths need the stitch pipeline |
| **Amazon ad video** | **NEW** `amazon-ad-16x9` / `amazon-ad-9x16` presets, `verified: False` by design | preset tests | specs themselves are **unverified** (Amazon docs = standing gate) |
| **Captions / subtitles** | `local_transcribe.py` exists | — | not wired to video; no word-timed burn-in, no safe-zone placement |
| **Audio** | `local_voice.py`, `chat_voice.py` (TTS) | — | no voiceover track, no music bed, no ducking |
| **Hook / script** | `hookTemplates.js` (sourced: 3–5 word hook held ~2 s) | UI only | no server-side script → scenes → per-scene prompts planner |
| **Tooling** | `ffmpeg` + `ffprobe` present on PATH (`C:\Users\T2Hol\tools\ffmpeg\bin`) | verified now | unblocks stitching/muxing without new installs |

## 2. What I changed this pass

**`Northstar_backend/video_formats.py`** — five placement contracts, each carrying aspect, canvas,
fps, duration window, container/codec, size cap, UI **safe zones**, plus `source`, `verified` and
`checked`. Amazon's two are `verified: False` **on purpose**: reading Amazon specs is a standing gate,
so they render but must report `compliance.verified = false` rather than claim a compliance nobody
checked.

**`plan()`** turns a duration into sampler calls: 4n+1 frames, an 81-frame ceiling per call, clip
count, frames per clip, and `stitch_required`.

**`POST /shorts`** now takes `platform` + `seconds`. The contract is validated **before** the engine
check (a bad request is a 422 whether or not the GPU is armed), and a window that needs more than one
sampler call is **refused** with `422 video_needs_stitch` — the honest error instead of a 2-second clip
labelled as a 30-second TikTok.

Measured live: `GET /video-formats` → 5 contracts; `POST /shorts {platform: tiktok, seconds: 30}` →
`422 video_needs_stitch, 12 clips × 77 frames`.

## 3. Work order (in dependency order)

1. **Stitch pipeline** (~2 units, unblocks every length): per-clip renders → `ffmpeg` concat → H.264
   MP4 at the preset's fps/size, `ffprobe`-verified duration and bytes against `max_bytes`; write a
   manifest. Acceptance: a 15 s 9:16 MP4 whose probed duration is within ±1 frame and whose size is
   under the cap.
2. **Captions** (~2 units): `local_transcribe` → word-timed cues → burned-in caption layer placed
   inside the preset's safe zones, plus a sidecar `.srt`. Acceptance: OCR on a sampled frame finds
   the spoken words; nothing renders under the platform's UI strip.
3. **Audio** (~1 unit): TTS voiceover (`local_voice`) + a local royalty-free music folder + ducking.
   Acceptance: muxed track, verified non-silent, loudness normalised.
4. **Script → scenes planner** (~2 units): hook from `hookTemplates` + brand voice from
   `social_pulse` → N scenes with durations, per-scene prompts and on-screen text. Acceptance: a
   planner output whose scene durations sum to the requested preset window.
5. **Style prompt packs** (~1–2 units, parallel): per-surface prompt templates (A+ module, listing
   white-bg/lifestyle/macro, social story, ad) that always route through `text_safe` for packaging.
6. **Amazon spec verification** (operator): import the current Amazon ad-video spec via a doc upload
   or hand-off, then flip those presets to `verified: true` with the checked date.

Nothing on that list needs a download or a paid service. Items 1–3 are what turn "a 2-second clip"
into "a TikTok that ships".
