# MOGRA i-series v2 — sharp logo master + full-lockup redo (2026-10-18)

Operator report: "it's not using our logo. Redo them all, but first turn our logo image
into a clearer, sharper image of the exact same."

**Constraint of record:** the session model cannot view images (harness: "this model does
not support image input"). Everything below is therefore measured numerically - pixel
statistics, mask IoU, edge-slope metrics, overlap audits and md5 file identity - and the
operator is asked to eyeball the two review images named at the end.

## What was actually wrong (all found by measurement, not by eye)

1. **The logo master was soft.** `exports/mogra_logo_master.png` was a plain 4x LANCZOS
   upscale of the supplied artwork (opaque, cream field). No edge treatment.
2. **The wordmark crop sliced the emblem.** The pipeline's `wordmark()` takes the bottom
   52% of whatever master it is given. In the old master that cut (row 208.5 of the
   source) lands on the mortar base - every stamp carried a clipped sliver of the base
   above the letters.
3. **Only the wordmark band was stamped - never the full logo** (emblem + EST 2023 +
   wordmark + tagline) on any i-series front, despite the series being the "identity"
   series (i01_logo_monument … i10_logo_hero).
4. **Two designs stamped the logo in its own background colour** (invisible logo):
   - i07_asymmetric_corner: PLUM2 stamp on PLUM2 ground (headline + rule too)
   - i08_logo_in_shape: IVY stamp on the IVY rounded rect ("reversed out" means the
     ground colour must be used)
   The overlap audit surfaced both as near-zero stamp-ink panels (797 px / 2,021 px
   against 10k-70k for the rest).

## Deliverables

### 1. Sharp logo master v2 (the "clearer, sharper, exact same" image)
- `exports/mogra_logo_master_v2.png` — 2336×2008 RGBA, 8x, transparent paper field.
- `exports/mogra_logo_before_after.png` — side-by-side review sheet (old 4x vs v2,
  full lockup + the wordmark band at native pixels).
- `exports/mogra_logo_qa.json` — the measurements:
  - source md5 == operator copy md5 (`8b476a1e…`, byte-identical artwork)
  - mask IoU vs source **0.9862** (geometry unchanged - "exactly the same thing")
  - edge slope at 8x: 0.090 → 0.153 (**1.70x sharper** than a plain upscale)
  - the pipeline cuts now land inside the artwork's true blank gap:
    cut52 = 130.5, cut55 = 138.0, gap = rows 127..142 (bottom pad 39 px)
- Built by `Northstar_backend/refine_mogra_logo.py` (deterministic; asserts IoU ≥ 0.95,
  sharpness ≥ 1.20x and the cut invariants - it fails loudly if the artwork changes).

### 2. Full redo of the 10 designs (front + back + shelf mockup each)
- `exports/mogra-lionsmane-6oz-i-series-v2-20261018/` — 48 files, flat single folder:
  `iNN_*_front.png`, `iNN_*_back.png`, `iNN_*_shelf_front.png`,
  `iNN_*_shelf_back.png`, both contact sheets, READMEs, BACK_LABEL_REQUIREMENTS.md.
- Fronts now stamp the **full lockup** (emblem + EST 2023 + wordmark + tagline), sized so
  the visible logo is 1.25x what the old wordmark-only stamps showed (20–58 mm visible
  width), ink-centred on the old anchors; compositions otherwise unchanged.
- Backs keep the regulated layout; the header now carries the full lockup
  (identity series only - other series keep the legacy wordmark header).
- i07 and i08 ink fixed (MOON on PLUM2; MIST on IVY) so the logo and headline are
  actually visible.

### 3. Overlap audit (no vision needed)
`Northstar_backend/tools_i_series_audit.py` renders every panel twice (with/without the
lockup), diffs them, and measures whether the lockup's ink intersects pre-existing
elements. Result: **all 20 panels 0.000% collision**, no empty stamps; every exported
panel is verified to carry the lockup (leaf-green pixels present in all 40 panel files,
e.g. i01 front 6,096 px). Evidence JSONs: `reports/i_series_lockup_audit_*.json`.

## Code changes
- `Northstar_backend/package_designs.py` — `set_logo_assets()` + `lockup_stamp()`
  (visible-bbox-centred, keeps green leaves); i01–i10 use it; i07/i08 ink fixes;
  `render_back` stamps the lockup when the spec sets `logo_lockup=True`; i-specs set it.
- `Northstar_backend/export_mogra_designs.py` — `--logo-master <file.png>` flag;
  without it, the v2 master is auto-built via `refine_mogra_logo.build_master()`.
- New tools: `refine_mogra_logo.py`, `tools_i_series_audit.py`, `tools_analyze_logo.py`.

## Honest limits
- No vector master: `vtracer` is not installed (noted in the pack README). The 8x raster
  with 1.70x edge gain is what ships; a true vector trace remains an optional follow-up.
- The operator's review images are the final judge of "sharper and the same": check
  `exports/mogra_logo_before_after.png` first, then the new pack's contact sheets.
- Placeholder regulatory values on the backs are unchanged (see
  BACK_LABEL_REQUIREMENTS.md).

## Ask
1. Open `exports/mogra_logo_before_after.png` - confirm the v2 logo is the same artwork,
   now crisp.
2. Open `exports/mogra-lionsmane-6oz-i-series-v2-20261018/contact_sheet.png` (and
   `contact_sheet_mockups.png`) - confirm the full lockup placement per design.
3. Say which design(s) proceed; logo stamp sizes are single numbers in
   `package_designs.py` if any need nudging.
