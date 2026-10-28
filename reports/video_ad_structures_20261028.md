# 1.3 — VIDEO AD CREATION (TY SERVICE)
## Phase 2 research deliverable — REA program

**Date:** 2026-10-28
**Scope:** establish which parts of a short-form ad can be assembled
deterministically on this machine, catalogue the hook structures worth
automating, and put a real assembled clip on disk with ffprobe evidence.
**Method:** FFmpeg 9.0.2 (installed) + Piper narration (`local_voice.py`) +
published ad-structure sources. **Spend:** 0. **Amazon contact:** 0.

Evidence file: `reports/rea_probe/video/video_probe.json`
Clip: `reports/rea_probe/video/ad_15s_1080x1920.mp4`

---

## 1. What exists today

- `design-studio/VideoUgc.jsx` — a **planning** workspace: hook field (60 chars),
  duration validated against 6–45 s SB / 2–20 s store ranges, caption safe-area
  rules, synthetic-performer disclosure toggles, storyboard export via
  `buildStoryboardPack`. Generation is deliberately unarmed.
- `studio_generation.generate_video(narration=...)` — Wan 2.2 TI2V 5B lane
  (832×480, 49 frames, ~87.6 s measured 2026-10-22), optional local narration.
- `local_voice.py` — Piper (preferred) / SAPI fallback; `local_transcribe.py`
  (faster-whisper CPU); `local_vision.py` frame QC.

So the repo can *plan* an ad and *generate* a 2-second atmospheric clip. What it
cannot do is **assemble** an ad — which is the part that is deterministic, free,
and where the structure actually lives.

---

## 2. The deterministic / generative line (measured, not assumed)

| Capability | Deterministic (FFmpeg) | Needs a model | Evidence |
|---|---|---|---|
| Shot assembly, ordering, trims | **yes** | no | 3 shots concatenated |
| Ken-Burns move on a still | **yes** (`zoompan`) | no | 4 s in / 4 s out at 1080×1920 |
| Caption burn-in with a real font | **yes** (PIL overlay PNG) | no | 3 captions, y = 55 % of height |
| Narration | **yes** (Piper, local) | no | `engine=piper voice=piper` |
| Loudness normalisation | **yes** (`loudnorm`) | no | I=-14, TP=-1.5, LRA=11 |
| Vertical reframe from a still | **yes** (`scale`+`crop`) | no | 1080×1920 achieved without letterboxing |
| Product hero footage | no | **yes** | Wan lane exists but caps at 832×480 / 49 frames |
| Human performance / UGC | no | **yes** | not attempted |
| Music bed | no | no — **licensing** blocks it | see §6 |
| Beat-synced cutting | partial (fixed grid) | **yes** (beat detection) | not attempted |

**The line:** everything except *the footage itself* is deterministic. That
inverts the usual assumption that ad creation is a generative problem — the
generative part is one shot source, and the structure around it is arithmetic.

### The clip that proves it

| Property | Value |
|---|---|
| duration | 12.000 s |
| video | h264, 1080×1920, 30 fps, 1,753,582 bps |
| audio | aac, 11.99 s, 62,111 bps (Piper narration, loudness-normalised) |
| file | 2,737,719 bytes (2.74 MB) |
| shots | 3 × 4.0 s (zoom-in / pan / zoom-in) |
| captions | 3, placed at y = 1056 px (55.0 % of height) |
| sources | 1 real studio render + 1 label panel + Piper TTS |

That is an ad-shaped deliverable built with zero spend, zero provider keys and
no generative model.

---

## 3. Hook template catalogue

The published consensus is tight and consistent: the hook lands in **1–3 s**,
the body carries one promise, the CTA closes, and on-screen text carries the
message because autoplay is muted. The difference between the sources is
*which* hook archetype they name, so the catalogue below keeps the archetypes
and drops the adjectives.

Each template is a structure with editable slots, and each cites the sources
that actually show it.

### H1 — "Open on the payoff"
`[0.0–1.5]` show the finished result; `[1.5–3.0]` one line naming what it is;
`[3–10]` the mechanism; `[10–12]` CTA.
Instantiation: *"The label nobody reads" → "printed on the bag, not stuck on it"*
(this is the clip built in §2).
Sources: TrueFuture ("start on the evidence, action, result… do not begin with a
logo"), Vyra ("start on the moment I pull the print off the screen"), Clipping
Culture ("open on the payoff or the problem, never the lead-up").

### H2 — "Name the problem in the viewer's words"
`[0–2]` the frustration, stated plainly; `[2–6]` why it happens; `[6–12]` the
product resolving it, visibly.
Sources: Moonb ("open on a frustration the viewer knows in their body"),
Adligator ("problem→solution→CTA without losing attention").

### H3 — "The mistake"
`[0–2]` "you're doing X"; `[2–5]` the cost of X; `[5–12]` the correction.
Sources: Clipping Culture (formula #7 "flag the mistake"), Captions (mistake
hook named for Shorts).

### H4 — "Unsolicited proof"
`[0–2]` the number or the test, on screen; `[2–8]` how it was measured;
`[8–12]` CTA. Best fit for proof-heavy categories where the claim *is* the hook.
Sources: Adligator (proof part of the fixed structure), Creatify
(hook → problem → tension → solution → proof → CTA).

### H5 — "Before / after flash"
`[0–1.5]` before-and-after in one frame pair; `[1.5–3]` the delta named;
`[3–12]` how. Sources: the Medium/Billo write-up (before-and-after flash as the
hook), TrueFuture (start on the contrast).

**Counter-rules:** never open on a logo (three sources say so explicitly); one
sentence or one shot in the hook, not both unpacked; on-screen text must stay
up long enough to read (Vyra 2 s, this build 4 s).

---

## 4. Pacing: what is documented vs what was measured

| Fact | Value | Source type |
|---|---|---|
| Hook window | **1–3 s** | published consensus (5+ sources) |
| Structure | hook → value/proof → CTA | published consensus |
| Direct response length | **15–30 s** | vendor guidance (Adligator, Moonb) |
| Awareness length | **6–15 s** | vendor guidance |
| Amazon SB video range | **6–45 s** | already encoded in `VideoUgc.jsx:19` (registry-sourced) |
| Amazon store background | **2–20 s** | same |
| X video length | ≤ 15 s recommended, 2:20 supported | official (X spec, 2026-10-28) |
| TikTok recommended length | 21–34 s (TikTok's own SMB one-pager, surfaced via search) | vendor doc, **secondhand** |
| Shot length in the built clip | **4.0 s per shot, 3 shots** | **measured** (ffprobe) |

**Honest gap:** no 20–30-ad corpus was timed in this run. Ad libraries
(TikTok Creative Center, Meta Ad Library) are JS-rendered and timing a video
means playing it; the plan's "measure 20–30 timelines" step is *not* done. It is
specified below as an instrument rather than faked.

**The instrument for the build step:** the probe already emits per-shot durations
and total runtime as JSON. Pointing it at a downloaded ad (with the operator's
own rights) and reading the same fields gives a real timeline; that is a data
problem, not a research problem.

---

## 5. FFmpeg outlines (what to implement per template)

All chains below are the ones that actually ran in this probe, parameterised.

```
# shot (per still), vertical, no letterbox
ffmpeg -loop 1 -i shot.png -t 4 \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,
       zoompan=z='min(zoom+0.0008,1.18)':d=120:s=1080x1920:fps=30,format=yuv420p" \
  -c:v libx264 -preset veryfast -pix_fmt yuv420p shot.mp4

# concat (identical codec settings)
ffmpeg -f concat -safe 0 -i concat.txt -c copy base.mp4

# captions (PIL overlay PNG, kept out of the bottom 30 % UI band)
[0:v][cap0]overlay=0:1056:enable='between(t,0,3.9)'
[1:v][cap1]overlay=0:1056:enable='between(t,4,7.9)'
[2:v][cap2]overlay=0:1056:enable='between(t,8,11.9)'

# narration + loudness
[4:a]loudnorm=I=-14:TP=-1.5:LRA=11,apad[aout]
-c:a aac -b:a 128k -shortest
```

Per-template differences are data, not new code:

| Template | Shot count | Shot length | Caption policy | Audio |
|---|---|---|---|---|
| H1 payoff | 3 | 4 s | 3 cards, y 55 % | narration |
| H2 problem | 4 | 3 s | 4 cards, y 55 % | narration |
| H3 mistake | 3 | 4 s | 2 cards (hook + fix) | narration |
| H4 proof | 4 | 3 s | numbers as a card at 50 % | narration + on-screen figure |
| H5 before/after | 2 + split | 3 s + 6 s | 1 card | narration |

Deliberate omissions in the shipped probe: **no music** (licensing — §6), **no
transitions beyond hard cuts** (a cut is free; a transition costs a plugin or a
custom xfade graph and adds nothing to the hook), **no text animation** (each
animated caption is a render pass; the probe proves static captions first).

---

## 6. What cannot be automated (the non-empty list)

1. **Music.** Every usable track is licensed. A local music generator exists in
   the provider suite but its weights' licence is unverified → local bench only,
   and no output right now. Until then, ads ship with narration or silence.
2. **Human performance.** No UGC actor, no license, no model that produces a
   credible person ad.
3. **Hero product footage.** The Wan lane gives 832×480 / 49 frames. Usable as
   B-roll atmosphere; not usable as a hero shot that must read a label.
4. **Beat-synced cutting.** Needs beat detection over a licensed track — blocked
   by (1).
5. **Platform-native captions that follow speech timing.** `local_transcribe.py`
   can word-time a WAV; wiring that to caption timing is a build step, not
   research, and is listed below.

---

## 7. BUILD CANDIDATES

| id | component | change | evidence (report §) | effort | risk | gate |
|---|---|---|---|---|---|---|
| V1 | new `studio_video_assemble.py` | the §5 chain as a service: shots + captions + narration → mp4, returning ffprobe metadata | §2 measured clip | 4 h | low; FFmpeg is a local binary | none |
| V2 | `design_studio_async` job type | `video_assemble` alongside render/edit, same reserve→commit meter | §5 | 3 h | low | none |
| V3 | hook templates as data | H1–H5 with slot schemas, feeding the existing storyboard pack | §3 | 2 h | low | none |
| V4 | caption timing from audio | use `local_transcribe` word timings to place caption cards | §6 item 5 | 3 h | medium; ASR timing drift | none |
| V5 | `VideoUgc.jsx` | add "assemble from stills" alongside the plan-only workspace | §2 | 3 h | medium; UI change | none |
| V6 | music decision | either license a bed or state "narration only" in the UI | §6 item 1 | 0 (decision) | — | **spend** if licensing |

**Rejected:** generating the whole ad with Wan (resolution ceiling makes label
text unreadable); auto-posting to platforms (credentials + platform review).

## 8. UNVERIFIED

- Real ad-corpus pacing (no timelines were timed; §4 states this).
- TikTok's 21–34 s recommendation — seen secondhand through the search provider,
  not fetched from TikTok's PDF.
- Whether Wan footage is *acceptable* in an ad — 1 clip exists from 2026-10-22 at
  832×480; quality was not judged in this run.
- Any claim that a specific hook archetype outperforms another: every source
  asserting lift is a vendor blog, and none of their numbers were reproducible
  here. Treated as folklore; the templates are structural, not performance claims.
