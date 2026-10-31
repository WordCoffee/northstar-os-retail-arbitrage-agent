# 100 further improvements — Creative Services

Derived from the failures actually observed on 2026-10-30 (FLUX 3 lettering, scrub residue,
bleed-through, RAM floor, OCR confidence). Ordered by leverage, not by category size.

## A. Plate generation & the text problem (1–20)

1. Inpaint the label region with a control mask instead of erasing glyphs after the fact.
2. Add a two-pass generate: pass 1 at 512² to locate the pouch face, pass 2 at 1024² guided by it.
3. Reject any plate where `assert_plate_clean` fails at 0.35 AND 0.50 confidence (two floors).
4. Add a low-contrast OCR pass (CLAHE + threshold sweep) to catch the `ß5sr10mm0` class.
5. Store `plate_sha256` in the label sidecar so a changed plate can never reuse old geometry.
6. Add a `blank_plate` prompt macro library (kraft, coated, corrugated, glass, aluminium).
7. Wrap the plate prompt in `text_fidelity.sanitize_brief_for_render(hard=True)` automatically.
8. Detect burned-in logos via template matching against known brand marks.
9. Add a plate-quality score (crease realism, specular spread, silhouette symmetry) to reject junk.
10. Render at 3 seeds and pick the plate with the fewest OCR boxes.
11. Cache good plates by prompt hash so repeat SKUs skip generation entirely.
12. Add a `--no-generate` path that composites onto an operator-supplied photo.
13. Separate the render into diffuse/specular/shadow passes for label-light matching.
14. Add a normal-map pass so the label warp follows real surface curvature.
15. Auto-derive the label quad from the cutout alpha silhouette instead of luminance.
16. Support non-pouch geometries: box (6 faces), bottle (curved wrap), tube, jar.
17. Add a
`--dry-run` that reports the prompt, seed, predicted material tier and cost before rendering.
18. Reject plates whose background is not neutral (colour cast breaks the white hero later).
19. Log every render's seed + prompt + plate hash to a reusable plate library.
20. Add a ComfyUI graph version pin in the report so a graph change is traceable.

## B. Deterministic compositing & typography (21–40)

21. Raise the neutralise inset from 0.78 to a measured value per plate (currently a constant).
22. Feather the neutralise mask from the quad's own edge angle, not a fixed 10 px.
23. Verify post-composite OCR equals the intended copy exactly; diff words, not just "≥2 hits".
24. Add optical kerning via per-pair offsets in `_tracked` for headline text.
25. Enforce a baseline grid across title/subtitle/bullets (currently free-flowing).
26. Auto-shrink long titles to a measured fit rather than a fixed size ladder.
27. Add a legal-copy block (ingredients, address, net weight) with its own 5 pt minimum.
28. Generate the UPC/EAN from a real GS1 check digit, with quiet zones and HRI text.
29. Add QR generation for lot traceability, with error-correction level M.
30. Support a logo image with alpha, auto-keyed and placed per brand memory.
31. Add foil/spot-UV masks exported as separate channels for the printer.
32. Add a soft specular sheen over foil areas matched to the plate's light direction.
33. Add emboss height maps (debos/emboss) for tactile preview.
34. Add a print-sim pass: dot gain, plate misregistration, and ink opacity.
35. Add CMYK soft-proof of the label with the RSWOP profile before export.
36. Add bleed polygon clipping so the label never paints past the die line.
37. Export a layered PSD (label, shading, foil, highlights) for the archive.
38. Keep text as vector in the PDF path (never rasterise type).
39. Add per-language text boxes with autofit + overflow refusal.
40. Add a "no unlabelled zone" audit: any OCR box outside the label quad is a failure.

## C. Listing imagery (41–55)

41. Make the contact shadow direction configurable and match the render's key light.
42. Add a shadow strength auto-tuner from the subject's luminance.
43. Add reflection support for glossy products on white.
44. Enforce the 85% fill rule with a measured bounding box, not an assumed one.
45. Add a secondary-image template set (scale shot, detail macro, lifestyle, comparison).
46. Reject a hero whose subject touches the frame edge.
47. Add a "no props" check via segmentation outside the subject bbox.
48. Auto-generate alt text per image from the brief, capped at 120 chars.
49. Add 1:1 / 4:5 / 16:9 derived exports from one master render.
50. Add WebP and AVIF export alongside PNG.
51. Add a 2× and 3× slice for retina storefronts.
52. Add a file-size guard (2 MB A+ limit) with automatic recompression.
53. Add EXIF/XMP rights metadata to every exported asset.
54. Add an image-diff check between render and final hero so unintended edits are caught.
55. Batch the hero step behind `hardware_guard` and record peak VRAM per image.

## D. A+ and storefront (56–70)

56. Compose live A+ modules from a JSON spec rather than hard-coded JSX.
57. Add the remaining module kinds (sidebar, four-tile, premium desktop/mobile, logo).
58. Add an A+ export that emits each module at exact size plus a manifest.
59. Validate total module count against Basic vs Premium limits before export.
60. Add comparison-chart row/column editing with keyboard reordering.
61. Add lazy-loading via IntersectionObserver for module galleries.
62. Add hotspot metadata for Premium A+ interactive modules.
63. Add a fixed-column simulation at 970 / 728 / 344 px for review.
64. Add currency and unit toggles driven by the target marketplace.
65. Add a whitespace-density guard (min margin between text blocks).
66. Add a fallback layout for extreme aspect ratios (tall bottles).
67. Add per-module alt-text fields with required validation.
68. Add a naming-convention enforcer `SKU_MODULE_VIEW_VERSION`.
69. Add ZIP bundling of a full A+ page with its manifest.
70. Add a11y checks: text overlay contrast on the actual rendered pixels.

## E. Prepress and structure (71–85)

71. Validate glue-tab polygons do not intersect fold zones.
72. Add material thickness profiles that shift fold lines by half the caliper.
73. Add nesting/sheet-layout optimisation for print runs.
74. Add a fold-resistance/stress map on the dieline.
75. Add perforation and tear-strip line encoding.
76. Enforce 300 DPI equivalent on every raster placed into a dieline.
77. Add a preflight summary that blocks hand-off on any open defect.
78. Add printer-ready manifest JSON per dieline.
79. Add Pantone/CMYK swatch validation against brand memory.
80. Add bleed-to-trim intersection verification.
81. Add die-cut boundary masking for custom shapes.
82. Add structural stacking-load sanity checks from material + dimensions.
83. Add a print-finish cost estimator tied to material and area.
84. Add dieline JSON sidecars with geometry + metadata.
85. Add regression fixtures: three reference dielines that must remain byte-stable.

## F. Operating loop, memory, governance (86–100)

86. Wire `/api/design-studio/render-brief` into the actual render call (route exists, caller not).
87. Wire `/listing-handoff` into the Listing Forge create flow.
88. Persist brand proposals through an operator-approved store and show them in a review queue.
89. Add a margin-change trigger that re-renders when the price moves across a tier boundary.
90. Add keyword drift detection: if the top keyword changes, flag the hero for review.
91. Add a per-account "winning prompt" index with vector retrieval at prompt-build time.
92. Add a cost ledger entry per render (time, watts estimate, credits = 0).
93. Add a run journal for creative jobs (who/what/when/hash), mirroring Chrome Connect.
94. Add a crash-recovery checkpoint between plate and composite stages.
95. Add a gateway-down fallback that queues jobs instead of failing them.
96. Add a CI target that runs pytest + npm test + build on every creative-module change.
97. Extend the drift-parity test to every numeric constant shared between Python and JS.
98. Add a "materials tier" audit that flags premium renders on sub-35% margin products.
99. Add an operator dashboard tile: plates refused, OCR boxes, render seconds, VRAM peak.
100. Add a weekly self-improvement report generated from the run journal, not from memory.
