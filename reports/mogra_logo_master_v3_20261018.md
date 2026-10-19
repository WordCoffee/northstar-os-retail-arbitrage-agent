# MOGRA logo master v3 — ultra-2K reconstruction (2026-10-18, follow-up)

Operator feedback on v2: *"the logo master v2 looks horrible and is brown almost like it
tried to be transparent. Redo the logos and master them for ultra 2K clarity, don't
change anything else about them. If need be recreate them exactly for the clearest image
as our master file."*

## Why v2 looked brown/muddy (root cause, measured)

v2 keyed a soft per-pixel alpha over the whole mark. Only full-strength strokes reached
~100% opacity; everything else - the grey-green the wordmark settles into at 60-90%
coverage, the tan mortar interior, the pale sage shading, all the anti-aliased edges -
sat at 20-90% opacity *and* kept white-mixed fringe colours. On a transparent
checkerboard (or any dark viewer that shows alpha as black) that mix reads as a brown
smear. The artwork itself contains no brown in the wordmark: measured stroke tones are
the dark grey-green (82,86,70) family; the browns (125,86,59 / 120,103,85) belong to the
mortar and pestle only.

## v3: reconstruction, not filtering

`Northstar_backend/rebuild_mogra_logo_hd.py` rebuilds the SAME artwork from its own
pixels as flat colour layers:

1. **Palette measured from the artwork** (k-means, fringe-whites pruned, 7 tones kept -
   e.g. brown 125,86,59 · tan fill 187,176,147 · wordmark 82,86,70 · tagline 129,131,115
   · light 152,155,138 · leaf 110,172,70).
2. **White-line projection matte**: every pixel is assigned to the class whose
   white→ink colour line it actually lies on (`pixel = a·C + (1-a)·white`). A wordmark
   fringe pixel therefore resolves to the *wordmark* ink at partial alpha - never to a
   tan or a near-white, which is what removes both fringe colour cast and halos.
3. **Layer reconstruction at 10x** (~2.9K): each class mask and the matte are upscaled
   with Lanczos; colour is the normalised layer blend, alpha a steepened matte. Full
   strokes land at 100% opacity; only true edges keep in-between values.

Nothing was redrawn, re-lettered or recoloured - the master is the operator's artwork,
re-encoded at ultra-2K.

## Verification (all asserted by the script before it writes anything)

| Check | Value |
|---|---|
| mask IoU vs source artwork | **0.9993** |
| recompose-vs-source error (ink px) | mean **5.12**, p95 **13.9** / 255 |
| edge sharpness vs plain upscale | **1.65x** steeper |
| fully-opaque core strokes | **80.9%** of ink coverage |
| size | **2920 x 2510** (~2.9K) |
| OCR (rapidocr) | reads `EST` · `2023` · **`MOGRA ORGANICS`** · `Healthy & Organic` - same tokens the source gives |
| pipeline crop cuts (52%/55%) | rows 130.5 / 138.0, inside the artwork's true blank gap 127..142 |
| source md5 | `8b476a1e...` (byte-identical to `Desktop\Mogra Organics\logo.png`) |

## Deliverables

- `exports/mogra_logo_master_v3.png` - RGBA master, 2920x2510, fringe-free.
- `exports/mogra_logo_master_v3_white.png` - the same on white, opaque (quick-look file;
  no checkerboard interpretation needed).
- `exports/mogra_logo_before_after_v3.png` - v2 vs v3, each shown on white AND on dark -
  the review sheet that settles the complaint visually.
- `exports/mogra_logo_qa_v3.json` - every number above.
- Pack regenerated with the v3 master: `exports/mogra-lionsmane-6oz-i-series-v2-20261018/`
  (10 fronts + 10 backs + 20 shelf mockups + sheets + READMEs; same compositions, same
  stamp anchors and visible sizes - only the logo image changed). The pack's `logo/`
  folder carries the master + the white companion + the QA json.
- Overlap audit re-run on v3: all 20 panels **0.000% collision**, no empty stamps
  (`reports/i_series_lockup_audit_20261018_223644.json`).
- v2 artifacts retired to `exports/_logo_master_v2_retired/` (traceability only).

## Honest limits

- No true vector (SVG) master yet: `vtracer` is still not installed. The palette-layer
  reconstruction is where that work would slot in later if wanted.
- This session's model cannot view images; the final "clear as our master file" call is
  the operator's - start with `mogra_logo_before_after_v3.png`, then
  `mogra_logo_master_v3_white.png`, then the pack's `contact_sheet.png`.
