# Video-generation ecosystem scan — 2026-10-21

Goal: find what can improve our 5–10 second ad-clip pipeline, local (16 GB laptop
GPU) and in production. This is an inventory and a shortlist — **nothing here was
run or installed**, so capability claims are marked as such.

## Scan

| source | rows | method |
|---|---|---|
| Hugging Face | **38,129 models** | 42 search/pipeline passes, cursor-paginated, deduped |
| GitHub | **300 repos** | REST search, 28 queries — **stopped at HTTP 403** (unauthenticated cap: 10 req/min, 60/hour) |
| **total** | **38,429** | |

The GitHub cap is the only reason this is not a 20,000-repo sweep: the
unauthenticated search budget blocks after a few requests. `gh auth login`
(one interactive command, no secret ever printed) raises it to 30 req/min, which
makes 28 queries × 10 pages ≈ 20,000 repos a ~9-minute job. Re-run:

```
gh auth login
python tools/scan_video_ecosystem.py            # GitHub + Hugging Face
python tools/scan_video_ecosystem.py --wide     # + broad paginated pass
python tools/analyse_video_scan.py              # ranking table
```

Classification of the HF inventory:

| class | count |
|---|---|
| generation models (t2v/i2v/v2v) | 10,534 |
| adapters / LoRAs | 2,641 |
| support (VAE, interpolation, upscale, tokenizer) | 287 |
| video understanding | 56 |
| noise (classification, CLIP, VidLLM) | 6,306 |
| other | 18,305 |

Dumps live in `reports/video_scan/` (`huggingface.jsonl` is 16.7 MB and is
git-ignored; it is fully regenerable from the script).

## We already own the workhorse — zero download

ComfyUI **0.40.0** ships native `nodes_wan.py`, and the complete 5-second 720p
image-to-video stack is already on disk:

| file | size |
|---|---|
| `unet/Wan2.2-TI2V-5B-Q5_K_M.gguf` | 3.55 GB |
| `vae/wan2.2_vae.safetensors` | 1.31 GB |
| `text_encoders/umt5-xxl-encoder-Q5_K_M.gguf` | 3.86 GB |
| **working set** | **≈ 8.7 GB** |

Wan 2.2 is **Apache-2.0**. We can generate clips today without downloading
anything — that is the shortest path to the 5–10 clip requirement.

Also owned: `seedvr2_3b_fp8` + its VAE (video/image restoration — our 1080p
finisher).

## Shortlist

Ranked by fit for *our* job (short product clips from stills), not by hype.

| # | model | licence | size / fit | role | verdict |
|---|---|---|---|---|---|
| 1 | **Wan 2.2 TI2V-5B** | Apache-2.0 | 8.7 GB, owned | 121 frames @ 720p from a still | **run first** |
| 2 | **SeedVR2 3B** | Apache-2.0 | owned | restore + 1080p finish | **use in the same pass** |
| 3 | **RIFE / FILM** | MIT | ~0.2 GB | 24 → 48 fps interpolation | add if motion looks choppy |
| 4 | **Wan 2.2 I2V-A14B** (GGUF) | Apache-2.0 | ~9–10 GB + offload | better motion/detail | second wave |
| 5 | **Wan2.2-Animate-14B / S2V-14B** | Apache-2.0 | 14B, offload | drive a character from video / speech → talking head | testimonial-style ads |
| 6 | **HunyuanVideo 1.5** | Tencent "other" | "lightweight" per repo | quality tier | licence review first |
| 7 | **LTX-2.5** | Lightricks "other" | 22B distilled variants exist | fastest family, **8,729 likes — the most-liked open model in the scan** | cloud/production candidate, licence review |
| 8 | **MiniMax-H3** family | upstream "other"; many Apache-tagged repacks | many quantised sizes | fast i2v family | verify upstream licence before selling |
| 9 | Mochi 10B, SVD, AnimateDiff, Open-Sora, Allegro, SkyReels | mixed | — | — | superseded; skip |

Licence summary: **Apache-2.0** (Wan 2.1/2.2, VACE, Animate, SeedVR2, Helios,
Lance) is safe to build a paid product on. **"other"/NOASSERTION**
(LTX-2.x, HunyuanVideo 1.5, MiniMax-H3, SVD) needs the actual terms read before
it touches a customer deliverable — the same gate we applied to Swift 1.5.

## GitHub rows worth knowing (of the 300 captured)

| repo | stars | licence | note |
|---|---|---|---|
| `huggingface/diffusers` | 34,775 | Apache-2.0 | the integration surface for every model below |
| `Tencent-Hunyuan/HunyuanVideo-1.5` | 4,577 | NOASSERTION | "a leading **lightweight** video generation model" |
| `genmoai/mochi` | 3,752 | Apache-2.0 | Apache but heavy (10B) |
| `PKU-YuanGroup/Helios` | 2,219 | Apache-2.0 | real-time **long** video generation |
| `bytedance/Lance` | 1,360 | Apache-2.0 | 3B-active unified image+video model |
| `Wan-Video/Wan2.2` | — | Apache-2.0 | the model we own |
| `Lightricks/LTX-Video` | — | other | fast DiT family |

## Recommended pipeline for 5–10 clips

1. **Still** from the existing product-image lane (accurate packaging, no invented text).
2. **Wan 2.2 TI2V-5B**: 121 frames, 704×1280 or 1280×704 → one 5 s clip.
3. **RIFE** 24 → 48 fps (optional; hides the low frame rate on pans).
4. **SeedVR2** finish → 1080p.
5. **ffmpeg** assembly: title card, beat-aligned cuts, music bed, burned captions,
   loudness normalisation — all local, already installed (ffmpeg 9.0.2).
6. Deliver 5–10 clips per job.

Every step is local and free; the only variable cost is time on the GPU.

## The constraint that decides the architecture: one GPU, one tenant

The brain holds **13 GB**; the Wan stack needs **≈ 8.7 GB**. Together that is
**21.7 GB on a 16.3 GB card** — they cannot co-reside.

So video rendering must take a **VRAM lease**: unload the brain
(`keep_alive: 0`, the pattern already used in `studio_generation.py`), render,
then let the brain reload (~8 s). The UI must say *"rendering — chat paused"*
rather than silently timing out, and the queue must never start two renders at
once.

## Pricing alignment

`creative_pricing.py` already prices video: `video_short` (15 s) and
`video_long` (60 s), with a `video_wan_15s` unit cost of $0.75 per pass
(1 pass draft / 2 final for short; 4 / 6 for long). A 5–10 clip job is 25–50 s,
which falls **between** those two products. Add a `clip_pack` job (5×5 s and
10×5 s) so the quote the customer sees matches what we actually deliver.

## Next step (one acceptance test)

Single run, then decide: **one real product still → Wan 2.2 TI2V-5B → 5 s 720p**,
measuring wall time, peak VRAM, and the brain-unload/reload handoff. If it holds,
batch 5 clips and wire the lane behind the existing `media: "video"` switch.
Not done yet — this report is the inventory, not the benchmark.
