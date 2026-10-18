# Mockup print-integration engine v2 — designs printed INTO the package

_2026-10-18 · fixes: "sticker placed on the container", "design not attached to
the package", "doesn't look like packify.ai"_

## Root causes found
1. **Old plates fought integration**: kraft package on a warm-beige scene — the
   print had to stop before the package edge and any colour change read as a
   pasted rectangle (a decal).
2. **Old warps were patches**: a homography/cylinder in a fixed rectangle with
   weak shading (±7 %) — the photo's lighting did not continue through the
   print, so it floated on top of the package.

## The fix (new pipeline)
**Plates** — 4 new studio plates rendered on the local lane (4B pin):
matte-white pouch (front/back) and matte-white paper tube with kraft lid
(front/back) on a flat light-grey sweep, soft shadow.
`render_studio_plates.py` regenerates them.

**Engine** — `Northstar_backend/mockup_engine.py`:
- **Calibrated silhouette anchors** per plate (`data/mockup_plates.json`,
  measured from the plates and verified visually) + a small clamped gradient
  snap per row — no heuristic can wander onto the backdrop or cast shadow.
- **Silhouette-following mapping**: every row maps the art across that row's
  true package width (linear on pouches, `arcsin` cylinder compression on
  tubes) → the print reaches the real package edges, exactly like print on a
  physical object.
- **Baked lighting**: the plate's own luminance (large-scale shading + fine
  texture) is multiplied into the print → cylindrical shading, the lid's cast
  shadow, zipper ridge and fabric folds continue THROUGH the design.
- **Wrinkle emboss + fold displacement** (damped at top/gusset), **edge
  feathering** (dilate + ~2 px blur) so the print dissolves into the edge.
- **Column-wise base-curve clip** so the print follows the package base instead
  of spilling onto the floor.

**Art** — `package_designs.apply_paper()`: subtle paper grain + mottle on every
front/back so flat art reads as printed stock under the lighting bake.

## Verified
- 4 plate segmentations checked on overlay previews; 2 collision bugs found and
  fixed during review (mask floor-bleed at the base; lot/best vs barcode).
- Full set re-rendered and reviewed at contact-sheet + full-res level:
  10 designs × front + back, all reading as printed packages.

## Outputs
- Flat art (300 dpi, paper-textured): `exports/mogra-designs-20261018-bold/`
- Shelf mockups (v2 engine): `exports/mogra-shelf-mockups-20261018-v3-studio/`
- Engine test/calibration previews: `exports/_engine_test/` (dev only)

## Known small nits (documented, not blockers)
- Tube fronts: adjacent elements can visually touch after arc compression
  (e.g. wordmark near the seal) — layout compression note.
- Pouch backs: the print ends at the base seam; the last few px show the seam
  band (as on a real bag).
