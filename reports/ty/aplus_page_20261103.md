# A+ content: a complete page from product copy, every module measured

**Date:** 2026-11-03 · **Commits:** `ebca86a7` (page + API), `14605a9d` (real tiles) · **Probe:** t19 PASS · **Tests:** 9 passed.

The A+ renderer already had module geometry, type fit, contrast and a `qa` block. What was missing was the brief: product copy → a complete page. That now exists, exposed through the product API.

## The page

`aplus_brief.page_copy()` maps the declared product facts to six beats:

| Module | Canvas | Live bytes |
|---|---|---|
| header | 970×600 | 361,239 |
| three_tiles | 970×300 | 210,650 |
| comparison | 970×600 | 33,997 |
| banner | 970×300 | 186,009 |
| premium_desktop | 1464×600 | 359,313 |
| logo | 600×180 | 8,299 |

Every module is rendered by `aplus_render.render_module` and passed through `assert_perfect`:
exact canvas, real contrast under every text block, type ≥ 14 px, under 2 MB, prohibited copy
screened before a pixel is written. The page total is **1,159,507 bytes**, `ok: true`, no problems.

`POST /api/design-studio/aplus-page` takes the copy and a plate picture and returns each module as a
PNG data URL with its QA, canvas and sha256. `GET /modules` lists the page order. A prohibited claim
returns **422** with the reason (measured: `prohibited A+ copy: cures`).

## The defect the live page exposed

The first live page used a **gold-circle placeholder** for the three-tile module: `build_page` fell
back to synthetic tiles when none were passed. A page that claims to be a deliverable cannot carry
placeholder art. It now derives square crops from the supplied plate at evenly spaced heights, so
every tile is the actual product. Pinned by a test that two different plates produce different
`three_tiles` bytes.

Before: 13,836 B / sha `4e59b56a3129` (placeholder). After: 210,650 B / sha `00e1ad66116f` (real crops).

## Determinism and safety

- Building the same page twice produces identical module hashes (t19).
- Prohibited copy (price, promotion, shipping, competitor, medical) is refused by the renderer's own
  screen; the page cannot smuggle a claim past it.
- The page is deterministic local rendering; no model call, no network.

## Honest gaps

- **The header crops a portrait plate hard.** The live header shows the pouch's label cut at the
  image panel's edge; a landscape or square product photo composes better. The renderer's `cover` is
  correct for a full-bleed panel; the plate choice is the issue.
- **The tiles are three crops of one picture**, not three different scenes. A real page would use
  distinct lifestyle/detail shots.
- **`single` and `sidebar` are not in the default pack** (300×300 thumbnail beats); they render, but
  are not part of this story.
- **No file storage / no UI wiring.** The endpoint returns data URLs and hashes; the caller persists.
- **Amazon A+ module specs are not re-read here.** Geometry is this repo's declared contract; Amazon
  compliance is not claimed.

## Files

`Northstar_backend/aplus_brief.py`, `aplus_page_api.py`, `test_aplus_brief.py`,
`test_aplus_page_api.py`, `state/probes/t19_aplus_page.py`. Live page:
`renders/mogra_lions_mane/aplus/*.png` (gitignored).
