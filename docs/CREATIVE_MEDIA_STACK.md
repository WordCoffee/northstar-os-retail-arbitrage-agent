# CREATIVE MEDIA STACK — Quality-Cheap (2026-09-22)

> Scope: product pictures, ad videos, presentations, UGC content, YouTube Shorts /
> TikTok. Goal: best quality-per-dollar (Sept-2026 list rates, per-usage, no
> subscriptions). Cited by `shared/model-suite.json`. Iterate on the cheap tier,
> render final on the top tier — 90% of cost is rejected drafts otherwise.

## TL;DR stack

| Asset type | Primary (quality) | Budget / iteration tier | Cost |
|---|---|---|---|
| Product pictures | **FLUX.2 [pro]** via fal/Replicate | FLUX.2 [klein 9B] drafts | $0.03 / $0.015 per img |
| Product edits / composites | **FLUX.2 [pro] edit** via Replicate | Nano Banana edit | ~$0.055 / $0.04 per edit |
| Ad creatives with lots of text | **GPT Image 2** via OpenRouter | Nano Banana 2 (Gemini 3.1 Flash Image) via fal | ~$0.05–0.13 / $0.08 per img |
| Presentations | FLUX.2 pro for imagery + native slide text | klein 9B for concepts | $0.03 per img |
| Ads / shorts / TikTok | **Kling 2.6 Pro** via fal | FLUX 3 draft (free 5/day) + Wan 2.5 | $0.07–0.14/s |
| Premium / hero video | Veo 3.1 (fast) via fal | Veo 3.1 standard | $0.10–0.40/s |

## Per-job detail

### Product pictures (photorealism)
- Best photoreal quality-per-dollar: **FLUX.2 [pro], $0.03/1MP** (identical on fal / Replicate / BFL direct).
- Draft pipeline: **FLUX.2 [klein 9B], $0.015/img** (or klein 4B $0.012–0.014). ~30–50% of batches can be approved from klein.
- Consistency across a product line: **FLUX.2 [pro] edit** with a reference image (Replicate ~$0.055) — keeps packaging/logo consistent.
- Keep resolution at 1–1.5MP (1024–1536px). 4MP is 4x the price and mostly unnecessary for web/commerce.

### Ad creatives with lots of text
| Model | Where | Cost/img | Text quality |
|---|---|---|---|
| Gemini 3.1 Flash Image ("Nano Banana 2") | fal | $0.08 | Excellent; character-by-character typography |
| Nano Banana Pro (Gemini 3 Pro Image) | fal | $0.15 | Better on dense/multi-line ad layouts |
| GPT Image 2 | OpenRouter | ~$0.05–0.13 | Best-in-class text-in-image + prompt adherence |
| FLUX.2 (any tier) | fal/Replicate | $0.014–0.07 | Trails GPT/Gemini on text — skip for copy-heavy ads |

Default ad-text renderer = **GPT Image 2 on OpenRouter**; secondary = **Nano Banana 2 on fal**
($0.08). Note: all Nano Banana outputs carry Google **SynthID** (invisible watermark).

### Presentations
- Imagery: FLUX.2 pro ($0.03). Slide body text stays in the deck tool — don't pay image models to render body text.
- Full-slide hero images with baked-in caption text: Nano Banana 2 ($0.08) or GPT Image 2 for longer phrases.

### Video (fal, per-second)
| Model | fal price | 5s | 15s (Short/TikTok) | Best for |
|---|---|---|---|---|
| Wan 2.5 | $0.05/s | $0.25 | $0.75 | Budget motion, simple scenes |
| FLUX 3 draft | ~$0.06/s (5 free/day sandbox) | $0.30 | $0.90 | Fast iteration, storyboards |
| Kling 2.6 Pro | $0.07/s (no audio) / $0.14/s (audio) | $0.35–0.70 | $1.05–2.10 | **UGC/shorts with real people + native audio** |
| Kling v3 (i2v) | $0.112/s | $0.56 | $1.68 | Image→video product shots |
| Veo 3.1 fast | $0.10/s | $0.50 | $1.50 | Hero-quality premium ads |

- **UGC + Shorts/TikTok: Kling 2.6 Pro** — native 9:16, realistic people. 15s talking-style ≈ $1.20–2.10.
- **Product motion**: shoot-to-video from a FLUX.2 pro still via Kling v3 i2v ($0.56/5s) or Wan 2.5 ($0.25).
- **Drafts/moodboards**: FLUX 3 draft — free daily allowance on the fal sandbox, else $0.06/s.
- Voiceover is noise in the budget: ElevenLabs v3 ~$0.03 / Deepgram Aura-2 ~$0.007 on a ~$2 clip.

## Provider plan (one key per provider)
1. **fal.ai** — primary: FLUX.2 images, Kling 2.6/v3, Wan 2.5, Veo 3.1, Nano Banana 2 (image+video, per-usage).
2. **OpenRouter** — text + vision understanding + GPT Image 2 (text-heavy ad finals).
3. **Replicate** — optional mirror for FLUX.2 pro/edit; identical pricing, useful fallback.

## Cost levers (10x, not 10%)
1. **Stage your renders** — klein 9B / FLUX 3 draft / Wan for iteration → FLUX.2 pro / Kling 2.6 / Nano Banana 2 for final.
2. **Resolution budget** — 1MP unless a deliverable needs more (4MP = 4x).
3. **Batch with num_images** — 1–4 per request; parallelize and pick winners.
4. **Keep video to 5s units** — generate 5s clips, extend/assemble in the editor; per-second cost scales linearly.
5. **Free/eval allowances** — fal's 5 free FLUX 3 draft videos/day for ideation.
6. **Don't conflate text need with cost** — copy-heavy ads → GPT Image 2 / Nano Banana 2; image-first product shots → FLUX.2 pro.

## Compliance flags
- **Nano Banana / Nano Banana 2 / Nano Banana Pro** and **Veo 3.1** outputs carry **SynthID** (Google) — disclose AI generation where required. Kling (fal) paid API output has no forced watermark.
- Replicate = pay-per-output for FLUX.2 pro (no idle-time surprises).

## Mapping to the suite tiers
- **V1** draft = FLUX.2 klein 9B → final FLUX.2 pro
- **V2** = FLUX.2 pro (+ edit) for product/presentation stills
- **V3** = GPT Image 2 / Nano Banana 2 for ad visuals, A+, UGC, text-heavy graphics
- **Video** = Wan (capped) + Kling 2.6 Pro / Veo 3.1 (usage-metered add-ons)
