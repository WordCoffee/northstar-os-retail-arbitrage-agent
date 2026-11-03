# Item 0 — designed product pictures: done, with the gaps named

**Date:** 2026-11-03 · **Commits:** `4cf60335` (compositor + legibility), `91bee21a` (product picture
API), `03df3301` (OZ/0Z gate fix) · **Probes:** t9/t10/t11/t12 PASS · **Tests:** 89 + 8 passed.

The owner asked for a product picture of a 6 oz stand-up pouch, front and back, fully designed,
with a nutrition label. What had been delivered was two flat labels. This pass closes that gap
through the product's own HTTP API, not a shell-side compositor.

## What runs now

```
python tools/render_product_picture.py --out renders/mogra_lions_mane --seed 20261103
```

The command POSTs to `POST /api/design-studio/product-picture`. The endpoint:

1. renders a **blank** kraft pouch plate with FLUX 3 (local ComfyUI) through
   `text_fidelity.render_with_text_guard(..., text_safe=True)` — lettering is detected, retried with
   a hardened prompt, reconstructed, or the face is refused (`plate_has_lettering`);
2. measures the printable face with `pouch_label.measure_face` (chroma segmentation, sub-pixel side
   edges, RANSAC quadratic fit, weld/base insets) — a plate with no package is refused
   (`plate_face_not_found`), never composited;
3. warps the designed panel onto that quad with `mockup_compositor.composite_panel_onto_quad`
   (pixel-centre homography, content-trim crop, antialiased edge, surface realism); pixels outside
   the measured face stay photographic;
4. OCRs the finished picture with `mockup_quality.assert_legible` and only writes
   `product_front.png` / `product_back.png` when the wordmark and net weight are read and the type is
   sharp. A failure is kept under `_rejected/` with the named reason.

The panel artwork lives in `Northstar_backend/mogra_label_art.py` — the same panels the label CLI
writes. Text is drawn, never diffused. The back panel now carries the net weight in addition to the
Supplement Facts block.

## Evidence (measured, this run)

| Check | Result |
|---|---|
| `state/probes/t10_pouch_mockup.py` | **OK** — plate-size output, corners painted, nothing outside the quad |
| `state/probes/t11_mockup_legibility.py` | **OK** — sharp composite accepted, blurred one refused |
| `state/probes/t12_plate_pair.py` | **OK** — flat plate refused with `plate_face_not_found` |
| `state/probes/t9_feather_sigma.py` | **PASS** — NaN/±inf refused, finite values clamp |
| API response | `ok: true`, engine `flux3-comfyui`, `armed: true`, model `flux3-image-klein-nvfp4`, tier `final` |
| `product_front.png` | 1024×1536, 1,663,119 B, seed 20261103, quad `[[212.4,434.0],[823.5,434.0],[793.2,1214.0],[245.0,1214.0]]`, gate **ok** (median text sharpness 5240.9) |
| `product_back.png` | 1024×1536, 1,654,848 B, seed 20261104, quad `[[246.6,486.0],[777.1,486.0],[744.9,1189.0],[287.5,1189.0]]`, gate **ok** (sharpness 20297.9) |
| OCR words, front | `MOGRA`, `ORGANICS`, `LION'S MANE`, `MUSHROOM POWDER`, `NET WT. 6 oz (170 g)` |
| OCR words, back | `MOGRA ORGANICS`, `NET WT. 6 0Z (170 G)`, `Supplement Facts`, `Servings per container 85`, `2,000 mg % DV`, `LOT LM-0000` |

Engineering defects found by doing it, and fixed:

- **`fold_shadow: 0.35` at `fold_threshold: 0.05` treated ordinary kraft shading as a crease and
  multiplied the cream label down to 169/255** (first live picture). The realism recipe is now tuned
  for print on a lit face: `fold_shadow 0.12 / fold_threshold 0.10`, matte `specular_cap 0`.
- **The plate's specular patch washed out the design.** Surface maps are measured before the label
  area is flattened; the flatten happens after, so creases still displace the ink but a photographic
  highlight cannot sit on the label.
- **`scripts/start-flux3.ps1` never started ComfyUI from this repo.** `Start-Process` joins
  `-ArgumentList` with spaces and the repo path contains one, so `-File` received
  `C:\Users\T2Hol\Desktop\Northstar`. The path is quoted now.
- **The legibility gate refused a readable picture** because RapidOCR read `6 oz` as `6 0Z`. The
  comparison folds O→0; it is still about whether the weight was read.
- `test_plate_geometry.py` pinned the old silent NaN default. It was corrected to the t9 contract —
  the probe is the authority; the test was encoding the defect.

## Honest gaps (not fixed here)

- **The front and back are two different generations**, so they are not the same physical pack.
  The definition of done allows this; a true pair needs one plate rendered twice (front/back) or a
  turnaround render. Recorded for the next unit.
- **The design is a cream label on kraft, not full-bleed print.** It reads as a label on a pouch,
  which is a legitimate SKU style, but a full-bleed wrap is not implemented.
- **The draft marks are intentional.** Nutrition values and the UPC are placeholder; the panel says
  DRAFT. Verification remains the operator's (and Amazon specs remain behind the standing gate).
- **The API is unauthenticated only through the documented dev shim** (`ENVIRONMENT=development`,
  loopback, demo org). A hosted call needs a bearer token; nothing was weakened.
- **No A+ / listing-image / social / video contract yet.** The same standard — placement contract,
  measured quad, OCR, `ffprobe` for video — is the next work order, not a claim.

## Files

`Northstar_backend/mogra_label_art.py`, `product_picture.py`, `product_picture_api.py`,
`test_product_picture.py`, `main.py` (router), `mockup_compositor.py` (composite/find/feather),
`mockup_quality.py`, `tools/render_product_picture.py`, `tools/render_mogra_label.py`,
`scripts/start-flux3.ps1`. Generated (gitignored): `renders/mogra_lions_mane/product_front.png`,
`product_back.png`, `product_picture_manifest.json`.
