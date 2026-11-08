# Spec — Package Designer

Status tags: **REBUILT** (built from this spec, no third-party code) · **UNVERIFIED** (claim not
confirmed by observation this pass).

## 1. Behaviour being modelled

Every packaging tool the operator named (Packify, Pacdora, Cubit, Mockey, Artboard Studio) is
described in the blueprint as working the same way: **collect dimensions and panel content first**,
then produce artwork. The blueprint states this; it is recorded here as
**UNVERIFIED against the products themselves** — none was observed in this pass.

What Northstar therefore requires (derived from the operator's own gap report, not from a
competitor): a complete package = front + back + side + dieline + mockup.

## 2. Inputs

Required (the build refuses without them):

| Field | Why |
|---|---|
| `title` | the product name exactly as printed |
| `weight` | net quantity — a legal requirement |
| `dims.width_mm / height_mm / gusset_mm` | the dieline and the mockup fit both derive from it |
| `ingredients` **or** `supplement_facts` | printed legal copy |
| `company` | back panel identity |
| `address` | back panel identity |
| `country_of_origin` | customs/consumer requirement |

Optional: `subtitle`, `claims`, `icons`, `suggested_use`, `warnings`, `supplement_facts`,
`lot_code`, `keywords`, `plate_asset_id`, `logo_asset_id`.

## 3. Workflow

```
request
  → router classifies (package_designer)
  → missing_inputs()        → questions (stop here by default)
  → render front panel      (real logo, real fonts, drawn cert icons)
  → render back panel       (legal block + reserved barcode zone + lot area)
  → render side panel       (brand, weight, claims, cert marks)
  → panel sheet             (flat, labelled, for review)
  → dieline                 (doypack template → SVG + PDF, same dimensions)
  → mockup                  (front composited onto a plate, if supplied)
  → validate_panels()       (ready_for_print + missing + warnings)
```

## 4. Edge cases and failure modes

| Case | Behaviour |
|---|---|
| Vague request ("a pouch") | refuses, returns the required-input list |
| Missing one legal fact | refuses by default; `allow_incomplete` draws `[MISSING: field]` **on the artwork** |
| Unusual aspect ratio | builds, but warns that the height/width ratio is outside the 1.2–1.9 band |
| Prohibited claim | builds, but warns that claims are rendered as supplied and must be screened |
| No plate supplied | panels + dieline still produced; mockup skipped with a warning |
| Dieline params out of range | `design_studio_print.sanitize_params` raises; the tool returns an honest error |

## 5. Quality bar / validation

- all three panels + sheet present, valid PNG
- dieline SVG starts with `<`, PDF starts with `%PDF`
- dieline pouch dimensions equal the requested dimensions (flat-sheet width is reported separately
  and must not be confused with the pouch width — a real bug caught in test)
- barcode zone reserved, never drawn as a fake barcode
- net weight and company/origin present before `ready_for_print` is true

## 6. What the studied tools reportedly do better — and what Northstar does better

**Packify, verified 2026-10-23** from its own public API documentation (captured 2026-10-16,
`research/packify_dyp_re_20261016/packify_public_api_docs_extract.txt`; capability map in
`research/packify/capability-map.md`):

- Packify splits the job into **design generation** and **photoshoot**, where the photoshoot call
  takes *explicit placement coordinates* (x, y, display width/height, crop box, rotation, source
  size). That is geometry, not generation — the same conclusion this compositor reached
  independently.
- Its **Conversational Mode is marked "Coming Soon"**; only direct generation ships. Northstar's
  router + required-input gate is therefore ahead on the "collect first, render second" axis.
- Packify offers **2K output** for 1:1/16:9/9:16 (our lane caps the long edge at 1216 px) and a
  **mockup template library** (we have one measured-face compositor and the doypack family).

Northstar's stated improvements:
1. **Refuses to invent legal copy** — a missing fact is a `[MISSING: field]` marker on the artwork.
2. **Measures the face** instead of requiring a manual quad pass.
3. **One source of truth** feeds packaging, listing and A+ from the same facts.
4. **Local and free**, with a per-job ledger instead of credit-gated API access.

## 7. Known limits

- Geometry is a *planning* dieline (seal style assumed K-seal); a converter's die drawing is the
  authority.
- The mockup fit is measured from the render, not from the die.
- No 3D preview.
