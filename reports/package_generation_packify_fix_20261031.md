# Product package generation — Packify-parity tranche (2026-10-31)

## What was broken

The package path was pouch-only and visually flat:

| Layer | Before | Effect |
|---|---|---|
| `specialists/package_designer.py` | Required `width_mm/height_mm/gusset_mm`; built a doypack only | A box, bottle or tube request could not become a package |
| Front panel | `pouch_label.render_label` (cream field + centred text) | No designed front; below Packify's concept-level output |
| Chat tool `build_package` | Called the pouch-only designer and saved with `pd.save_package` | The agent could not produce the new formats |
| Panel resolution | Default 900×1200 panels | Not 300 DPI on an 80×180 mm carton or long tube |
| Print reporting | Mockup-plate DPI was presented as `print_ready` | A 300 DPI label design was reported "not print-ready" because the *preview* plate was 1024 px |
| Validation | Pouch 1.2–1.9 height/width heuristic ran on every format | A normal 2.25 carton ratio produced a false warning |

## What shipped

- **`Northstar_backend/package_pipeline.py`** — one contract for `pouch`, `box`, `bottle`, `tube`:
  designed front → back → side → flat sheet → print dieline (SVG + PDF) → measured mockup → manifest.
- **`Northstar_backend/package_art.py`** — dynamic, product-agnostic front design system:
  seven palettes (`forest`, `midnight`, `kraft`, `bone`, `clay`, `sage`, `slate`), proportional layout per face,
  fitted title/subtitle, hero motif, claim stack, drawn certification icons, net-weight capsule, paper grain.
  Certifications are drawn only when `organic_certified` is set.
- **`package_designs.py` integration** — a `design` key can select one of the existing Mogra catalogue fronts;
  otherwise the dynamic renderer is used.
- **`pouch_label.compose(label_panel=...)`** — the pouch compositor can now consume the designed front
  instead of re-rendering the old plain label; default behaviour is unchanged.
- **300 DPI panel artwork** — front, back and side are rendered for the real face dimensions. The manifest
  separates `artwork.dpi` / `print_ready` (print file) from `mockup_dpi` / `mockup_print_ready` (preview plate).
- **Chat/agent path** — `_t_build_package` now calls the four-format pipeline; its schema accepts
  `format`, `depth_mm`, `diameter`, `label_height`, `label_top_offset`, `brand`, `theme`, `design`, `servings`
  and `organic_certified`.
- **Format-aware validation** — the pouch aspect-ratio warning only runs for pouches.
- **CLI** — `tools/build_package_formats.py` builds a full set and a contact sheet:
  `python tools/build_package_formats.py --out exports/packages_packify_20261031_release`.

## Evidence

### Automated

```text
121 passed, 1 warning in 40.94s
  test_chat_tools.py
  test_package_pipeline.py
  test_package_design.py
  test_package_designs_j.py
  test_package_readiness.py
  test_specialists.py
  test_gateway.py
  test_pouch_label.py
  test_pouch_label_geometry.py
  test_pouch_label_placement.py
```

The 11 new pipeline tests cover all four formats, the panel/dieline/mockup contract, the manifest
round-trip (no raw bytes), format-specific missing inputs, mm-true 300 DPI fronts and theme fallback.

### Live renders

`exports/packages_packify_20261031_release/`

| Format | Artwork DPI | Mockup DPI | Geometry residual | OCR gate |
|---|---:|---:|---:|---|
| pouch | 299.97 | 104.52 | 0.366 px | text present |
| box | 300.00 | 95.95 | 0.159 px | text present |
| bottle | 299.72 | 38.07 | 0.208 px | text present |
| tube | 299.72 | 97.70 | 0.255 px | text present |

Every set contains `front`, `back`, `side`, `sheet`, `mockup`, `dieline_svg`, `dieline_pdf` and a
JSON manifest with the sanitized product spec, dimensions, surface measurement and quality verdict.
Contact sheet: `exports/packages_packify_20261031_release/contact_sheet.png`.

### Ty’s Assistant

- `tys_5e73b1a837b9` — first research order. Inspect steps completed; the coding step fell back to the
  1.9 B local model and returned an unusable material snippet. The 27 B lane was not started because free
  RAM was below the 3 GB floor. Recorded as a lane limitation, not a passing research result.
- `tys_4e9dd69a9dc8` — review order with `qwen3.5:2b`. It completed. One finding was valid and shipped:
  the manifest omitted the product spec snapshot. Two others were checked and rejected: ingredient/supplement
  validation already exists in `missing_inputs`, and the reported “residual” formula is actually the
  confidence helper; `geom_residual_px` itself is unchanged.

## Remaining gap to Packify parity

This is a substantial tranche, not a claim of pixel-for-pixel parity:

1. The dynamic front has one composition with seven palettes; Packify offers many distinct layouts.
   The existing Mogra catalogue is selectable but brand-specific.
2. Back/side panels are legally complete but visually plain; they need a designed legal layout.
3. Mockups are measured from 1024 px plates, so the preview DPI is 38–105. The label artwork is 300 DPI
   and the dieline is vector; a print mockup would need a larger plate or an operator photo.
4. Dielines remain draft geometry until confirmed with the converter.
5. No operator visual sign-off / physical proof has been run.

## Reproduction

```powershell
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
python tools\build_package_formats.py --out exports\packages_packify_20261031_release
python -m pytest Northstar_backend\test_package_pipeline.py -q
```
