# Creative Media Stack — Quality-Cheap Recommendation (2026-09-22)

Scope: product pictures, ad videos, presentations, UGC content, YouTube Shorts / TikTok.
Goal: best quality-per-dollar. Prices are Sept 2026 list rates, per-usage, no subscriptions.

## TL;DR Stack

| Asset type | Primary (quality) | Budget / iteration tier | Cost |
|---|---|---|---|
| Product pictures | **FLUX.2 [pro]** via fal or Replicate | FLUX.2 [klein 9B] drafts | $0.03 / $0.015 per img |
| Product edits / composites | **FLUX.2 [pro] edit** via Replicate | Nano Banana edit | ~$0.055 / $0.04 per edit |
| Ad creatives with lots of text | **GPT Image 2** via OpenRouter | Nano Banana 2 (Gemini 3.1 Flash Image) via fal | per-token; ≈$0.04–0.17 est* / $0.08 per img |

\* GPT Image family is **token-billed, not per-image** — see verification note below; do not trust a hardcoded per-image figure in config until verified.
| Presentations | FLUX.2 pro for imagery + native slide text | klein 9B for concepts | $0.03 per img |
| Ads / shorts / TikTok video | **Kling 2.6 Pro** via fal | FLUX 3 draft (free 5/day) + Wan 2.5 | $0.07–0.14/s |
| Premium / hero video | Veo 3.1 (fast) via fal | Veo 3.1 standard | $0.10–0.40/s |

Rule of thumb: **iterate on the cheap tier, render final on the top tier.** 90% of cost is spent on rejected drafts otherwise.

## Images — path per job type

### Product pictures (photorealism)
- Best photoreal quality-per-dollar: **FLUX.2 [pro], $0.03/1MP** (identical price on fal.ai, Replicate, and BFL direct).
- Draft pipeline: **FLUX.2 [klein 9B], $0.015/img** (or klein 4B $0.012–0.014). ~30–50% of product batches can be approved directly from klein 9B.
- Consistency for a product line / campaign: FLUX.2 [pro] edit with a reference image (Replicate ~$0.055 with one input MP) — keeps packaging/logo consistent across shots.
- Keep resolution at 1–1.5MP (1024–1536px). 4MP render is 4x the price and mostly unnecessary for web/commerce.

### Ad creatives with lots of text (the Gemini-3.1-Image problem)
| Model | Where | Cost/img | Text quality |
|---|---|---|---|
| Gemini 3.1 Flash Image ("Nano Banana 2") | fal | $0.08 | Excellent; character-by-character typography |
| Nano Banana Pro (Gemini 3 Pro Image) | fal | $0.15 | Better on dense/multi-line ad layouts |
| GPT Image 2 | OpenRouter | per-token (≈$0.04–0.17 est) | Best-in-class text-in-image + prompt adherence |
| GPT Image 1.5 | fal / OpenRouter | cheaper | Near-2.0, not quite as sharp |
| FLUX.2 (any tier) | fal/Replicate | $0.014–0.07 | **Trails GPT/Gemini on text** — skip for copy-heavy ads |

Recommendation: default ad-text renderer = **GPT Image 2 on OpenRouter**; secondary = **Nano Banana 2 on fal** ($0.08, flat if you already host image work there). Use Nano Banana 2's multi-reference (up to 14 imgs) + character consistency (up to 5 people) for brand-consistent UGC-style statics.

#### ⚠ GPT Image pricing is per-token — verify before trusting `cost_per_img`
OpenRouter lists the GPT Image family as **text/image-I/O tokens**, not a flat per-image rate (e.g. `gpt-5-image-mini` at ~$2.50/$2.00 per 1M tokens, `gpt-5-image` at ~$10/$10 per 1M tokens; Google's Nano Banana 2 is similarly token-billed). The "per-image" figures here (≈$0.008–0.166 for GPT-5 Image depending on resolution/quality, per third-party estimates) are **derived estimates, not posted prices**. Actual bill varies with image output size, quality tier, input tokens, and reference-image tokens.

Do this before wiring `cost_per_img` into config:
1. Fire one real generation per size/quality tier you actually ship (e.g. 1024² medium, 1024² high) through the **fal image endpoint** (`fal-ai/gpt-image-2`) or **OpenRouter image endpoint** (`/api/v1/images`).
2. Read the **exact cost from the endpoint response** — OpenRouter returns per-endpoint pricing lines with a billable unit (`token`/`megapixel`/`image`) and `cost_usd`, and the `usage` object includes exact cost; fal bills flat per-image for its hosted GPT Image endpoints.
3. Only bake the verified per-image number into config, and re-verify on rate-card changes (tokens per image drift with resolution/prompt complexity).

fal's GPT Image 1.5/2 endpoints are **flat per-image billing** (their unit is `image`, not token) — if you want deterministic `cost_per_img`, route through fal rather than OpenRouter for the GPT Image family.

Note: all Nano Banana outputs carry Google **SynthID** invisible watermark — relevant to ad-policy/compliance if they want verifiable-AI provenance.

### Presentations
- Imagery: FLUX.2 pro ($0.03). Slide text stays in the deck tool (Canva/PPT) — don't pay image models to render body text.
- For stylized full-slide hero images where caption text must be baked in: Nano Banana 2 ($0.08) or GPT Image 2 for longer phrases.

## Video — path per job type

| Model | fal price | 5s | 15s (Short/TikTok) | Best for |
|---|---|---|---|---|
| Wan 2.5 | $0.05/s | $0.25 | $0.75 | Budget motion, simple scenes |
| FLUX 3 draft | ~$0.06/s (5 free/day in sandbox) | $0.30 | $0.90 | Fast iteration, storyboards |
| Kling 2.6 Pro | $0.07/s (no audio) $0.14/s (audio) | $0.35–0.70 | $1.05–2.10 | **UGC/shorts with real people + native audio** |
| Kling v3 (i2v) | $0.112/s | $0.56 | $1.68 | Image→video product shots |
| Veo 3.1 fast | $0.10/s (no audio) | $0.50 | $1.50 | Hero-quality, premium ads |
| Veo 3.1 std | $0.20–0.40/s | $1.00–2.00 | $3.00–6.00 | 4K / best quality |

- **UGC + Shorts/TikTok: Kling 2.6 Pro** via fal. $0.14/s with native audio, 9:16 native. A 15s talking-style short ≈ $1.20–2.10. It's the realistic-people sweet spot.
- **Ad videos / product motion**: shoot-to-video from a FLUX.2 pro still via Kling v3 i2v ($0.56 for 5s) or Wan 2.5 ($0.25) for cheaper simple pans.
- **Drafts/moodboards**: FLUX 3 draft — free daily allowance on fal sandbox, else $0.06/s.
- Avoid Replicate's video (Wan 2.1 at $0.09–0.25/s) unless already in that stack — fal is cheaper.
- Don't buy upscalers (Topaz Astra etc. $1.20–3.00/10s) for social video — 1080p from Kling/Veo is enough; they punish the budget.

## Provider plan (one codebase, one key per provider)

1. **fal.ai** — primary: FLUX.2 (imgs), Kling 2.6/v3, Wan 2.5, Veo 3.1, Nano Banana 2 (videos + images in one place, per-second / per-image billing, no subscription).
2. **OpenRouter** — text-heavy ad finals: GPT Image 2 (their image API routes it per-image). Single models only, not a media host.
3. **Replicate** — optional mirror for FLUX.2 pro/edit; identical pricing to fal, useful as fallback when one queue is congested.

## Cost levers (10x savings, not 10% )

1. **Stage your renders**: klein 9B / FLUX 3 draft / Wan 2.5 for iteration → FLUX.2 pro / Kling 2.6 / Nano Banana 2 for final. This is the biggest single lever.
2. **Resolution budget**: 1MP images unless a deliverable needs more. 4MP = 4x price.
3. **Batch with `n`/num_images**: 1–4 images per request on Nano Banana 2; parallelize and pick winners.
4. **Keep video to 5s units**: generate 5s Kling/Veo clips and extend/assemble in the editor; per-second cost scales linearly so don't pay for dead frames.
5. **Free/eval allowances**: fal's 5 free FLUX 3 draft videos/day for ideation before any spend.
6. **Don't conflate text need with cost**: for copy-heavy ads pay GPT Image 2/Nano Banana 2; for image-first product shots pay FLUX.2 pro. Using the premium-text model for every image wastes money.

## Example monthly budgets

| Volume | Images | Video | Est. cost |
|---|---|---|---|
| Hobby (20 imgs + 10 shorts/mo) | all klein/flux drafts, few pro finals, ~$1–2 | Kling 5–15s 2x/mo, ~$2–4 | **$3–6/mo** |
| Solo creator (200 imgs + 40 shorts/mo) | ~$6–12 (mix klein/pro/Nano Banana) | 40 × 10s Kling w/audio ≈ $0.80–0.90 ea ≈ $36 | **$42–50/mo** |
| Agency (2,000 imgs + 150 shorts/mo) | ~$60–150 bulk | $150–250 (Kling/Veo mix) | **$200–400/mo** |

## Compliance flags
- **Nano Banana / Nano Banana 2 / Nano Banana Pro** outputs carry SynthID (Google). Paid fal/OpenRouter commercial use is fine, but disclose AI-generation where required.
- **Veo 3.1** on fal is also SynthID-watermarked and cannot be disabled.
- Kling (fal) has no forced watermark for paid API output on fal — cleaner for sponsor/paid-ad cuts.
- Replicate = pay-per-output for FLUX.2 pro (not per-GPU-second, so no idle-time surprises).