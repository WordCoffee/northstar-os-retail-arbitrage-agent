# Creative pipeline: why the output is not production quality, and the plan

**Work order:** review the creative pipeline, refine it; the images and videos produced recently are not
production quality. **Method:** measured the existing pipeline, then researched GitHub + Hugging Face for
what is actually available locally. **Date:** 2026-11-03.

---

## 1. Diagnosis — four defects, all measured

| # | Defect | Evidence |
|---|---|---|
| **a** | **The product is invented, not referenced.** Every render is text-to-image: FLUX 3 draws *a* pouch from a description, so it is never *your* pouch. | the mushroom-coffee brief returned a generic kraft pouch; the lion's mane brief returned a different one again |
| **b** | **Diffusion invents lettering.** Anything more than a blank plate gets gibberish packaging copy. | measured: `APBDE MUSOROM COFFEE` on a "no text" brief. Worked around with `text_safe` + OCR, which is correct but means every render is a blank plate |
| **c** | **No detail stage.** Output stops at 1024². RealESRGAN x4 enlarges; it does not recover detail or material realism. | 1024×1024 PNG, 25 s; no refine pass exists |
| **d** | **Video is a stub of the format.** Wan 2.2 TI2V **5B**, one sampler call ≤ 81 frames (~2.7 s @30 fps), no motion control, no start/end frame, no audio, no upscale. | `POST /shorts` refuses anything longer with `video_needs_stitch` |

There is also **no automated quality score**, so a weak render can only be rejected by eye.

## 2. The finding that changes the plan

**FLUX 3 Image Klein — the model already installed — supports multi-reference conditioning (up to 10
images) and bounding-box placement. The pipeline uses it as text-to-image only.** Feeding the real
packshot as a reference is the direct fix for defect (a), and it costs **0 GB of downloads**.

Two more facts that reset priorities:

- **The binding constraint is 16 GB of system RAM, not VRAM.** Any stack whose weights + text encoder
  exceed ~14 GB total pages to disk on this box. Two-model workflows (render → free → refine) are the
  only reliable pattern here.
- **Licences eliminate half the "obvious" candidates** — FLUX.1 Kontext/Fill dev, FLUX.2 dev, Redux dev
  are non-commercial; SUPIR is proprietary; MMAudio's weights are CC-BY-NC.

## 3. The plan

### Phase 0 — Reference conditioning and a ship gate (0 GB, no licence change)

1. **Use the reference lane.** Extend `studio_generation` + `POST /generate` to accept
   `reference_assets[]` (the real product photo, the label artwork) and an optional placement box, and
   pass them to Klein's multi-reference conditioning. Text stays a *description*; the reference carries
   identity.
2. **Compose, don't diffuse, the typography.** Keep the vector-text composite (`tools/render_mogra_label.py`
   is the pattern) over the reference render, then the existing OCR check.
3. **Add the ship gate** (`mockup_quality.py`): PickScore (MIT) for prompt adherence + HPSv2 (Apache-2.0)
   for a human-preference floor + SSIM/pHash against the real product photo + the OCR text check. CPU,
   ~5.5 GB on disk, **0 VRAM**. A render that fails is refused, not delivered.
4. **Acceptance:** `renders/mogra_lions_mane/product_front.png` / `product_back.png` produced by the API,
   reference-conditioned, 2000px, passing the gate. Same three probes queued today
   (`t10` composite, `t11` legibility, `t12` plate refusal) become the mechanical half of it.

### Phase 1 — A real detail stage (3.16 GB)

**SeedVR2 3B fp8 (Apache-2.0, 3.16 GB)** — one-step restoration, native ComfyUI nodes, BlockSwap/VAE
tiling for 16 GB. This is the honest path from 1024² to a 2000px packshot. RealESRGAN stays as a cheap
pre-scale. Rejected: SUPIR (commercial licence), FLUX Fill dev (non-commercial).

### Phase 2 — Video that is actually a video (~10 GB)

1. **Wan 2.2 **A14B** (Apache-2.0)** Q4/Q5 experts loaded sequentially, **FLF2V chaining**: each 5 s shot's
   last frame becomes the next shot's first frame, then SeedVR2 to 1080p. Fits 16 GB, 81 frames per call,
   start+end frame control.
2. **VACE-Fun A14B** for reference-to-video and mask edits (the product stays the product across shots).
3. **Optional, only if one-pass length + audio is worth the licence:** LTX-2.3 distilled Q4 (~12 GB,
   LTX-2 Community licence: commercial allowed **under $10M revenue**, no-compete and no-training
   clauses) gives up to ~20 s at 50 fps **with synchronised audio** in one pass. It is the only candidate
   that removes the stitch step. Decision needed from you (see §6).
4. Audio: LTX-2's built-in AV track first (free, in-sync); Stable Audio Open 1.1B (Stability Community,
   <$1M revenue, CC-BY) for music beds ≤47 s. **MMAudio is out** (CC-BY-NC weights).

### Phase 3 — Make it a loop, not a script

Wire the ship gate into the creative lane so **best-of-N** is automatic: render 2–3 variants, score them,
keep the winner, record the rejects with their scores. That is how "quality" becomes a number the
autonomous loop can optimise instead of an opinion.

## 4. What we already have that is a keeper

- `text_safe` + OCR text-free verification (the only correct answer to diffusion lettering).
- Vector label rendering at 300 dpi (`tools/render_mogra_label.py`).
- Vector typography >> generated typography, permanently.
- `ad_formats` / `video_formats` placement contracts with declared `verified` flags.
- ffmpeg/ffprobe for stitching and verification.

## 5. Licence ledger (record every download in `provenance.csv`)

| Use | Model | Licence | Size | Note |
|---|---|---|---|---|
| Render | FLUX 3 Image Klein *(installed)* | FLUX Kommunity — <$5M rev, owner attested 2026-10-28 | 4.92 GB | reference + bbox, already installed |
| Detail | SeedVR2 3B fp8 | Apache-2.0 | 3.16 GB | **to download** |
| Video | Wan 2.2 A14B Q4/Q5 | Apache-2.0 | ~18 GB (two experts) | **to download** |
| Video (optional) | LTX-2.3 distilled Q4 | LTX-2 Community, <$10M rev, no-compete | ~12 GB | **decision** |
| Audio (optional) | Stable Audio Open 1.1B | Stability Community, <$1M rev, CC-BY | 4.52 GB | **to download** |
| Gate | PickScore / HPSv2 | MIT / Apache-2.0 | 5.5 GB | **to download** |
| **Avoid** | FLUX.1 Kontext/Fill dev, FLUX.2 dev, Redux dev, SUPIR, MMAudio, CLIP-IQA (S-Lab) | non-commercial / proprietary | — | do not install |

Disk: 58 GB free; Phases 0–1 need ~9 GB, Phase 2 adds ~30 GB. Fits, with the 10 GB floor respected.

## 6. Decisions I need from you

1. **Downloads** — approve ~9 GB (Phase 0–1) and then ~30 GB (Phase 2). Everything is local and free.
2. **LTX-2 licence** — its community licence allows commercial use under **$10M revenue** with a
   no-compete clause. You already attested T2 Holdings is under $5M for the FLUX Kommunity Licence; the
   same statement covers this, but it is your call whether you want a second licence with a no-compete
   clause in the stack.
3. **Quality bar as a number** — I will set the first thresholds from a scored baseline of your own
   reference images, then show you the scores. If you want a higher bar, it is a number, not a rewrite.

## 7. What happens first

Phase 0, this week, no downloads: reference conditioning + bbox + ship gate + the three probes already
queued. The first measurable outcome is a `product_front.png` of **your** pouch — reference-conditioned,
2000px, scored, with the vector label composited — instead of a plausible stranger.

## Addendum (2026-11-04): LTX-2.3 investigated - it does not fit yet, and not because of disk

Owner asked for LTX-2.3 anyway ("best we can get"). Research estimate said ~12 GB; the real model is
**22B**, so that figure was the Q4 of a much smaller assumption. Measured from the HF API:

| Piece | Repo | Size |
|---|---|---|
| distilled checkpoint Q4_K_M | `unsloth/LTX-2.3-GGUF` (`distilled-1.1/�-Q4_K_M.gguf`) | **13.22 GB** (Q4_K_S 12.07) |
| text projection | `Kijai/LTX2.3_comfy` | 2.15 GB |
| video VAE + audio VAE | `Kijai/LTX2.3_comfy` | 1.35 + 0.34 GB |
| fp8 transformer (alternative) | `Kijai/LTX2.3_comfy` | 21.9-23.5 GB |
| fp8 (official) | `Lightricks/LTX-2.3-fp8` | 27.5 GB |
| **text encoder** | **not in any accessible repo** | � |

`Comfy-Org/LTX-2_ComfyUI` (the repo that would carry the encoder and the audio path) returns **401 -
gated**. `Comfy-Org/ltx-2.3` carries only LoRAs (6 files). So the minimal runnable set is ~16 GB of
weights *plus* a Gemma-3-class text encoder that is not obtainable today without an HF token.

Two independent blockers, neither of them the SSD:
1. **Gated weights** - need an HF token with access, or a mirror.
2. **16 GB system RAM** - a 13 GB checkpoint plus an 8-24 GB encoder cannot be resident; ComfyUI would
   spend the render swapping. Disk is 31.1 GB free and would take the checkpoint, but a model that
   cannot load is not "the best we can get", it is 16 GB of dead weight.

**Decision:** do not fetch LTX-2.3 yet. Proceed with Wan 2.2 A14B chained shots (already downloaded,
Apache-2.0) for video, and add **Stable Audio Open 1.1B (4.52 GB, Stability Community, <$1M rev)**
for audio beds - that is the achievable version of "length + audio". Revisit LTX-2.3 when (a) an HF
token unlocks the gated repo and (b) RAM is 32 GB or the model can stream from the new SSD.

## Correction (2026-11-04): I was wrong about FLUX 3, and the plan gets cheaper

The operator challenged my claim. Research against BFL docs, the HF org and the Klein ComfyUI repo
shows the claim was wrong in four ways:

| I said | Actually |
|---|---|
| "only a 1024x1024 generator" | Klein is documented **up to 4K** - the `4k` tier is an equal-area class up to **16.8 MP** (w/h 64-6256). 1024 is only our template default. |
| "no reference conditioning" | **Up to 10 reference images**, addressed positionally (`<ref_image_0>`...). The Klein ComfyUI repo ships `mi2i` (multi-image-to-image) graphs. |
| "text-to-image only" | Repo ships `t2i`, `i2i` and `mi2i`, in int8 and bf16, for both klein and base - **12 workflow files**, plus 5 reference JPEGs. |
| "FLUX 3 does no video" | **FLUX 3 Video** does t2v/i2v/v2v, 5-20 s, keyframes, synchronised audio - but it is **API/private weights only**, so not available on this box. |

Verified directly: `black-forest-labs/flux-3-image-klein-comfy` (gated auto) contains
`flux3_klein_int8_{t2i,i2i,mi2i}.json` and the bf16/base variants. Our installed 4.92 GiB nvfp4 file is
the **DiT only**; the Qwen3-VL-4B encoder (4.86 GB int8) and FLUX.2 VAE are already on disk too.

### What this changes

- **Reference conditioning and 4K are available with the weights we already have.** The graph we built
  is a text-to-image template; the capability was never missing. Phase 0 is: install the `mi2i` graph,
  raise the canvas to a real 4K class, feed the product photo as `<ref_image_0>`, composite vector text.
- **SeedVR2 is demoted for stills** (Klein renders native 4K); it stays useful for **video** upscale.
- **Video remains Wan 2.2 locally.** FLUX 3 Video is the better model and the honest answer to "FLUX 3
  does video" - it is simply not open-weights, so using it would mean a cloud lane and a spend gate.
- The earlier "~12 GB LTX" note stands as corrected: LTX-2.3 is 22B and gated; that decision is unchanged.

Lesson recorded: I generalised from a template we wrote to a claim about the model. Capability claims
come from the model card and the shipped workflows, not from our own graph.
