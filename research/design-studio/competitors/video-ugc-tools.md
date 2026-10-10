# Video and UGC: Kling, Runway, Veo, Hailuo, HeyGen, Arcads, MakeUGC ? Competitor Deep Dive

> Track A of the Northstar Design Studio research corpus. Every claim carries a
> source URL and a tag: [documented] (vendor's own docs/pricing), [observed]
> (seen in product, demo, or video), [inferred] (derived reasoning or
> third-party claim, not confirmed by the vendor).
> Pulled at: 2026-10-10.

## 1. What it is, who it's for, pricing tiers and generation limits

PRICING NOT CAPTURED for this group in this pass. See the coverage report for
the explicit shortfall. What IS documented:
- These models appear almost exclusively as PARTNER MODELS inside other tools.
  Adobe Firefly's plan page documents them by name and tier: **Google Veo 3.1
  Fast, Kling 2.5 Turbo, Kling 3.0, Luma Ray 3.14, Runway Gen 4.5** (plus
  Nano Banana 2, Flux.2 Pro, ChatGPT Image 2, OpenAI Image Generation, Black
  Forest Labs Flux.2 Pro) [documented]. That is the only vendor-published
  tier-by-tier availability matrix captured in this pass.
- Creatify documents "10+ Premium AI Models (Nano Banana Pro)" on Starter and
  "30+ Premium AI Models (Sora 2 Pro)" on Pro [documented] ? confirming Sora 2
  Pro is available to sellers through an aggregator rather than directly.
- Amazon's own Sponsored Brands video specs (see amazon-requirements.md) are
  the constraint this entire cluster must be measured against.

## 2. Feature inventory

| Feature | How it works | Source | Tier |
|---|---|---|---|
| Veo 3.1 Fast | Video model, Premium tier unlimited on Firefly Premium | adobe.com/firefly/plans | Premium |
| Kling 2.5 Turbo | Video model, Pro Plus tier unlimited | adobe.com/firefly/plans | Pro Plus |
| Kling 3.0 | Video model, Premium tier unlimited | adobe.com/firefly/plans | Premium |
| Luma Ray 3.14 | Video model, free daily generations | adobe.com/firefly/plans | free |
| Runway Gen 4.5 | Video model, listed among partner models | adobe.com/firefly/plans | varies |
| Nano Banana 2 (1K/2K) | Image model, unlimited first year on Pro+ | adobe.com/firefly/plans | Pro Plus |
| Flux.2 Pro | Image model, unlimited first year on Pro | adobe.com/firefly/plans | Pro |
| Sora 2 Pro | Video model, 30+ models on Creatify Pro | creatify.ai | Pro |
| HeyGen / Arcads / MakeUGC | Named by G2 reviewers as tools users switched FROM to Creatify | g2.com/creatify/pricing | n/a |
| Amazon Sponsored Brands video spec | 6-45s, 16:9 square pixel, 1280x720/1920x1080/3840x2160, MP4/MOV, H.264/H.265 Main|Baseline, 23.976-30fps, min 1 Mbps video, PCM/AAC/MP3 96kbps 44.1kHz; 9:16 vertical 720x1280/1080x1920/2160x3840 via Ads API | advertising.amazon.com | Amazon |

## 3. User workflow, step by step (clicks to first output)

Not captured ? pricing and per-tool workflows for Kling, Runway, Veo, Hailuo,
HeyGen, Arcads and MakeUGC were not retrieved in this pass. Recorded as an
explicit shortfall rather than guessed. The only workflow documented here is
the aggregator path (Firefly/Creatify) because that is what a seller can
actually buy.

## 4. UI / layout patterns

Not captured for this group. The relevant observed pattern is that these
models are delivered through an aggregator UI (Firefly model picker, Creatify
Asset Generator / Model Playground) rather than as standalone seller-facing
products ? which is itself the finding: a seller does not buy Veo, they buy the
surface that wraps it.

## 5. What users love / hate

Not captured ? no review/complaint corpus was retrieved for this group in this
pass. Creatify reviewers do name Arcads, HeyGen and Synthesia as the tools they
switched from, citing better pricing and quality [documented in G2 review
commentary], which is the only comparative signal captured.

## 6. Gaps for Amazon sellers specifically

Gaps for Amazon sellers specifically:
1. **No tool in this group validates the Sponsored Brands video spec.** A seller
   can render a beautiful video that fails on duration (6-45s), aspect ratio
   (16:9 square pixel only on the standard surface), codec, bitrate, or the
   "no text in the bottom-right corner" safe-area rule, and get the ad rejected.
2. **No AI-generated-people disclosure handling.** Sponsored Brands and A+ both
   require disclosure/metadata when photorealistic AI people appear.
3. **No product-fidelity contract.**
4. **No keyword/search-term hook input.**
5. **No experiment linkage.**
6. **Model availability changes without notice** ? Adobe's own terms reserve the
   right to modify or discontinue any partner model at any time, so any
   workflow hard-wired to one model is fragile.

## 7. Output quality notes and known failure modes

Known failure modes for generated video/UGC: lip-sync errors; wrong voice or
speed; pacing that feels mechanical; takes that cost credits and produce nothing
usable (Creatify's third reviewers); hands and bodies with anatomical errors;
product label/text garbling when the video re-renders the product; audio
quality making a video unwatchable on mute-first platforms; and the fact that
Amazon's SB video surface is the ONLY video ad slot on search results ? meaning
a rejected creative has no fallback placement.
