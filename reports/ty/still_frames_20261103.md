# Still placements: social frames and a listing gate that was rejecting good images

**Date:** 2026-11-03 · **Commit:** `5e144b18` · **Probe:** `state/probes/t17_still_frames.py` PASS · **Tests:** 7 passed.

The creative scan listed two still gaps: ad stills had no placement safe zones, and listing images had
rules but no systematised prompt pack or gate. Both are closed, and building the gate exposed a real
defect that would have refused every correct main image.

## What was added

`ad_formats.py` — eight still placements (`amazon-main`, `meta-feed`, `ig-story`, `reels`, `tiktok`,
`shorts`, `sponsored-brand`, `display`), each with a canvas, a safe-zone contract, `verified` and a
`source`. Numbers taken from the checked video presets are `verified: true`; Amazon and the working
estimates are `verified: false` and say why.

`social_frames.py` — draws the product picture and vector copy (headline, subline, CTA pill) inside
the placement's safe area, returns the measured boxes, checks WCAG AA contrast, and OCRs the result.
A no-text placement (`amazon-main`) **refuses copy** rather than silently painting it. The listing
prompt pack has five styles (white-bg, lifestyle, flat-lay, macro, scale-shot), each lower-case and
digit-free, each proven to survive `sanitize_brief_for_render`. `listing_gate` refuses a main image
that carries lettering or fails the listing rubric.

## The defect the probe found

`asset_rubric.score_listing` added `copy_not_readable` whenever OCR found fewer than half the
expected words — **including when no copy was expected**. A perfectly good white-background main
image with no text therefore always failed (`legibility 0.0`, `copy_not_readable`). The rubric now
grades copy only when `expected_copy` was supplied; a text-free listing image scores on purity, fill,
balance, and correct absence of lettering.

## Measured

```
meta-feed: [1024, 1024] boxes={'headline': [61,666,942,749], 'cta': [61,820,360,870], ...}
           contrast={'headline': 11.14, 'cta': 7.41} ocr=["LION'S MANE", ..., 'SHOP NOW']
tiktok:    [864, 1536] ocr=["LION'S", 'MANE', 'MUSHROOMPOWDER', 'SHOP NOW']
sponsored-brand: [1536, 864] ocr=["LION'S MANE", 'MUSHROOMPOWDER', 'SHOP NOW']
listing white: {'listing_rubric_pass': True, 'text_free': True} 99.9 []
listing grey:  listing_image_refused: listing_rubric_pass
listing lettered: listing_image_refused: text_free
t17 still frames: OK
```

## API

`POST /api/design-studio/social-frames/render` takes a product picture as a data URL, a placement,
the copy and a palette; it returns the measured boxes, contrast, OCR words, a PNG data URL and the
saved path. `GET /api/design-studio/social-frames/placements` returns the eight contracts.

A frame that fails its own check is saved as `rejected_*` and returned as a **422** with the candidate
path and the reason — it is never presented as a deliverable. `amazon-main` refuses copy by contract.

Live run (real `product_front.png`, TikTok):

```
ok: true
file: Northstar_backend/data/studio_generated/tiktok_e445423614.png
canvas: [864, 1536]
boxes: headline [51,749,708,1001], subline [51,1028,708,1081],
       cta [51,1108,310,1183], product [180,122,580,722]
contrast: 11.14 / 11.14 / 7.41
checks: ocr_available, headline_read, cta_read, inside_safe_area, contrast_aa -> all true
compliance: verified true (TikTok)
```

The endpoint writes no database row: it returns the image and its path so the caller's own asset flow
decides where it lives. That keeps the account-scoped storage out of a stateless render.

## Honest gaps

- **The frames use a synthetic product picture in the probe.** The renderer is real; the photograph
  is not. A live frame needs a FLUX plate or a product picture from item 0.
- **Meta/IG/display safe zones are working estimates** (`verified: false`). Amazon's main-image rule
  is respected but its spec was not read (standing gate).
- **No endpoint yet.** `social_frames` is a library + probe + tests; wiring it to `POST
  /api/design-studio/frame` is the next integration step.
- **The CTA pill is drawn copy, not a platform button.** It is inside the safe area but it is an
  image, not a clickable element.

## Files

`Northstar_backend/ad_formats.py`, `social_frames.py`, `asset_rubric.py`,
`test_social_frames.py`, `test_asset_rubric.py`, `state/probes/t17_still_frames.py`.
