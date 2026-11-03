# Script to scenes: a budget the sampler and the stitcher can both honour

**Date:** 2026-11-03 · **Commit:** `386b7305` · **Probe:** `state/probes/t16_video_script.py` PASS · **Tests:** 5 passed.

Work order item 4 in `reports/ty/creative_scan_20261103.md`. The planner turns the product's own copy
into five beats — hook, benefit, proof, product, close — inside the placement window.

## What it guarantees (and checks)

- **Durations sum to the requested window exactly.** Weights are applied per beat, then frame counts
  are computed and the largest scene absorbs the rounding residual: 15 s → 450 frames, 30 s → 900.
- **The hook is 3-5 complete words.** A cut phrase loses its trailing stopword ("the pouch you reach
  for" stays five words; a longer template cut at five does not end on "the"/"you"/"for").
- **Prompts survive the text-safe lane.** Every prompt is lower-case art direction with no digits and
  no all-caps runs; `sanitize_brief_for_render` leaves real direction and finds no expected terms,
  so the image model is never asked to paint lettering.
- **Every scene carries an on-screen line and a voiceover line**, with an estimated spoken duration
  (2.7 words/s, measured Piper pace on this box) and a `voice_fits_scene` flag.
- **Compliance rides along.** An Amazon preset returns `compliance.verified = false` because its spec
  is behind the standing gate; a TikTok/Shorts preset says `true`.

The beat windows are the sourced structure already recorded in
`northstar-os-ui/src/studio/engine/hookTemplates.js` (hook 1-3 s, body 7-20 s, CTA 2-5 s; a 3-5 word
on-screen hook held ~2 s). The module repeats that they are **structure, not a performance claim**.

## Measured

```
tiktok 15s: scenes=5 sum=15.0s frames=450/450 hook='the pouch you reach for'
tiktok 30s: scenes=5 sum=30.0s frames=900/900 hook='the pouch you reach for'
shorts 15s: scenes=5 sum=15.0s frames=450/450 hook='the pouch you reach for'
amazon-ad-16x9 15s: scenes=5 sum=15.0s frames=450/450 hook='the pouch you reach for'
  (compliance verified: false, as declared for this preset)
t16 video script planner: OK
```

## Honest gaps

- **Not yet wired to the renderer.** `shorts.generate_stitched` still renders one prompt for every
  clip; using the per-scene prompt/frames is the integration unit, not a claim made here.
- **The on-screen line is a caption candidate, not a caption.** It still has to go through
  `video_captions` to be placed, burned and OCR-checked.
- **Voiceover timing is an estimate**, not a forced alignment. A line that overruns its scene is
  flagged (`voice_fits_scene: false`), not silently sped up.
- **Copy is the product's declared copy.** Claims are rendered as supplied; a disease/treatment claim
  still needs the compliance screen that `package_art` warns about.

## Files

`Northstar_backend/video_script.py`, `test_video_script.py`, `state/probes/t16_video_script.py`.
