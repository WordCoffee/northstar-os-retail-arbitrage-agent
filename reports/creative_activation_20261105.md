# Creative services activation — 2026-11-05

Scope: bring the staged local creative pipelines up and prove they render, rather
than reporting them "unblocked" without evidence. Local ComfyUI only. No spend,
no paid credits, no Amazon, no credential read, no external provider.

## What was actually blocking

Not the licence, not the gate logic, not missing weights:

| check | result before |
|---|---|
| `MEDIA_GEN_LIVE` | not set |
| ComfyUI `:8188` | not running (connection refused) |
| GPU | idle, 0 MiB used of 16,303 MiB |
| disk free | 12.8 GB (floor is 10 GB) |

The lane was simply **not started**. Nothing needed unblocking beyond that.

One registry entry was also stale: `shared/provider-suite.json` marks
`flux3_klein` as `installed: "weights_missing"`. The gateway reports

```
{"status":"ok","model":"flux-3-image-klein",
 "weights":{"present":true,"missing":[],
            "unet":"...\\flux3-image-klein-nvfp4.safetensors",
            "text_encoder":"...\\qwen3vl_4b_int8_convrot.safetensors",
            "vae":"...\\flux2-vae.safetensors"},
 "steps":16}
```

so the marker is wrong. It is recorded as a backlog item rather than edited,
because `shared/` is outside the loop's commit allowlist.

## Activation

```powershell
powershell -NoProfile -File scripts/start-flux3.ps1     # ComfyUI :8188 + gateway :8190
$env:MEDIA_GEN_LIVE = "1"                                # arm for the process that renders
```

The starter checks the house resource floors and refuses rather than let Windows
kill a render halfway. `MEDIA_GEN_LIVE` is read per process, so arming is scoped
to the render and is not left on.

**Operational note:** do not pipe the starter's output (`... | Select-Object`).
The child processes inherit the pipe handle and the pipeline waits on them even
though the script itself has returned. Redirect to a file (`*> file`) or call it
with `Start-Process`.

## Render 1 — image (FLUX 3 Image Klein)

Prompt: *"A pristine blank kraft stand-up pouch, unprinted uniform matte
material, soft diffused studio key light from upper-left, seamless light-grey
background, 85mm product lens, eye-level three-quarter view"*

| measured | value |
|---|---|
| model | `flux3-image-klein-nvfp4` |
| size | 512 x 512, requested 512 x 512 (`fitted: false`) |
| seed | 424242 |
| wall clock | **30.2 s** |
| bytes | 343,069 |
| file | `reports/creative_activation_20261105/flux3_pouch_512.png` |

Verified with Pillow, not the return value: `format PNG, size (512, 512), mode
RGB`, mean RGB `(201.1, 185.9, 173.3)`, per-channel std `(26.0, 36.4, 49.8)` —
a warm kraft subject on a light ground with real structure, not a flat frame.
Visually confirmed: a clean unprinted stand-up pouch, no lettering, no logo,
which is exactly what the brief asked for.

## Render 2 — video (Wan 2.2 TI2V 5B)

Prompt: *"A pristine blank kraft stand-up pouch rotating slowly on a seamless
light-grey studio sweep, soft diffused key light, no lettering"*

| measured | value |
|---|---|
| model | `wan2.2-ti2v-5b-q5` |
| canvas | 512 x 480 |
| frames | 49 (4n+1 snap of a 2.0 s request) |
| duration | 2.0417 s |
| wall clock | **68.6 s** |
| bytes | 87,028 |
| file | `reports/creative_activation_20261105/wan22_pouch_2s.mp4` |

Verified with `ffprobe`, not the return value: `codec_name h264`, `width 512`,
`height 480`, `nb_frames 49`, `duration 2.041667`.

Audio is `null` on this render because no narration was requested — a silent
clip, correctly reported as silent rather than passed off as narrated.

## Why the lane is stopped again

ComfyUI was stopped after the proofs (`start-flux3.ps1 -Stop`; GPU back to
0 MiB). This box has one 16 GB card that the assistant's brain also needs, and a
resident runtime blocks model loads. Activation is one command, not a daemon.

## What this does not prove

- No prompt-author refinement was exercised: that path needs the local 27B author
  on `:8080`, which is a separate process and was not started.
- No multi-clip video, no narration, no captions, no print master, no upscale.
  Those are separate lanes with their own gates.
- No quality claim beyond "the render is a real image of the requested subject".
  Legibility and prepress checks are `mockup_quality` / `print_prep` territory.

## Gates held

No spend, no paid credit, no Amazon, no credential read, no provider call, no
policy or allowlist edit. `MEDIA_GEN_LIVE` was set only inside the render
processes and was not persisted.
