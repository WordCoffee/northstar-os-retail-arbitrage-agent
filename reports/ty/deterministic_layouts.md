# Deterministic infographic and packaging pipelines

Owner ask (2026-11-09): *build infographic and packaging_mockup as deterministic pipelines — HTML/
Playwright or Pillow text and callout layout over generated imagery for infographics; perspective
warp or template mapping of real artwork onto the dieline for packaging. Use the Lion's Mane pouch
as the target and show source-next-to-output.*

Both stages are built, both run on the real Mogra pouch, and the sheet is
`reports/ty/layout_demo_source_next_to_output.png`.

## The result on the Lion's Mane pouch

| brief | situation | score | verdict | what failed |
|---|---|---|---|---|
| LM-DET-01 | infographic | 79.2 | fail | `reference_subject` — printed text 5/9 words (0.56, min 0.60) |
| LM-DET-02 | infographic | **100.0** | **pass** | — |
| LM-DET-03 | packaging_mockup | 76.2 | fail | `reference_subject` — printed text 5/9 words (0.56, min 0.60) |
| LM-DET-04 | packaging_mockup | **100.0** | **pass** | — |

Every geometric rule now passes on all four: `aspect` 0.8000 vs 0.8000, `dimensions` 1600×2000 /
2000×2500, `subject_fill` 33.8–75.1 % against 10–80 %, `text_free` margin ink 2.91 % against a
0.20 % floor, and `product_region` structure **0.959–0.962** — the real cutout, verified at the
recorded placement (infographic) or at the recorded quad (packaging).

The two failures are the same failure, on the same source image, in both situations: `mogra_pair_main.png`
is two pouches photographed together, and when one of them is 10–15 % of a page the OCR cannot
recover 9 of the expected 9 words (it recovers 5). That image also under-recovers before any layout
is applied, so this is the source's legibility, not the layout's geometry. The other Mogra image
scores 100 in both stages.

## What each stage actually does

**Infographic (`deterministic.infographic`)** — a page, not a full-bleed collage:

1. the generated scene (with the real product already placed by the composite path) becomes a
   **70 %-wide photo panel** inset on the page;
2. the product's box is **mapped through the panel transform** and returned, so the product-region
   audit still compares the seller's pixels at the right place;
3. the title, the `product guide` subhead, three **callout chips with leader lines** and the footer
   are drawn in the margins — the chips sit *outside* the panel and point in, so nothing is drawn
   over the product;
4. the page is composed at the **brief's own aspect** (4:5), by extending the square render with a
   mirrored, darkened band — never by cropping the product.

**Packaging (`deterministic.panel_warp`)** — the seller's artwork on a panel:

1. the placed artwork is perspective-warped into a **quad** inside its own bounding box (the far
   edge pulled in by 6 %), with a vertical shading gradient so the face reads as a surface;
2. the quad is recorded, and the product-region check **warps the cutout with the same homography**
   before comparing (`quad_similarity`), so a warped panel is compared like with like instead of
   being reported as a fidelity failure;
3. wide subjects are capped at 0.55 of the frame height for this situation, which is what brings
   `subject_fill` inside 15–80 % on a 4:5 page.

Both are deterministic: the same brief and inputs produce byte-identical output, which is asserted
in `test_seller_deterministic.py` (16 tests) rather than claimed here.

## Two defects this work found in the scorer

1. **The product-region check compared the canvas aspect, not the subject's.** A pouch pair on a
   square canvas is a 1.86:1 subject; the guard compared 1.00 to 1.86 and returned
   `cannot_verify — this is not the same subject` on a correct composite. It now measures the
   subject's alpha bounding box.
2. **The quad path compared the whole canvas.** `place_product` pastes the trimmed subject, so
   warping the full canvas into the quad compared the product plus its transparent margins
   (structure 0.33). It now trims first, and the same panels read 0.96.

And one in the generator, which the demo run caught and a test now covers: the record's box is
`(left, top, right, bottom)` while the layout helpers work in `(x, y, width, height)`. Mixing them
produced a box 6.10 wide for a 1.40 subject. The conversion now happens in exactly one place, and
the test asserts the quad sits inside the box.

## Not done, and queued

- **A real dieline** (front, side and bottom faces with fold shadows) rather than a single warped
  panel — `sel-05-dieline`.
- **The seller's own copy**: the callouts currently say *where* the product is ("front view",
  "label", "net weight"). A renderer must not invent a claim, so the page carries structural labels
  until a brief supplies copy — `sel-06-infographic-copy`.
- The `mogra_pair_main` OCR limitation above is a property of that photograph; a single-pouch
  reference, or a larger panel with fewer words expected, would clear it.
