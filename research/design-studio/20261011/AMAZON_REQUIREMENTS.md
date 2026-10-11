# Amazon creative requirements — reference for the NorthstarOS Design Studio research

**Scope:** current Amazon requirements for listing creative, A+ Content, Storefront assets and
Sponsored ads creative, plus prohibited-content / prohibited-claim rules.

**Research date:** 2026-10-09 (UTC). **Researcher:** Amazon-compliance & seller-voice subagent.

**Evidence classes** (per `RULES.md` R0): VERIFIED = directly observed on a public page/doc during
this research; REPORTED = claimed by a third party or by a vendor page but not observed;
UNKNOWN = not confirmed, including fetch failures.

**Universal date-sensitivity notice (R6):** Amazon requirements change without notice. Amazon
itself states it "periodically updates our policies" and reserves the right to reject, remove or
request modifications to any ad "at its sole discretion, for any reason"
(S403). **Every requirement row in this document is `date_sensitive: yes`.** Nothing here should
be shipped as a hard-coded constant in the Design Studio without a re-verification pass and a
visible "verify against Seller Central" affordance.

---

## Retrieval notes (important for reading this document)

Several canonical Amazon surfaces are **client-rendered single-page applications** and returned
only navigation chrome to an unauthenticated fetch:

| Official page | Result |
|---|---|
| `sellercentral.amazon.com/help/hub/reference/...` (Product image requirements, A+ Content guide, etc.) | `UNKNOWN (fetch failed: SPA — HTML shell only, article body loaded by JS)` (S420) |
| `advertising.amazon.com/resources/ad-policy/en/sponsored-ads-policies` (Sponsored ads guidelines & acceptance policies) | `UNKNOWN (fetch failed: empty body, client-rendered only)` (S421) |
| `advertising.amazon.com/resources/ad-policy/en/stores` (Stores guidelines & acceptance policies) | `UNKNOWN (fetch failed: same)` (S422) |
| `advertising.amazon.com/resources/ad-policy/en/creative-acceptance` (Amazon Ads Guidelines & Acceptance Policies) | `UNKNOWN (fetch failed: same)` (S423) |
| `advertising.amazon.com/resources/ad-policy/en/sponsored-display-policies` | `UNKNOWN (fetch failed: same)` (S424) |

Where a canonical help page could not be reached, this document substitutes the **closest
reachable official Amazon property**:

- Amazon's own **Seller Forums** on `sellercentral.amazon.com` and `sellercentral.amazon.co.uk`
  (server-rendered, official Amazon property, posts by Amazon employees) — used for product-image
  requirements (S415, S416).
- Amazon's own **PDF guides hosted on `m.media.amazon.com`** (sp-marketing-toolkit /
BX_Marketing) — used for A+ Content Basic, Premium and Brand Story module specs (S410–S413).
- **Amazon Ads** `advertising.amazon.com` ad-specs, ad-policy and library pages that *do*
  server-render — used for Stores, Sponsored Brands, Sponsored Display / eCommerce creative and
  advertising policy (S400–S409).

Third-party summaries were **not** used to fill Amazon requirement rows. Where a third-party
summary is quoted at all it is labelled REPORTED and appears only in
`SELLER_PAIN_POINTS.md`, never as a requirement source.

---

## 1. Main image (the "hero" image)

**Rule.** The first image on the detail page — the one shown to customers in search results —
must show only the product for sale on a white background, and the product should fill the image
frame. Additional images should show the product in use or in an environment, different angles
and different features.

**Concrete specs (as published by Amazon):**

| Spec | Value |
|---|---|
| Minimum image count per detail page | 1 image required |
| Recommended count | 6 images + 1 video |
| Longest-side pixel range (all images) | 500 to 10,000 px |
| Preferred longest side for zoom | >1,000 px (Amazon: "we prefer images to be larger than 1,000 pixels on the longest side to allow for zoom") |
| Accepted file formats | JPEG (.jpg/.jpeg, preferred), TIFF (.tif), PNG (.png), non-animated GIF (.gif). Animated GIFs not supported by Amazon's servers |
| Product fill | The product must fill **at least 85%** of the image |
| Background | White |
| Prohibited on MAIN | Text, logos, borders, colour blocks, watermarks or other graphics over the top of the product or in the background |
| Packaging | MAIN images must show products outside their packaging; boxes, bags or cases must not appear unless an important product feature |
| Quality | Images must not be blurry, pixelated or have jagged edges; all images must accurately represent the product for sale |

**Enforcement.** Images that do not meet these standards "may be rejected, removed, or altered.
Non-compliant images can lead to product listing suppression from search results." Where
multiple selling partners supply images for the same product, Amazon selects the images it judges
best meet its requirements — uploading an image does not guarantee it is displayed, and Amazon
may select different images from those supplied by the brand owner.

**Sources:** S415, S416 (Amazon employee posts on Amazon Seller Forums, both explicitly
summarising Amazon's "Product image requirements" help page).
**URLs:** https://sellercentral.amazon.co.uk/seller-forums/discussions/t/4b3c4c39-6f8c-4312-aa0e-99982eb8f5e1 ·
https://sellercentral.amazon.com/seller-forums/discussions/t/99a0dc92-15dc-492a-b24e-f327f4c28dd5
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED · **`date_sensitive: yes`**
**Compliance-limit note:** the canonical *Product image requirements* and *main image requirements*
help pages themselves are JS-gated and could not be retrieved (S420), so these rows come from
Amazon's own summary of that page on an official Amazon property rather than from the page
itself. Treat wording as authoritative-but-secondhand. The 85% fill figure and the
"no text/logos/borders" rule are stated by Amazon in those posts. Category-specific main-image
rules (e.g. apparel mannequin/flat-lay conventions) were **not** retrieved.

---

## 2. Secondary images

**Rule.** Secondary images should show the product in use or in an environment, different
angles, and different features. They carry the same technical requirements as the main image.

**Concrete specs (as published by Amazon):**

| Spec | Value |
|---|---|
| Longest-side pixel range | 500 to 10,000 px |
| Formats | JPEG (preferred), TIFF, PNG, non-animated GIF |
| Quality | Clear, no pixelation, no jagged edges, must accurately represent the product |

**Text / graphics on secondary images — Amazon's own guidance conflicts.** Amazon's "Quick Tip"
post (S416) restricts the *no text* rule to MAIN images only. A seller reply on S415 records
finding contradictory language across Amazon's own style guides — one requirements page stating
"No text or pricing details (Swatch only)" and a Quick Start Style Guide warning that
"Borders, watermarks, text, or other decorations" can trigger a quality alert. That conflict is
**not resolved by any Amazon source reachable in this research**.

**Sources:** S415, S416.
**URLs:** as above. **Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED ·
**`date_sensitive: yes`**
**Compliance-limit note:** the dedicated "requirements for all product images" help page could
not be retrieved (S420). Whether text/graphics are permitted on secondary images is therefore
**UNKNOWN as a matter of Amazon's current published rule**, even though infographic-style
secondary images are ubiquitous in practice.

---

## 3. Infographics / text-on-image usage in listing images

**Rule (confirmed parts).** No text, logos, borders, colour blocks, watermarks or other graphics
on the MAIN image (S416). For secondary images, the prohibition is ambiguous — see §2.

**Rule (A+ Content surface, where text-in-image restrictions are actively enforced).** Amazon's
A+ guides instruct sellers to "limit the amount of text embedded in images" and to use the
descriptive text fields instead, because text inside images is not read by search engines or
screen readers (S411, S412, S414). The Stores creative guidelines repeat the same instruction:
"Uploading images with embedded text is not encouraged. The text will not be readable by search
engines, or by people who rely on screen readers to navigate your Store" (S401). Amazon's KDP
A+ examples page is blunter still for the text-overlay modules: "Don't add text to your
background image. Add text to the overlay box" (S414).

**Observed enforcement (seller reports, see SELLER_PAIN_POINTS.md theme 6).** Sellers on Amazon's
own Seller Forums report Premium A+ images being **rejected for containing a brand logo**, with
the stated reason that "text is no longer allowed on images", and product images rejected because
of text that is part of the physical product itself — one seller cites the word "Volume" printed
below a volume knob being flagged (S430). Separate seller reports describe an Amazon-side "Content
Quality Analysis" that **soft-hides A+ content** flagged for "Lack diverse images" and
"professional usage context" (S432).

**Sources:** S401, S411, S412, S414, S416, S430, S432.
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED (rules) · **`date_sensitive: yes`**
**Compliance-limit note:** there is no reachable Amazon page that states a precise character
budget, minimum type size, or allowed/prohibited word list for text inside *listing* images.
The A+ text-in-image restriction is documented as guidance and as rejection behaviour, not as a
published numeric spec. **Any numeric text-in-image guardrail the Design Studio ships must be
labelled as a heuristic, not an Amazon rule.**

---

## 4. A+ Content — Basic modules

**Eligibility.** Available to Professional sellers approved as brand owners through Amazon Brand
Registry, and to emerging brand owners in certain managed programmes (Launchpad, Amazon
Exclusives). Once approved, A+ Content can only be added to products in the approved brand
catalogue. A+ Content is free for eligible sellers (S428).

**Module count.** Up to **five** Basic A+ Content modules per ASIN (S428). A+ Content lets you
add images and text into five to seven different content modules to highlight product-level
features (S411).

**Global image file requirements (all modules):** `.jpg`, `.bmp` or `.png` — animated GIFs are
not supported; individual image files **no greater than 2 MB**; resolution **at least 72 dpi**;
colour space **RGB** (CMYK not supported). Images larger than a module's maximum will be resized
to fit; images smaller than the module minimum will not be scaled up (S410 — stated for Premium
but published as the standard requirement across modules).

**Per-module minimum image sizes (official Amazon asset-creation guide, S413):**

| Basic module | Min. image size | Notes |
|---|---|---|
| Single Image & Sidebar | 300 × 400 (main) + 350 × 175 (sidebar) | Both images required |
| Single Left Image | 300 × 300 | |
| Single Right Image | 300 × 300 | |
| Four Images & Text | 200 × 200 (up to 4) | Image Keywords field labels 300 × 300 |
| Comparison Chart | 150 × 300 (up to 6) | |
| Four Image Highlights | 400 × 400 | Second image slot listed as `X00xX00` (unresolved in Amazon's own sheet) |
| Single Image & Specs Detail | 300 × 300 | |
| Single Image & Highlights | 300 × 300 | |
| Three Images & Text | 300 × 300 × 3 | |
| Four Images / Text Quadrant | 135 × 135 × 4 | |
| Image & Dark Text Overlay | 970 × 300 | |
| Image & Light Text Overlay | 970 × 300 | |
| All Text | none | Text only |
| Technical Specifications | none | Spec name/definition min 4, max 16 rows |

**Character limits.** Amazon's standard-modules asset sheet publishes **no character limits**;
the A+ Content Manager shows the limit on each text field as you fill it. Reachable Amazon
figures for individual modules: Product Description Text up to **6,000 characters** and
Technical Specifications up to **16 rows** (S414, KDP surface — same module family, different
Amazon programme). From Amazon's SP-API A+ documentation, `StandardSingleImageHighlightsModule`:
main image min 300 × 300 px, image alt text max 100 chars, headline max 160, subheadline max 200,
body max 1,000, bullet max 100, up to 8 bullets (S425).

**Approval workflow.** Review can take **up to seven business days** (longer in high-volume
periods); after approval, publication can take up to 24 hours; **resubmission after rejection
takes another seven business days**. Applying to more than 1,000 ASINs requires the bulk-upload
workflow (CSV/XLS, up to 500,000 ASINs in the first column) (S411).

**Sources:** S410, S411, S413, S414, S428, S425.
**URLs:** https://m.media-amazon.com/images/G/35/sp-marketing-toolkit/Sellerfacingguides/BO/Standard_A_Module_Templates.pdf ·
https://m.media-amazon.com/images/G/01/BX_Marketing/2023/AMZ_Guide_A_BPG_04b_US-4-21-2023.pdf ·
https://m.media-amazon.com/images/G/01/BX_Marketing/2023/AMZ_Guide_Premium_A_Module_05b.pdf ·
https://kdp.amazon.com/help/topic/GCKLH8V7ULLD5EXY ·
https://sell.amazon.com/blog/a-plus-content-design-guide ·
https://developer-docs.amazon/sp-api/lang-US/docs/a-plus-content-examples
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED (S410/S411/S413/S414/S428) and
REPORTED (S425 — retrieved through a search index; the live developer-docs path returns 404) ·
**`date_sensitive: yes`**
**Compliance-limit note:** the standard-modules PDF is undated on its face and the per-module
character limits are not published in any reachable Amazon page. The "Four Image Highlights"
second-image dimension is an unfilled placeholder in Amazon's own template sheet — do not invent
a value for it.

---

## 5. A+ Content — Premium modules

**Source of truth:** Amazon's *Premium A+ Module Guide*, Version 1.0, "Last updated May 30, 2023"
(S410) — an official Amazon PDF on `m.media-amazon.com`.

**Module count.** Up to **seven** modules per ASIN with Premium (S428). Amazon's SP-API
troubleshooting documentation states a Premium document cannot contain more than seven modules,
and that "content documents cannot contain both premium and standard module types" (S426,
REPORTED).

**Global image file requirements:** `.jpg`, `.bmp`, `.png` (no animated GIFs); **≤ 2 MB** per
file; **≥ 72 dpi**; **RGB** (CMYK not supported).

**Module specifications:**

| Premium module | Char limits | Desktop min. image | Mobile min. image | Other limits |
|---|---|---|---|---|
| Premium Full Image | Headline 80 · Body 300 | 1464 × 600 | 600 × 450 | |
| Premium Text | Headline 80 · Body 300 | — | — | |
| Premium Background Image with Text | Subheadline 40 · Headline 60 · Body 300 | 1464 × 600 | 600 × 450 | Text box left/right; text colour black or white |
| Premium Four Images & Text | Subheadline 80 · Headline 30 · Body 150 | 300 × 225 | none (reuses desktop) | |
| Premium Dual Images with Text | Subheadline 50 · Headline 50 · Body 300 | 650 × 350 | none | |
| Premium Single Image with Text | Subheadline 40 · Headline 80 · Body 500 | 800 × 600 | none | |
| Premium Full Video | Headline 80 · Body 300 | video preview image 1464 × 600 | none | Video `.mp4` only, min 960 × 540, ≤ 200 MB, ≤ 180 s. Ideal ≤ 10 s |
| Premium Video with Text | Subheadline 40 · Headline 80 · Body 500 · Video title 50 · Video description 200 | video 800 × 600; preview image 800 × 600 | none | ≤ 200 MB, ≤ 180 s |
| Premium Comparison Table 1 | Module headline 80 · Image headline 25 · Feature 30 · Tooltip 150 · Detail 30 | 200 × 225 | none | Products 4–7, Features 5–12 |
| Premium Comparison Table 2 | Module headline 80 · Image headline 30 · Feature 30 · Body 80 | 300 × 225 | none | Products 2–3, Features 2–5 |
| Premium Comparison Table 3 | Chart headline 25 · Image headline 25 · Feature 20 · Feature text 20 | 488 × 700 | 600 × 450 (per panel) | Products 2–4, Features 3–7 |
| Premium Hotspots 1 | Hotspot headline 50 · Hotspot body 200 | 1464 × 600 | 600 × 450 (per hotspot) | Hotspots 2–6 |
| Premium Hotspots 2 | Module headline 80 · Body 300 · Hotspot headline 50 | 1464 × 600 | 600 × 450 (per hotspot) | Hotspots 2–6 |
| Premium Navigation Carousel | Navigation text 25 · Subheadline 25 · Headline 25 · Body 100 | 1464 × 600 | 600 × 450 (per panel) | Panels 2–5 |
| Premium Regimen Carousel | Module headline 100 · Inset headline 20 · Inset body 100 · Navigation text 20 | 1464 × 600 | 600 × 450 (per panel) | Panels 2–5 |
| Premium Simple Image Carousel | Headline 50 · Body 200 | 1464 × 600 | 600 × 450 (per panel) | Panels 2–6 |
| Premium Video Image Carousel | Headline 80 · Panel headline 50 · Panel subheadline 80 · Panel body 500 · Video title 50 · Video description 200 | video 800 × 600; image 800 × 600 | none | `.mp4` only, ≤ 200 MB, ≤ 180 s. Panels 2–6 |
| Premium Q&A | Question 120 · Answer 250 | 1464 × 600 | none | Q&A 2–5 |
| Premium Technical Specifications | Headline 80 · Specification 30 · Definition 500 | — | — | Specifications 4–16 |

**Sources:** S410, S428, S426.
**URLs:** https://m.media-amazon.com/images/G/01/BX_Marketing/2023/AMZ_Guide_Premium_A_Module_05b.pdf ·
https://sell.amazon.com/blog/a-plus-content-design-guide ·
https://developer-docs.amazon/sp-api/lang-US/docs/a-plus-troubleshooting
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED (S410) / REPORTED (S426) ·
**`date_sensitive: yes`**
**Compliance-limit note:** the guide is stamped "Version 1.0, last updated May 30, 2023" and is
the only reachable per-module Premium spec. Premium A+ eligibility is granted by Amazon after
review and is not automatic (sellers report being denied despite meeting the stated criteria —
S433). Amazon markets Premium A+ as including "integrated 720p videos" (S428) while the module
guide specifies 960 × 540 minimum for the full-video module; treat the guide's numbers as the
asset spec and Amazon's marketing copy as aspirational.

---

## 6. Brand Story

**Source of truth:** Amazon's official *A+ Brand Story – Introduction* guide
(`Aplus_Brand_Story_Guide_EN_US_20210227.pdf`, S412) — an official Amazon PDF.

**Structure.** Brand Story renders as a horizontal carousel with a full-width background, in a
dedicated "From the brand" slot **above** existing A+ content on the detail page. Up to **19
content cards**.

**Module specs:**

| Card | Spec |
|---|---|
| Brand Carousel Background (**required, exactly one**) | Desktop image **1464 × 625 px** (required) · Mobile image **463 × 625 px** (required) · Accepted file types **.PNG & .JPEG** · Headline text **30 chars** · Description text **135 chars** |
| Brand Logo & Description | Logo image **315 × 145 px** (.PNG/.JPEG) · Descriptive text **450 chars** |
| Brand Questions | Total text **750 chars** (pre-loaded or custom questions) |
| Brand Focus Image | Image **362 × 453 px** (.PNG/.JPEG) · Overlay headline **30 chars** · Overlay text **135 chars** |
| Brand ASIN & Store Showcase | ASIN main images auto-added at **166 × 182 px** · Card title **30 chars** (optional) · "Shop All" links to the Amazon Brand Store via the `/stores/page/{pageId}` id |

**Layout constraint.** The background is 172 px taller than the cards so brand imagery at the top
is not covered by the scrolling cards.

**Best practices published by Amazon:** avoid embedding excessive/descriptive text in the
background image; avoid duplicating imagery shown in the background image; use different card
types to maintain customer interest; use the descriptive text fields to aid discoverability and
limit text embedded in images.

**Sources:** S412, S410, S411.
**URLs:** https://m.media.amazon.com/images/S/aplus-media-library-service-product-documents-media/AplusBrand/Aplus_Brand_Story_Guide_EN_US_20210227.pdf
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED · **`date_sensitive: yes`**
**Compliance-limit note:** the PDF is dated 2021-02-27 in its filename; Brand Story module
availability and specs may have moved. Amazon's SP-API A+ docs (S426, REPORTED) state Brand Story
modules must live in their own document with `contentType` set to BrandStory, and give a Brand
Story logo minimum of **362 × 453** — which is the *Brand Focus Image* size in the PDF, not the
Logo card's 315 × 145. That discrepancy is unresolved and flagged in "Requirement uncertainty".

---

## 7. Amazon Storefront assets

**Source of truth:** Amazon Ads *Stores creative guidelines* (S401).

**Page structure.** Every Store page has a built-in header section and needs at least one
additional content tile. Each page can have up to **20 sections**, with a maximum per page of:
**4 background video tiles, 1 product grid tile, 1 gallery tile, 1 featured deals tile,
1 recommended products tile**. Split sections contain multiple tiles arranged into layouts;
single-row split sections are variable in height.

**Header specs:**

| Element | Min. image size | Max. file size |
|---|---|---|
| Hero image | 3,000 × 600 px | 5 MB |
| Brand logo | 400 × 400 px | 5 MB |

**Safe zone.** Up to **30% of the hero image will be cropped — 15% from each of the left and
right sides**. All vital parts must stay inside the centre safe zone.

**Image tile specs (all max 5 MB):**

| Tile size | Min. image size (desktop) | Min. image size (custom mobile) |
|---|---|---|
| Full width | 1,500 × 20 px* | 1,680 × 20 px* |
| Large | 1,500 × 1,500 px | 1,680 × 20 px* |
| Medium | 1,500 × 750 px | 1,680 × 20 px* |
| Small | 750 × 750 px | 750 × 750 px |

\* For high-resolution display on all devices an image width of **3,000 px** is recommended. If a
title is added to the image tile, the image height must be **at least 32 px**.

**Link-title obstruction.** Adding a link title to an image tile covers part of the image:
about **19% of the height** for rectangle images (medium and full-width) and about **12% of the
height** for square images (small and large).

**Image-with-text tile specs:**

| Layout | Tile size | Min. image size |
|---|---|---|
| Text over image | Full width | 3,000 × 1,500 px |
| Text over image | Large | 1,500 × 1,500 px |
| Text over image | Medium | 1,500 × 750 px |
| Text over image | Small | 750 × 750 px |
| Text next to image | Full width | 1,500 × 1,500 px |
| Text next to image | Large | 1,500 × 1,500 px |
| Text next to image | Medium | 750 × 750 px |
| Text next to image | Small | 750 × 750 px |

**Shoppable image tile** (up to 6 products with interactive points): full width 1,500 × 750 px
(3,000 × 1,500 recommended), large 1,500 × 1,500, medium 1,500 × 750, small 750 × 750; all 5 MB.

**Video tile** (video file + cover image both required; plays inline on desktop, full screen on
mobile):

| Tile size | Min. cover image | Min. video resolution | Aspect ratio | File |
|---|---|---|---|---|
| Full width | 3,000 × 1,500 px | 1,280 × 640 px | 6:4 to 8:3 | MP4, H.264 |
| Large | 1,500 × 1,500 px | 640 × 640 px | 3:4 to 4:3 | MP4, H.264 |
| Medium | 1,500 × 750 px | 450 × 320 px | 6:4 to 8:3 | MP4, H.264 |

**Background video tile** (auto-plays muted on loop; video file only, no cover image):

| Tile size | Min. video resolution | Max. height | Video length | Aspect ratio |
|---|---|---|---|---|
| Full width | 1,280 × 640 px | 1,500 px | 2 to 20 seconds | 6:4 to 8:3 |
| Large | 1,280 × 640 px | 640 px | 2 to 20 seconds | 3:4 to 8:3 |
| Medium | 1,280 × 640 px | 320 px | 2 to 20 seconds | 6:4 to 8:3 |

**Gallery:** up to 8 images, min. image size 1,500 × 750 px.

**Product grid:** standard (square) or tall layout. ASINs added manually by keyword/ASIN search,
by entering a list of **up to 500 ASINs**, or automatically by keyword if the Store is associated
with the brand in the catalog. "Add to Cart" is not shown for products with multiple variations,
products allowing coupon clipping, out-of-stock products, or Apparel-categorised products (and is
hidden for all products in the tall grid).

**Best-seller / recommended-products tiles** each show 5 products automatically and require the
Store to be associated with the brand's products in the catalog.

**Text-in-image.** "Uploading images with embedded text is not encouraged" — not readable by
search engines or screen readers; use the "Image with text" tile instead (S401).

**Sources:** S401.
**URLs:** https://advertising.amazon.com/resources/ad-specs/en/stores ·
https://advertising.amazon.com/resources/ad-specs/stores
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED · **`date_sensitive: yes`**
**Compliance-limit note:** the *Stores guidelines and acceptance policies* page (the policy
counterpart to these creative specs) is client-rendered and unreachable (S422). Stores content
acceptance rules are therefore **UNKNOWN**. Stores eligibility requires an approved brand in
Brand Registry.

---

## 8. Sponsored Brands creative (including video)

**Sources:** S402 (Sponsored Brands video ad specs), S403 (Sponsored Brands & display ads
moderation guide), S404 (Asset-based / Brand Store creative specs), S409 (brand creative
guidance). All official Amazon Ads pages.

**Image quality.** All images must be at the highest image resolution possible **at 72 ppi**.
Images and text must be legible. Creative assets and imagery cannot obscure or interfere with the
legibility of ad templates. Low-quality images — crowded or cluttered, blurry, distorted,
pixelated, smudged or stretched — are rejected (S403).

**Ad formats / sizes.** Sponsored Brands formats listed by Amazon: **728 × 90, 800 × 90,
300 × 250, 160 × 600, 245 × 135, 900 × 45** (S403). Responsive component-based creatives support
**160 × 600, 245 × 250, 300 × 50, 300 × 600, 320 × 50, 414 × 125, 650 × 130, 728 × 90,
970 × 250, 980 × 55, 300 × 250, 336 × 280** (S404). Responsive size ranges: Wide (W/H > 1.5)
min 216 × 36; Rectangle (0.7 < W/H < 1.5) min 180 × 150; Tall (W/H < 0.7) min 120 × 240 (S404).

**Component character limits (Asset-based / Brand Store creative, S404):**

| Component | Limit |
|---|---|
| Headline | **50 characters** (25 JP) |
| Brand Name | 25 characters (15 JP) |
| Body Text | 100 characters (50 JP) |
| Disclaimer | 60 characters (28 JP) |
| Call to Action | dropdown of pre-approved CTAs |
| Logo | **400 × 400 px minimum, 1:1** |
| Image | 3 aspect ratios: Square 1:1, Tall 9:16, Wide 1.91:1 |

**Custom image sizes (S404):** Square 1:1 — recommended 1200 × 1200 px, min 600 × 600 px ·
Tall 9:16 — recommended 1000 × 1000 px, min 338 × 600 px · Wide 1.91:1 — recommended
1200 × 628 px, min 600 × 314 px. The in-form cropping tool requires the source image to be at
least 600 × 600 px and 5 MB or smaller. *(Note: Amazon's own labels for "Square" and "Tall" are
transposed relative to the ratios given — flagged in "Requirement uncertainty".)*

**Custom image prohibitions (S404, S403):** must not contain text, logos or CTAs; must not be on
a white or transparent background; must not be an individual brand logo or combination of logos;
must not be one of the selected product images; must not contain crowded, excessive, poorly
cropped or illegible elements; must not contain additional text other than text naturally present
in the image (e.g. on packaging); must not use letterbox or pillarbox; must not include pricing
and savings claims; must not contradict the landing page. If multiple identifiable products are
shown, the ad must accurately reflect the products on the landing page.

**Logo rules (S403):** must be the brand's **registered** logo (or one you have the legal right
to use); should fill the entire image or sit on a white or transparent background; must not be a
product, ASIN (including cropped versions), custom or lifestyle image or combination; must not be
used as an extension of the headline or contain additional text; must not be a combination of
logos; must not contain crowded or cluttered elements; must not appear on a complex graphical
background. Use Amazon's logo PSD template, which includes safe zones — content outside the safe
zone is cropped on some sizes.

**Copy rules (S403, S404):** sentence case is mandatory for self-service ad products — Title
Case, ALL CAPS, tOGGLE cAse and MIXED case are rejected. Special characters such as numerals,
`*`, `@` and periods in place of letters or to shorten words are not permitted (exceptions: part of
the brand/product/slogan, or accepted symbols like `$` and `#`). Proper punctuation required —
repeated question or exclamation marks, or more than two ellipses per headline, are rejected.
Ads must not contain superiority claims ("the best", "the most", "the biggest", "the tastiest",
"better than") unless substantiated; must not name competitors (generic "leading brand" phrasing
is allowed); must not use pressuring or urgency language ("Act now", "Last chance", "Don't miss
out"); must not use fake functionality; must not promote out-of-stock or recalled products;
pre-order products are permitted only with a "pre-order" CTA. Subscribe & Save references must
use the original, unadjusted Subscribe & Save logo and/or name.

**CTA rules:** non-specific CTAs such as "Click here" are prohibited. Onsite Billboard
(970 × 250): the CTA cannot be button-shaped. On mobile (all ads): CTA encouraged but not
required.

**Sponsored Brands video specs (S402):**

| Spec | Value |
|---|---|
| Duration | **6 to 45 seconds** (20 seconds or less highly recommended) |
| Dimensions | **1280 × 720, 1920 × 1080, or 3840 × 2160 px** |
| File size | **500 MB or less** |
| File format | **.MP4 or .MOV** |
| Aspect ratio | **16:9 (square pixel) only** |
| Video codec | H.264 or H.265 |
| Video profile | Main or Baseline |
| Frame rate | 23.976, 23.98, 24, 25, 29.97, 29.98, or 30 fps |
| Video bit rate | min 1 Mbps (4 Mbps or higher recommended) |
| Scan type | Progressive |
| Audio codec | PCM, AAC, or MP3 |
| Audio format | Stereo or mono |
| Audio bit rate | min 96 kbps |
| Audio sample rate | min 44.1 kHz |

**Video prohibitions (S402, S403):** no customer reviews or star ratings (even if these reviews
are on Amazon); no Amazon branding elements, trademarks, products or references to Amazon
products or services; no deals, discounts or other savings promotions; no flashing, spinning,
blinking or pulsating objects/text or high-contrast transitions; no pressuring, combative or
urgent language; no letterbox or pillarbox (black bars on any side); no text or important
information in the lower right corner (video safe area); no black or blank frames at the start or
end; no abruptly edited ending at maximum duration; no jumpy, jarring or overly fast-paced cuts;
no distracting, shrill, unexpected or violent sounds or sudden volume changes.

**Video craft guidance:** optimum length 15–30 seconds; show the product within the first two
seconds; mention key benefits within the first five seconds; end on the brand logo; on-screen
text should be a minimum of 50 pts (100 pts preferred) for 720p/1080p and 100 pts (200 pts
preferred) for 2160p; text and audio must be in the primary language of the site; use captions or
on-screen text because video autoplays without sound; if there is no soundtrack, make that clear
("No audio" disclaimer).

**Sources:** S402, S403, S404, S409.
**URLs:** https://advertising.amazon.com/resources/ad-specs/en/sponsored-brands-video ·
https://advertising.amazon.com/library/guides/sponsored-brands-sponsored-display-moderation ·
https://advertising.amazon.com/resources/ad-specs/component-based-creative ·
https://advertising.amazon.com/resources/ad-specs/how-to-build-brand-creatives-to-engage-amazon-shoppers
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED · **`date_sensitive: yes`**
**Compliance-limit note:** the canonical *Sponsored ads guidelines and acceptance policies* page
is unreachable (S421), so the full acceptance-policy text could not be checked. Submit ads at
least one week before launch to allow for moderation and resubmission (S403).

---

## 9. Sponsored Display creative

**Sources:** S400 (eCommerce display creatives — Responsive eCommerce Creative / REC specs),
S403 (moderation guide).

**General rules.** All images must be legible and at the highest resolution **of 72 ppi**. Text,
visuals and content must not interfere with the legibility of ad templates. All ads must be
**static** unless using the video format for display ads. Display ads dynamically incorporate CTA
elements by default, so additional call-to-action buttons or text are **not permitted** (S403).

**Display ad creative sizes (S403):** mobile web and mobile app — 300 × 250, 414 × 125,
320 × 50. Desktop — 320 × 50, 300 × 250, 160 × 600, 300 × 600, 650 × 130, 728 × 90, 970 × 250,
980 × 55.

**Responsive eCommerce Creative (REC).** Up to **20 ASINs** per creative (rotates products,
skips out-of-stock items automatically). Formats: static images — **JPEG, PNG**; video — online
video, **MP4, 16:9 aspect ratio, max 500 MB** (video currently US-only, third-party publisher
sites).

**REC component specs (S400):**

| Component | Spec |
|---|---|
| Brand logo | **600 px min. width · 100 px min. height · 1,000 kb max file weight · JPG, GIF or PNG** |
| Headline | **max 50 characters** |
| Disclaimer | **max 60 characters** |

**Headline guidelines (S400):** start with a capital letter (except certain brand names); no
multiple punctuation marks or special characters in a row; **pricing and savings claims must not
be present in the headline**; no forceful phrases or exclamation points; **no unsupported claims
— Amazon names "best", "top selling" and "healthiest" as examples that will not be approved**;
no Subscribe & Save messaging. Disclaimer field is only for products that require disclaimers.

**Custom images for responsive sizing (S400):** three images — square 1200 × 1200 px (1:1),
tall 900 × 1600 px (9:16), wide 1200 × 628 px (1.91:1). The in-form cropping tool requires a
source of at least 600 × 600 px and 5 MB or smaller.

**Size-specific custom image table (S400)** — ad slot → custom image dimensions, max file weight,
format, and type-size rules:

| Ad slot | Custom image dimensions | Max file weight | Format | Headline & body text | Disclaimer text |
|---|---|---|---|---|---|
| 300 × 250 & 336 × 280 | 900 × 480 px | 100 kb | HTML, JPG, GIF, PNG | 36–78 pts at 72 dpi | 27–36 pts Arial regular (or equivalent) at 72 dpi; ≤ 2 lines |
| 160 × 600 & 300 × 600 | 600 × 1020 px | 100 kb | HTML, JPG, GIF, PNG | 24–52 pts at 72 dpi | 24 pts Arial regular (or equivalent); ≤ 4 lines |
| 728 × 90 | 1140 × 180 px | 60 kb | HTML, JPG, GIF, PNG | 36–52 pts at 72 dpi | 28 pts Arial regular (or equivalent); ≤ 1 line |
| 300 × 50, 320 × 50, 414 × 125 | 570 × 375 px | 60 kb | HTML, JPG, GIF, PNG | 42–78 pts | 42–78 pts Arial regular (or equivalent); ≤ 2 lines |
| 980 × 55 | 110 × 55 px | 150 kb | HTML, JPG, GIF, PNG | — | — |
| 970 × 250 | 952 × 500 px | 150 kb | HTML, JPG, GIF, PNG | 36–78 pts at 72 dpi | 27–36 pts Arial regular (or equivalent) at 72 dpi; ≤ 2 lines |

**Text rules inside the custom image (S400):** total words may not exceed **10 words**
(40 characters in JP; disclaimer copy and logo text do not count); no more than **2 type
variations** (font size, colour, style; 3 excluding disclaimer in JP; logo type excluded); no
more than **2 logos** (legally required marks such as ESRB ratings do not count); disclaimer text
and copy inside the custom image must be sentence case; CTA buttons or text are not allowed —
REC supplies its own CTA buttons.

**Custom image prohibitions (S400):** must not contradict the landing page; must not be on a
white or transparent background; must not be an individual brand logo or combination of logos;
must not contain crowded, excessive, poorly cropped or illegible elements; must not contain
additional text other than text naturally present in the image (e.g. on packaging); must not
contain letterbox or pillarbox; must not contain pricing and savings claims. Composition rules:
no cut-off heads/limbs, no missing context, no awkward framing, no off-centre focus, no partially
cropped objects; backgrounds must be simple and uncluttered; high-resolution only.

**Sponsored Display video format specs (S403):** max file size 500 MB; aspect ratio 16:9;
duration 6–45 s; dimensions 1920 × 1080 or higher; min video bit rate 4 mbps; frame rate 23.976
(recommended), 24, 25 or 29.97; min audio bit rate 192 kbps; audio sample rate 44.1 kHz or
48 kHz; video H.264, MPEG-2 or MPEG-4; audio PCM or AAC; stereo or mono.

**Sources:** S400, S403.
**URLs:** https://advertising.amazon.com/resources/ad-specs/en/ecommerce ·
https://advertising.amazon.com/library/guides/sponsored-brands-sponsored-display-moderation
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED · **`date_sensitive: yes`**
**Compliance-limit note:** the dedicated *Sponsored Display policies* page is unreachable (S424).
Amazon notes it "may test variations of REC elements, copy, layout, and design", so live ads may
differ from the examples on the spec page.

---

## 10. Sponsored Products creative

**Rule.** Sponsored Products ads are built from the product detail page — the primary product
image and associated product information from the detail page are used automatically. There is
**no separate Sponsored Products creative-upload spec published in Amazon's ad-specs library**.

**Confirmed constraints that do apply (S403):**

- ASIN images showcased in ads must comply with Amazon's policies **and the Amazon Site
  Standards for Product Images**.
- GIFs or animations are not permitted.
- Duplicate or identical product images within the same ad are not permitted.
- ASIN images within the ad must be, or refer to, the product being sold.
- Images must clearly show all the product variations, such as colour, model or style.
- Low-quality images (crowded/cluttered, blurry, distorted, pixelated, smudged, stretched) are
  rejected; images must be at the highest resolution possible at 72 ppi.

**Practical consequence for a design studio:** for Sponsored Products, compliance is inherited
from the listing image (§1 and §2), not from an ad-specific spec. The Design Studio's main-image
and secondary-image output is therefore the whole of the Sponsored Products compliance surface.

**Sources:** S402, S403, S417, S418, S419.
**URLs:** https://advertising.amazon.com/resources/ad-specs/en/sponsored-brands-video ·
https://advertising.amazon.com/library/guides/sponsored-brands-sponsored-display-moderation ·
https://advertising.amazon.com/library/guides/getting-started-with-sponsored-ads ·
https://advertising.amazon.com/products/sponsored-ads
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED · **`date_sensitive: yes`**
**Compliance-limit note:** **UNKNOWN** — no Amazon-published pixel/format/file-size spec for
Sponsored Products creative specifically. Do not invent one. Amazon does publish generative-AI
image features for Sponsored Display and Sponsored Brands ("what's new" entries in its sitemap),
which reinforces that the listing image is the SP creative.

---

## 11. Prohibited content and prohibited claims

**Sources:** S403 (moderation guide — the most detailed reachable source), S405 (ad policies
quick reference), S406 (technical guidelines), S407 (general policies), S408 (brand usage).

**General requirements (S403).** Ads must: be suitable for a general audience; be honest about
the products or services; avoid content that may mislead or offend customers; accurately reflect
the content of the product detail page so what customers see is correct before clicking an ad or
deciding to purchase; be in the primary language of the Amazon site where the ad appears; be
clear and easily understandable to a wide audience; only promote products you own or are
authorised to resell or distribute.

**Claims and substantiation (S403).** Ads must be truthful and accurate. **Advertising claims
have to be the same ones as on the product detail page.** Claims on the detail page, in the
headline and/or on the product packaging will also require proof and substantiation. Superiority
claims (the best, the most, the biggest, the tastiest, better than) will be rejected unless they
can be substantiated. Ads should accurately reflect the landing page and must contain the same
exact offers and products.

**Unsupported-claim examples named by Amazon (S400):** "best", "top selling", "healthiest" are
unsubstantiated and will not be approved in REC headlines.

**Prohibited copy behaviours (S403):**
- **Special characters** — numerals, `*`, `@`, periods in place of letters or to shorten words
  (e.g. "H8", "B.E.S.T.", "w/out"), except where part of the brand/product/slogan or in accepted
  use (`$`, `#`, `AC/DC`, `AM/PM`).
- **Capitalisation** — sentence case only for self-service ad products; Title Case, ALL CAPS,
  tOGGLE cAse and MIXED case are rejected.
- **Punctuation** — repeated question or exclamation marks; more than two ellipses per headline;
  any end punctuation in calls to action ("Shop now!").
- **Pressure** — language creating urgency ("Hurry while supplies last!", "Don't miss out!!!!",
  "Are you ready????"); any combination of two or more of ALL CAPS, punctuation marks and/or large
  font sizes ("UNMISSABLE SUMMER DEALS!").
- **Competitive language** — competitors may not be explicitly called out by name; references to
  a "leading brand" or other generic phrasing are permitted.
- **Misleading content** — fake functionality (elements that look clickable but are not);
  mismatches between ad and landing page.
- **Personal language** — avoid "you"/"your" (Amazon's example: "Use our supplement to solve your
  weight issues").
- **Region/group callouts** — do not mention a specific region or group.
- **Distracting features** — flashing, blinking or pulsating objects/images/text; excessive
  animation (frame changes every 1–2 seconds, or objects moving constantly); animation mimicking
  user interaction.
- **Unavailable items** — ads must not promote out-of-stock or recalled products or unavailable
  services; pre-order only with a "pre-order" CTA.

**Price / promotion claims (S403).** Superlatives like "Huge savings" or "Gigantic discounts" are
not permitted, nor are mentions of specific pricing such as "Save 50%" or "$20 off". Permitted
messaging includes "[Product] savings", "Savings on [Product]", "Save now", "Great prices on
[Product]", "Great savings on [Product]", "Great bundles on [Products]", "Buy [Product] and get
[additional Product free]". The words "Deal" or "Deals" may only be used if the products have an
Amazon deal (Deal of the Day, Best Deal, Lightning Deal, coupon) live for the duration of the
campaign. Promotional copy in an ad must also be on the product detail page and valid for the
length of the campaign; campaigns must end on or before the last day of the promotion, and
promotional messaging must be removed if the campaign is extended. Holiday campaigns must start a
reasonable time before the event and end within 24 hours after it.

**Pricing consistency (S405).** Pricing and savings claims must be the same on the ad and the
landing page.

**Prohibited / restricted categories (S405):**

| Category | Status |
|---|---|
| Alcohol (as a product) | Prohibited in US, India, UAE and China; other locations permitted within guidelines |
| Charity / donation request | Permitted with copy and placement restrictions |
| Movie trailer | Permitted with placement restrictions based on rating |
| Pharmaceuticals, health and beauty products | Restricted — refer to full guidelines |
| Scary content | Permitted in some cases; cannot be excessive or gory; may face placement restrictions |
| Violence or weapons (as content) | Permitted only in certain contextually relevant cases and placements |
| Controversial social or political content | **Prohibited** |
| Foul, vulgar or obscene language | **Prohibited** |
| Hangover cures | **Prohibited** |
| Weapons (as a product) | **Prohibited** |

**Review / rating usage (S403).** Videos cannot include customer reviews, including star ratings,
**even if these reviews are on Amazon**. Amazon-generated elements (reviews, ratings, Prime badge,
pricing, deal badges) may be surfaced by Amazon's own systems but must not be reproduced by the
advertiser in creative.

**Amazon brand usage (S408).**
- The Amazon and Smile logos are **not permitted** in third-party advertising by vendors and
  sellers linking to Amazon. The **"available at Amazon"** logo is permitted, in white or
  "squid ink", with no review or approval needed.
- "Available at Amazon" minimum sizes: stacked lockup no smaller than 0.75 in wide for print,
  90 px at 1× screens, 180 px at 2×; horizontal lockup no smaller than 1.4 in print, 140 px at 1×,
  280 px at 2×. Do not alter artwork, proportion or colour.
- Amazon branded **buttons** are not allowed except in eCommerce ads ("Add to Cart", "Add to Wish
  List", "Shop now", "Clip coupon").
- Amazon must always be in title case — all capitals or lowercase is not allowed.
- Use of Amazon proprietary words/phrases tied to Amazon functionality (Gold Box, Deal of the
  Day, Super Saver Shipping, 1-Click, Seller Central, Wish List, Today's Deals, Subscribe & Save,
  Kindle, Amazon Mom, Look Inside the Book) requires Amazon approval.
- All imagery must be owned by the advertiser or cleared for use; Amazon.com product imagery must
  be approved by Amazon; imagery must not be downloaded from search engines.
- Ads must not look like, mimic, or be mistaken for Amazon content.

**Background / border rules (S403, S405).** Ads without borders cannot have a white or off-white
background colour; they must contrast with the white/off-white page background (e.g. light grey).
Alternatively the ad's background must contrast with a white background or contain a **1-pixel
non-white border**. Onsite animations must not exceed 15 seconds.

**Enforcement / discretion (S403).** Amazon reserves the right to reject, remove or request
modifications to an ad at its sole discretion, for any reason, and may suspend or terminate ad
accounts for severe or repeated Ad Policy violations. Amazon periodically updates its policies;
advertisers are told to check the Ad Policy Change Log regularly. Submit ads at least one week in
advance of launch.

**Sources:** S400, S403, S405, S406, S407, S408.
**URLs:** https://advertising.amazon.com/library/guides/sponsored-brands-sponsored-display-moderation ·
https://advertising.amazon.com/resources/ad-policy/quick-reference ·
https://advertising.amazon.com/resources/ad-policy/technical-guidelines ·
https://advertising.amazon.com/resources/ad-policy/general-policies ·
https://advertising.amazon.com/resources/ad-policy/brand-usage ·
https://advertising.amazon.com/resources/ad-specs/en/ecommerce
**Accessed:** 2026-10-09 (UTC) · **Label:** VERIFIED · **`date_sensitive: yes`**
**Compliance-limit note:** the full *Amazon Ads Guidelines and Acceptance Policies* (CAP) and the
*Sponsored ads guidelines and acceptance policies* are the authoritative documents and both are
client-rendered and unreachable (S421, S423). Amazon's own moderation guide states its content
list "does not contain our full ad policies". Health/supplement claim rules specifically were
**not** retrieved from Amazon — only the generic restricted-category pointer in S405.

---

## Which competitors produce compliant output

Verdicts follow the operator's rule: **VERIFIED only where an Amazon-specific spec, template or
export preset was directly observed in the competitor's product or docs. Otherwise UNKNOWN.**
"Does not demonstrably meet the Amazon rules" is the blunt answer for almost every general tool.

| Competitor | Amazon-specific spec / template / preset observed? | Verdict | What was actually observed (source) |
|---|---|---|---|
| **Canva** | **Yes — partial** | **VERIFIED (template exists; compliance NOT enforced)** | Canva publishes an "Amazon product image templates" page stating its preset layouts "default to the basic Amazon product image size — a 1080 × 1080 square photo" (S484, REPORTED: the page returned HTTP 403 and a browser-support interstitial, so the text came from a search index). That is a genuine Amazon-named template category with a stated pixel size. It is a *canvas size*, not a compliance preset: nothing observed enforces the pure-white background, the 85% fill, the no-text rule, the 500–10,000 px range, or format constraints. 1080 × 1080 also sits below the practical 1600/2000 px recommendation that most Amazon guidance and Amazon's own zoom preference imply. |
| **Figma** | **No** | **UNKNOWN** | No Amazon-specific spec, template or export preset on Figma's product surface or in its public community search results (S497). Amazon listing templates exist in the community as user-made files, which is not a product feature. Figma has no notion of Amazon image compliance. |
| **Adobe Firefly** | **No** | **UNKNOWN** | The product page returned HTTP 403 to every fetch attempt (S498). No Amazon-specific spec observed. Firefly is marketed on commercial safety and creative control, not on marketplace listing specs. |
| **PiccoPilot** | **No (REPORTED compliance claim)** | **UNKNOWN** | Homepage markets "100% Compliant" as one of three levers ("Optimized Templates + Low Cost + 100% Compliant = More Free Traffic") and lists Amazon among export destinations (S488). The templates page and the AI Templates tool page contain no Amazon reference or dimension specification (S488). The compliance claim is vendor marketing (REPORTED), unverified. Note: a **PicCopilot Service Closure Notice** is displayed on the site. |
| **Packify.ai (Pacdora)** | **No** | **UNKNOWN** | Both packify.ai (S493) and pacdora.com (S494) homepages contain no Amazon reference. Packify is positioned as an AI packaging-design agent (text → 3D packaging concepts, print-ready dielines, AI photoshoots). Its output is packaging artwork and dielines, not Amazon listing creative. Nothing observed maps to Amazon main-image, secondary-image or A+ specs. |
| **Creatify** | **No** | **UNKNOWN** | Homepage says "Works with Meta, TikTok, Youtube, Snap, Amazon and more" and "Auto-optimized for each platform's specs" (S489). That is a marketing claim about social/ad platforms; no Amazon creative spec, dimension or rule set was observed on the homepage or the ecommerce use-case page (S490). |
| **Photoroom** | **Partial (REPORTED)** | **UNKNOWN** | Homepage advertises "Instant Resize — one image, every format. Resize for Instagram, **Amazon**, Shopify, and more" plus "Sell on Amazon, eBay & more" as an industry vertical (S485). The dedicated resize/feature pages returned 404 or connection errors, so the actual Amazon preset dimensions were **not observed**. No Amazon compliance rule enforcement observed. |
| **Pebblely** | **No** | **UNKNOWN — and documented absence** | Pebblely's own "How does it work?" page lists its complete image-size preset set: **Square (1:1) for Instagram and Shopify, Portrait (4:5) for Instagram feed, Story (9:16) for Instagram and TikTok, Landscape (16:9) for website banners, and Facebook Ad (16:9) for social campaigns.** There is **no Amazon preset at all** (S486). Pricing tiers (S487: Lite US$9/30 images, Basic US$19/200, Pro US$39/500) mention background themes and credits, not Amazon specs. This is a documented, blunt gap: the tool's output geometry is social-first. |
| **Flair** | **No** | **UNKNOWN** | Amazon appears only as a customer logo on the homepage (S491). Feature pages (drag-and-drop canvas, AI Marketing & Ads, on-model photography, human builder) contain no Amazon spec (S492). Flair's own comparison table positions it against Pebblely/Botika/Claid, not against Amazon requirements. |
| **Helium 10** | **N/A — not a creative tool** | **UNKNOWN (no creative output to assess)** | Helium 10 is an Amazon/Walmart/TikTok Shop *seller-operations* suite: Keyword Tracker, Listing Analyzer, Listing Builder, Product Listing Converter, Profits, Follow-Up, Ads, Influencer Finder (S495, S496). Nothing in its tools list is an image/design generator or an Amazon creative-compliance checker. It is Amazon-native in domain, not in creative output. |

### Blunt summary of compliance gaps

1. **None of the ten tools was observed to enforce Amazon's main-image rules.** Not one enforces
   the pure-white background, the 85% frame fill, the "no text/logos/borders/watermarks" rule, or
   the 500–10,000 px longest-side range. That is a real, recorded gap — the single most common
   cause of listing suppression (see `SELLER_PAIN_POINTS.md`, themes 5 and 6) is exactly the rule
   these tools do not check.
2. **Only Canva has a genuinely Amazon-named template with a stated pixel size** (1080 × 1080),
   and that size is a canvas default, not a compliance target.
3. **Pebblely's documented preset list contains no Amazon geometry at all** — Square for
   Instagram/Shopify, 4:5, 9:16, 16:9, Facebook Ad. Any Amazon output is incidental.
4. **No tool was observed to enforce A+ Content module specs.** The per-module pixel minimums
   (970 × 300, 1464 × 600, 600 × 450, 300 × 300, 135 × 135, 488 × 700, 800 × 600…) and character
   limits are a dense, high-value constraint set that no tool in this set was seen to encode.
5. **No tool was observed to enforce Sponsored Brands / Sponsored Display creative rules** —
   the 50-character headline, the 400 × 400 logo minimum, the 1:1 / 9:16 / 1.91:1 custom-image
   triplet, the 10-word in-image text cap, the 2-type-variation and 2-logo limits, or the
   sentence-case and prohibited-claim rules.
6. **Packify/Pacdora and Helium 10 are out of scope for creative compliance** — one produces
   packaging artwork, the other produces listing copy and keyword data.
7. **Photoroom's "Instant Resize for Amazon" is REPORTED, not verified** — the feature page could
   not be reached, so the actual preset is unconfirmed.

---

## Requirement uncertainty

Things that could **not** be confirmed from an official Amazon property during this research:

1. **The canonical Seller Central "Product image requirements", "main image requirements" and
   "requirements for all product images" help pages** — JS-gated SPA, `UNKNOWN (fetch failed)`
   (S420). Every listing-image rule in §1–§3 therefore rests on Amazon's own summary of that page
   posted on Amazon Seller Forums (S415, S416).
2. **Whether text and graphics are permitted on *secondary* listing images.** Amazon's own pages
   conflict (a requirements page saying "No text or pricing details (Swatch only)" vs a Quick
   Start Style Guide warning about borders/watermarks/text). Unresolved (S415).
3. **The Amazon Site Standards for Product Images** — referenced by Amazon's own moderation guide
   (S403) as the governing standard for ASIN images in ads, but no reachable Amazon URL found.
4. **The full Amazon Ads Guidelines and Acceptance Policies (CAP), the Sponsored ads guidelines
   and acceptance policies, the Stores guidelines and acceptance policies, and the Sponsored
   Display policies** — all client-rendered and unreachable (S421, S422, S423, S424). These are the authoritative claim/policy documents; the prohibited-claims section
   in §11 is built from the reachable moderation guide and quick-reference instead.
5. **Character limits for Basic A+ Content modules** — not published in Amazon's standard-modules
   asset sheet (S413) or in the reachable guides; only a handful of figures are reachable
   (6,000-char Product Description, 16-row Technical Specifications, and the SP-API
   `StandardSingleImageHighlightsModule` limits).
6. **The "Four Image Highlights" second-image dimension** — Amazon's own template sheet lists it
   as an unfilled placeholder (`X00xX00`). Do not invent a value.
7. **Brand Story Logo card vs Focus Image size discrepancy** — the official PDF gives the Logo
   card as 315 × 145 px and the Focus Image as 362 × 453 px, while Amazon's SP-API docs (S426,
   REPORTED) cite a "Brand Story logo" minimum of 362 × 453. Unresolved.
8. **Premium A+ eligibility criteria** — Amazon states eligibility is granted after review;
   sellers report denial despite meeting published criteria (S433). The current, exact
   eligibility list is not published on a reachable page.
9. **Category-specific image rules** (apparel mannequin/flat-lay, grocery, health/beauty, etc.)
   — not retrieved. Amazon's own materials repeatedly note that "Amazon category rules can be
   stricter".
10. **Whether Amazon's AI-generated listing images (which sellers report being added
    automatically) carry a synthetic-content disclosure requirement.** Sellers on r/AmazonFBA
    report a requirement to tag photorealistic AI-generated people with
    `contains-synthetic-performer` in the XMP `dc:subject` field before upload, attributed to a
    synthetic-performer law. **No official Amazon page confirming this was reachable** — treat as
    UNKNOWN and verify before building any feature that emits AI people.
11. **Sponsored Products creative spec** — no Amazon-published pixel/format/file-size spec
    exists in the reachable ad-specs library; SP inherits listing-image rules (§10).
12. **Non-US marketplace variations** — every brand-new number here is from the US/en-US
    surface. Amazon publishes locale-specific ad-spec pages and its policies vary by country
    (e.g. alcohol advertising); none of that was checked.

**Recommended re-verification cadence:** before any Design Studio release that ships Amazon
presets or compliance checks, re-fetch §1–§11 sources and diff. Amazon states it periodically
updates policies, and the Seller Forums show image requirements being rewritten within the last
two years.

