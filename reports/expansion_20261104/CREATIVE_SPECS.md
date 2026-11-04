# E-Commerce Creative Service Specification

Status: **internal contract**, not a compliance claim. Amazon-specific presets remain
`verified: false` because reading Amazon's own documentation is a standing gate. The numbers below
come from this repository's measured renderers (`aplus_layout`, `aplus_render`, `ad_formats`,
`video_formats`, `mockup_quality`, `print_prep`, `ship_gate`) plus public, non-Amazon sources.

---

## 1. A+ content — module presets

Canvas is fixed before copy is set. `aplus_render.assert_perfect` refuses a module that misses the
canvas, contrast, type size or 2 MB cap.

| Module | Canvas (px) | Per-tile / notes | Copy rules |
|---|---|---|---|
| Standard header | 970 × 600 | copy band 44% of width, alternating side | head ≥ 24 px, body ≥ 14 px |
| Standard three tiles | 970 × 300 | three 300 × 300 tiles, 20 px gap | one claim per tile |
| Standard single | 300 × 300 | one image or one claim | body ≥ 14 px |
| Comparison | 970 × 600 | columns + rows, measured cell grid | no unverified comparative claims |
| Banner | 970 × 300 | full-width band | head ≥ 24 px |
| Sidebar | 300 × 400 | vertical stack | body ≥ 14 px |
| Premium desktop | 1464 × 600 | equal-area premium class | same contrast floors |
| Premium mobile | 600 × 450 | mobile rendition | same contrast floors |
| Logo | 600 × 180 | brand mark only | no headline |

**Contrast floors:** 4.5:1 body, 3.0:1 large (≥24 px), 6.0:1 when type sits over a photograph
(a scrim is strengthened until it measures; otherwise the module is refused).

**Six-beat page order** (from `aplus_brief`): header → three proof tiles → comparison → banner →
premium → logo. A page is only assembled when every module passes; a missing module fails the page
manifest rather than silently shortening it.

## 2. Still ad formats — canvas and safe zones

| Format | Canvas | Ratio | Text | Safe zone (top/bottom/right) |
|---|---|---|---|---|
| `square` (feed) | 1024 × 1024 | 1:1 | allowed | 2 / 2 / 2 % |
| `story` (9:16) | 864 × 1536 | 9:16 | allowed | 6 / 14 / — |
| `wide` (16:9) | 1536 × 864 | 16:9 | allowed | 5 / 10 / — |
| `amazon-main` | 1:1 | 1:1 | **not allowed** | pure white field |
| `meta-feed` | 1:1 | 1:1 | allowed | per placement |
| `ig-story` / `reels` / `tiktok` / `shorts` | 9:16 | 9:16 | allowed | 8–12 / 18–22 / 12–18 % |
| `sponsored-brand` / `display` | 16:9 | 16:9 | allowed | 4–5 / 8–10 / 5 % |

A caller that passes a contradictory width/height is refused (`ad_format_dimension_conflict`), not
silently overridden. Placement safe zones are enforced by measurement, not by prompt wording.

## 3. Listing images

* Main image: pure white field, subject fill **86%** (`listing_render` crops/rescales; measured
  86.04% live), text-free (OCR check), no props.
* Secondary images: lifestyle, macro, scale, packaging, group — the five Shopify-documented shot
  types map cleanly onto our five `listing_render` styles.
* A soft contact shadow can survive the crop; the rubric does not currently reject it. Add a shadow
  check before calling a listing image "print-ready" (open gap, not a claim).
* Every listing image carries `manifest.json` with fill %, purity, OCR words, rubric score,
  model, seed and file hash.

## 4. Short-form video (Shorts / TikTok / Reels)

| Preset | Canvas | fps | Window | Sweet spot | Safe zone (top/bottom/right) | Cap |
|---|---|---|---|---|---|---|
| `shorts` | 1080 × 1920 | 30 | 1–180 s | **30 s** | 10 / 18 / 12 % | 256 MB |
| `tiktok` | 1080 × 1920 | 30 | 3–600 s | **21 s** | 8 / 22 / 18 % | 4 GB |
| `reels` | 1080 × 1920 | 30 | 3–180 s | **20 s** | 10 / 20 / 14 % | 1 GB |
| `amazon-ad-16x9` | 16:9 | 30 | 6–45 s | 15 s | 5 / 10 / 5 % | 500 MB — `verified:false` |
| `amazon-ad-9x16` | 9:16 | 30 | 6–45 s | 15 s | 8 / 15 / 8 % | 500 MB — `verified:false` |

Rules already enforced: 4n+1 frames per sampler call, 81-frame ceiling, clips normalised and
concatenated, duration verified with `ffprobe` within one frame, captions drawn inside the safe
zone and OCR-checked, audio sidechain-ducked and normalised to **−16 LUFS**, h264 + AAC in MP4.
A plan that exceeds one sampler call returns `video_needs_stitch` instead of mislabelling a 2 s
clip as a 30 s TikTok.

## 5. Verification thresholds (the gate contract)

| Surface | Check | Threshold |
|---|---|---|
| Product picture | wordmark read + net weight read + sharpness | Laplacian variance ≥ 40 on ≥ 75% of text boxes; text height ≥ 10 px |
| Any gated image | identity vs reference | pHash distance ≤ 24 **and** SSIM ≥ 0.40, or SSIM ≥ 0.55 |
| Product picture / listing | HPSv2 preference | ≥ 0.20 |
| Product picture / listing | PickScore adherence | ≥ 18.0 |
| A+ module | contrast / type | 4.5 body, 3.0 large, 6.0 over photo; body ≥ 14 px, head ≥ 24 px; ≤ 2 MB |
| Listing main | fill / purity / text | 86% fill, purity 1.0, text-free |
| Video | duration / container / audio | ±1 frame, h264+aac MP4, −16 LUFS |
| Print | dieline | 300 DPI at the measured quad; quad area > 0; face ≤ image |

A missing measurement is `needs_review`, never `passed` (see `ship_gate`).

## 6. Dieline and print constraints

* `print_prep.face_pixels` refuses a collinear or zero-area quad; `dpi_report` refuses an image
  smaller than the measured face. A 300 DPI report on a quad that cannot be printed is a bug, and
  both paths have probes (`t1`, `t8`).
* `mockup_compositor` registers the panel to the measured quad with sub-pixel corners and edge
  feathering; a plate with no detectable face is `plate_face_not_found`, never composited.
* A 3D mesh (Blueprint B4) is a **candidate**, not a print asset: `manifold_edges > 0` or a bbox
  outside 2% of the measured face is refused.

## 7. What the research says (and what it does not)

Grounded, citable directions from the arXiv pass and public e-commerce guidance:

* **Ad creative generation** — AdBooster (arXiv 2309.11507) and the fashion e-commerce
  hyper-personalisation work (arXiv 1908.10139) both treat creative as generate-then-rank, not one
  shot. That is the same conclusion the image work reached independently: best-of-N plus a measured
  rank beats a single render.
* **Short-video engagement** — "Engagement Prediction of Short Videos with Large Multimodal Models"
  (arXiv 2508.02516) supports a learned engagement signal; it is not a licence to optimise for
  watch-time at the expense of the product claim. Keep it as a recorded score, not a gate until
  calibrated on our own posts.
* **Reference fidelity** — "Mind the RefGAP" (arXiv 2609.35708) is directly relevant to the
  reference-conditioning work: reference attention can drift; the identity gate (pHash/SSIM) is the
  measurable guard.
* **Product photography** — the Shopify guide documents the five shot types (white background,
  lifestyle, packaging, zoom, group) and side/soft lighting; our listing styles cover the first,
  second, fourth and fifth. Packaging-as-subject is the gap.
* **CTR literature** is dominated by user/feature models (deep interest networks, generative
  interest modelling) that need impression logs we do not have. Do not import a CTR model; import
  the evaluation discipline (holdout, calibration, no claim without a denominator).

## 8. Pipeline requirements to add

1. **Per-surface config** (`config/creative_specs.json`) holding the tables above, so a threshold
   change is data, not a code edit.
2. **A+ module presets** already exist in `aplus_layout`; expose them through the API with the six
   beats and refuse a partial page.
3. **Listing shadow check** — a measured contact-shadow detector before "print-ready".
4. **Best-of-N for ad stills** — 2–3 variants, rank by adherence then preference, keep the rejects.
5. **Short-video engagement score** — recorded only, until calibrated on real posts.
6. **Manifest completeness** — every output writes `manifest.json` with source brief, model + sha,
   seed, gates, scores and file hashes; an empty field is a failure, not a placeholder.

## 9. Deliberate exclusions

* No Amazon page, API or asset is fetched. Amazon presets stay `verified:false` until the owner
  supplies the current spec document.
* No claim of conversion lift from a layout rule. The measurable proxies are the gates above;
  conversion is a post-publish number we do not have.
* No anti-bot, CAPTCHA or stealth technique from any scanned browser project.
