# Creative lanes — what the service can make, and what each output is checked against

**Last updated:** 2026-11-03. Every lane below is local, deterministic where it draws type, and refuses
an output that fails its own measurement. Nothing on this page contacts Amazon or a paid provider.

## The rule every lane follows

1. **A photograph is a photograph; type is drawn.** Diffusion supplies the image and is never asked to
   spell. Text is rendered from real fonts, so a wordmark cannot come back misspelled.
2. **A placement contract precedes the pixels.** A canvas, safe zones, fps/duration or fill band is
   declared before rendering.
3. **The output is measured.** OCR, contrast, ffprobe, fill/purity, duplicate/tile hashes — whichever
   the surface needs. A file that fails is saved as `rejected_*` (or not written) with the reason.
4. **A candidate is not a shipped asset.** Where taste decides (framing, copy), the report presents
   candidates and names the choice as the operator's.

## The review gate (every presented image)

`Northstar_backend/ship_gate.review_image` runs on the Tys graphics lane before an image is
returned. It measures, in order: **identity** (pHash distance + SSIM against the reference product
photo), **legibility** (the OCR/sharpness contract, when text is expected), **preference** (HPSv2
cosine) and **adherence** (PickScore logits). Four truthful outcomes: `passed` (deliverable),
`refused` (with the failed axis and reason), `needs_review` (a required scorer is not installed -
never a pass) and `unscored` (nothing blocking measured - a candidate only).

Floors and per-surface policy live in `config/image_review.json`; they were calibrated on this
box's own outputs on 2026-11-04. The scorers are local CPU models run one axis per child process:
both resident measured 6.4 GB RSS and left 0.7 GB free, one at a time peaks at 2.5 GB (PickScore)
and 4.8 GB (HPSv2). Measured: product pictures 0.236-0.241 preference / 19.4-21.4 adherence; flat
label artwork 0.151 / 19.0 (refused on preference). Designed social frames score low by nature, so
that surface records the score without blocking on it.

## Endpoints

| Surface | Route | What it returns |
|---|---|---|
| Product picture (front/back) | `POST /api/design-studio/product-picture` | PNG files + per-face quad, OCR gate, text-safe record, manifest |
| Still placements | `GET /api/design-studio/social-frames/placements` | 8 placements with canvas + safe zones |
| Social frame | `POST /api/design-studio/social-frames/render` | PNG data URL + boxes, contrast, OCR checks; 422 with candidate on refusal |
| Listing image | `POST /api/design-studio/listing-images` | text-safe render, fit to 86% fill, main-image/secondary gate |
| A+ page | `POST /api/design-studio/aplus-page` | 6 modules as data URLs + per-module QA, page bytes |
| Video plan | `POST /api/design-studio/video-ad/plan` | scenes, per-scene sampler chunks, clip count, compliance |
| Video render | `POST /api/design-studio/video-ad/render` | 202 job; `GET /jobs/{id}` for stage/reason/manifest |

`POST /video-ad/render` requires `confirm: true`: a 15 s TikTok is eight sampler clips and roughly
12 minutes of local compute. The plan route exists so a typo cannot start it.

## The lanes

### Product pictures

`product_picture.produce` renders two blank plates on FLUX 3 through the text-safe guard, measures
each face with `pouch_label.measure_face`, warps the designed panel with
`mockup_compositor.composite_panel_onto_quad`, and refuses the picture unless
`mockup_quality.assert_legible` reads the wordmark and net weight. A plate with no package is
`plate_face_not_found`, never composited.

When a reference photo is supplied (`reference=` / `references={"front": id, "back": id}`), the plate
is **reference-conditioned** (FLUX 3 mi2i: `LoadImage -> VAEEncode -> ReferenceLatent`) so the pouch
is the real one, while the vector panel still replaces the label area: small print is drawn, never
diffused. Live 2026-11-04: front and back both passed the OCR gate; the same prompt without the
reference invented `AETICHIN ERMNICSES` on the label.

Live: `renders/mogra_lions_mane/product_front.png`, `product_back.png` (1024×1536, OCR-gated).

### Social frames and listing images

`social_frames` draws the product picture and vector copy inside a placement's safe area and returns
the measured boxes. A no-text placement (`amazon-main`) refuses copy. `listing_render` renders the
five text-safe listing styles and applies the matching rubric; a main image is cropped/rescaled to
86% fill on pure white so the fill band is deterministic rather than a prompt hope.

Live: a TikTok frame (864×1536, 11.14:1 headline contrast) and a white-background listing image
(1024×1024, 86.04% fill, purity 1.0, text-free, score 99.6).

### A+ pages

`aplus_brief` maps product copy to six beats (header, three tiles, comparison, banner, premium,
logo). Every module passes `aplus_render.assert_perfect` (exact canvas, measured contrast, type size,
under 2 MB) before the page is returned. Prohibited copy is refused by the renderer's screen.

Live: a six-module page from the item-0 picture, 1,159,507 bytes, all QA clean, deterministic hashes.

### Video

`video_script` → `shorts` (Wan 2.2) → `video_stitch` → `video_captions` → `video_audio`:

- scenes sum exactly to the placement window, prompts survive the text-safe sanitiser;
- each beat gets a deterministic crop of the **same** product picture (no second pouch invented);
- clips are normalised, concatenated and trimmed to the exact frame count, then ffprobe-checked
  (duration ± one frame, canvas, h264, mp4, size cap);
- captions are drawn in the safe area and OCR-checked; audio is local voice + a generated bed,
  sidechain-ducked and loudness-normalised to -16 LUFS;
- a failed picture gate deletes the file.

Live: a 15 s TikTok master, 450 frames, 1080×1920, h264+aac, -16.06 LUFS, captions OCR-checked,
8 clips, 12.2 minutes (`renders/mogra_lions_mane/video_15s/video_ad.mp4`).

## Honest gaps

- **Amazon specs are not read.** Amazon ad-video and main-image presets are `verified: false` or
  declared working assumptions; the standing gate is respected.
- **The 15 s cut is framed tight** (hook 1.35×, proof 1.55×) and its captions repeat the label's
  claims. It is a candidate for the operator's eye; `_FRAMING` is the one-line lever.
- **One plate, many crops.** The video varies the camera, not the set; distinct setups need distinct
  plates.
- **A+ header crops a portrait plate** at the image panel; a landscape product photo composes better.
- **No UI wiring yet.** The endpoints are the product surfaces; the screens are a separate unit.
- **Listing main images** are fitted to a white field but a soft contact shadow can survive inside the
  subject crop; the rubric does not currently reject a shadow.
