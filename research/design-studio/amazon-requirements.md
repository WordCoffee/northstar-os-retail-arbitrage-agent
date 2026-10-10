# Amazon Creative Requirements and Ranking Influence

Track B of the Design Studio research corpus. Every claim carries a tag:
`[documented]` = Amazon-owned source, `[observed]` = seen directly in product/demo/video,
`[inferred]` = derived reasoning or vendor-reported, not confirmed by Amazon.

Pulled at: 2026-10-10. Sources stored in `sources.db` (see `sources.md`).
Northstar OS relevance: every spec below is what the Design Studio must enforce
BEFORE an asset is allowed to be exported or uploaded.

---

## 1. Current image and content specifications (Seller Central / Ads docs only)

### 1.1 Main image (search-result slot)

| Rule | Value | Tag |
|---|---|---|
| Background | Pure white, RGB 255,255,255 | [documented] |
| Frame fill | Product fills 85-100% of frame on longest side | [documented] |
| Minimum size | 1,000 px on longest side for zoom; under 500 px auto-rejected | [documented] |
| Optimal size | 1,600+ px; sellers commonly upload 2,000x2,000 or 5,000x5,000 | [documented] |
| Formats | JPEG preferred; PNG, TIFF, GIF accepted | [documented] |
| Resolution | At least 72 dpi | [documented] |
| Color space | sRGB for main image; A+ requires RGB (CMYK unsupported) | [documented] |
| File size | Under 10 MB | [inferred] (widely stated, not in the help page text captured) |
| Prohibited | Text, logos, borders, colour blocks, watermarks, graphics over product or in background; multiple images of the same product; props | [documented] |
| Shadows | Minimal shadow allowed (needed when product is white) | [documented] |
| Lifestyle main image | Allowed ONLY for BED, BED_FRAME, MATTRESS, RUG, RUG_PAD, SOFA | [documented] |
| Photograph vs render | Seller Labs claims drawings/illustrations/rendered mockups are not acceptable as a main image | [inferred] - strong vendor claim, verify per category |
| Category precedence | Per-category style guides OVERRIDE the general rules on conflict | [documented] |

Critical consequence: Amazon SUPPRESSES A LISTING FROM SEARCH AND BROWSE until you
provide a main product image that meets all category-specific image requirements
[documented]. A non-compliant main image is not a cosmetic issue - it removes the
product from search entirely.

Additional images: 1 main + 5 to 8 additional images depending on category
[documented via third-party Linnworks mapping of flat-file columns; the flat file
schema itself exposes `main_image_url` + `other_image_url1..8` + `swatch_image_url`].

### 1.2 A+ Content modules (Basic)

| Module | Image size | Tag |
|---|---|---|
| Single Image & Sidebar | 300x400 main + 350x175 sidebar | [documented] |
| Single Left / Single Right Image | 300x300 | [documented] |
| Four Images & Text | 200x200 each | [documented] |
| Image & Dark / Light Text Overlay | 970x300 | [documented] |
| Comparison Chart | 150x300 | [documented] |
| Basic A+ overall | 970x300, 5 modules max | [documented] |

Image requirements for all A+ modules: .jpg / .bmp / .png, RGB only (CMYK not
supported), individual files under 2 MB, at least 72 dpi, animated GIF prohibited
[documented]. Images and text must be UNIQUE to A+ - reuse of gallery images is
rejected [documented]. Maximum one brand logo; only navigation icons beyond that
[documented].

Alt text ("image keywords") is REQUIRED for every module containing an image and
must genuinely describe the image for screen-reader users, or the content is rejected
[documented].

### 1.3 Premium A+ Content

| Module type | Notes | Tag |
|---|---|---|
| Premium Full Image / Text / Images & Text / Videos | Documented module set | [documented] |
| Premium Comparison Tables | Documented | [documented] |
| Premium Hotspots | Interactive hotspots to hone in on product features | [documented] |
| Premium Carousels | Clickable image or video carousel | [documented] |
| Premium Q&A | Documented | [documented] |
| Premium Technical Specifications | Documented | [documented] |
| Brand Highlight | Documented | [documented] |

Premium A+ image size 1464x600, 7 modules [documented]. Same file rules as Basic
[documented]. Oversized images are resized DOWN to module max but never upscaled -
so an undersized asset stays undersized [documented].

GATING: Premium A+ eligibility requires a Brand Story module published on ALL
brand-owned product listings plus additional approved content (forum thread text
truncated) [observed in Seller Central forum].

### 1.4 Brand Story

Appears in a dedicated "From the brand" section, ABOVE A+ Content when both are
present [observed]. Renders as a carousel with a full-screen background on desktop
and mobile, image-and-text cards, and links to other products and the Amazon Brand
Store [documented]. Applied across all ASINs in the brand [documented].

### 1.5 Storefront (Amazon Store)

Tiles have 4 sizes: Full Width (4:2), Large (2:2), Medium (2:1), Small (1:1)
[documented].

| Element | Spec | Tag |
|---|---|---|
| Hero image | 3,000x600 min to 3,000x1200 max, 5 MB | [documented] |
| Brand logo | 400x400 min, 5 MB | [documented] |
| Image tile - Full Width | 3,000x1,500 | [documented] |
| Image tile - Large | 1,500x1,500 | [documented] |
| Image tile - Medium | 1,500x750 | [documented] |
| Image tile - Small | 750x750 | [documented] |
| Embedded text height | 32 px on full width, 16 px on other sizes | [documented] |
| Video tile - Full Width | cover 3,000x1,500, video 1,280x640 min, aspect 6:4-8:3 | [documented] |
| Video tile - Large | cover 1,500x1,500, video 640x640 min, aspect 3:4-4:3 | [documented] |
| Background video | 1,280x640 min, 2-20 seconds, MP4 H.264 | [documented] |
| Product Grid | 2 initial rows, max 100 products | [documented] |
| Gallery | up to 8 images, min 1,500x750 | [documented] |
| Best Seller tile | 5 products, appears automatically only if criteria met | [documented] |

Safe zones: below 1,500 px width, up to 16% of the hero image left and right is
cropped, and the brand logo covers an additional 18% of the left side [documented].
Any logo or text in the hero must sit inside the required centre safe zone
[documented].

IMPORTANT ACCESSIBILITY/SIGNAL NOTE: Amazon explicitly does NOT encourage text
embedded in Store images because it is unreadable by external search engines and
screen readers - use the "Image with text" tile instead [documented]. Image tiles
with link titles obscure roughly 19% (rectangle) or 12% (square) of the image at
the bottom [documented].

### 1.6 Ads creative

Sponsored Brands video [documented]:
- Duration 6-45 s (20 s or less highly recommended)
- Dimensions 1280x720 / 1920x1080 / 3840x2160
- File size 500 MB max; format MP4 or MOV; 16:9 square pixel ONLY
- Codec H.264 or H.265, profile Main or Baseline
- Frame rate 23.976 / 23.98 / 24 / 25 / 29.97 / 29.98 / 30
- Video bit rate min 1 Mbps (4 Mbps+ recommended), progressive scan
- Audio PCM/AAC/MP3, stereo or mono, min 96 kbps, min 44.1 kHz

Sponsored Brands video - VERTICAL (Ads API) [documented]:
- Aspect 9:16; 720x1280 / 1080x1920 / 2160x3840; duration 6-45 s
- Brand logo image 400x400 or larger, 1 MB max, PNG or JPG, must fill the image
  or have a white/transparent background
- Headline max 50 characters (30 in Japan)
- Drive Page Visits goal: 1-3 advertised products. Grow Brand Impression Share: 0-3

Amazon DSP display sizes [documented]: the authoritative list includes 300x250,
320x50, 728x90, 160x600, 120x600, 300x600, 468x60, 400x39, 300x31, 980x55, 900x45,
970x250, 800x250, 480x200, 1800x1000, 630x90, 1500x260, 480x400, 1500x600, 336x280,
250x250, 200x200, 120x60, 250x360, 300x300, 300x1050, 300x480, 320x320, 580x400,
640x320, 640x1136, 640x360, 750x100, 750x1334, 750x200, 750x300, 930x180, 970x90,
980x120, 980x90, plus Image Mobile O&O 2560x2560 requiring 2x resolution
(a 300x250 placement needs a 600x500 upload).

Amazon Pro display banners [documented]: 300x250 / 728x90 / 160x600 / 300x600 /
970x250 at 200 KB, 320x50 at 50 KB, 414x125 at 100 KB, JPG or PNG-8. 320x50 must be
designed at 2X (640x100) and 414x125 at 2X (828x250). Font no smaller than 16 pt at
2X. GIF animation permitted but only up to 3 loops within 15 s on O&O.

Custom images (asset-based ads) [documented]: 1200x628 wide, 1200x1200 square,
900x1600 tall (9:16); floor 600x600; 5 MB cap, JPEG or PNG. Logo must be 1:1 and at
least 400x400. Headline 50 chars, brand name 25, DSP body text 100, disclaimer 60
[vendor synthesis of Amazon specs].

The white-background rule INVERTS between assets: a brand LOGO must fill the entire
image or sit on a solid colour background; a custom IMAGE must NOT be an individual
or multiple product image on a solid or transparent background [documented].

Policy rules that bite ad creative [documented]:
- Brand name or logo identifiable for at least 3 seconds in video
- CTA fewer than 30 characters (15 Japan), no punctuation
- No personalised language; ASCII art and emojis prohibited unless part of the logo
- Third-party watermarks prohibited
- Ad copy Arial 12-25 pt desktop; logo at 72 ppi
- Videos without sound permitted only if understandable and carry a "no audio" disclaimer

### 1.7 Bulk and variation workflows

- Bulk listing-quality fixes: Manage all inventory > Optimize listings > Improve
  Listing Quality in bulk > Generate report > upload values file > Review upload
  status (batch ID + processing report). Last 25 uploads retained [documented].
- Flat files: per-category Excel/TSV template; feed_product_type wrong value causes
  silent rejection of the entire row; parent_sku / parent_child / relationship_type /
  variation_theme wire the variation family [inferred from vendor guide].
- DESTRUCTIVE DEFAULT: the default feed mode is `Update`, where every EMPTY cell is
  interpreted as "blank this field". `PartialUpdate` ignores blank cells. A
  flat file that updates price but leaves bullets blank wipes the bullets
  [inferred from vendor guide]. This is the single most expensive flat-file mistake.
- Image columns: `main_image_url`, `other_image_url1..8`, `swatch_image_url`
  [documented in template schema]. Variation main images use variation-specific
  image properties in third-party tooling; each child ASIN needs its own compliant
  main image [observed].
- A+ Content: bulk upload REQUIRED above 1,000 ASINs [documented].
- Reverse file can be requested for existing products to seed a flat file
  [observed in seller forum].

---

## 2. Main-image compliance and common suppression triggers

SUPPRESSION IS DOCUMENTED: "We will suppress a listing from search and browse until
you provide a main product image that meets all our category-specific Image
Requirements" [documented].

Image-related suppression triggers [documented unless noted]:
1. Non-white background (including grey/cream colour cast) [documented]
2. Product not filling 85% of frame [documented]
3. Text, logos, watermarks, borders, colour blocks, promo text, badges [documented]
4. Multiple products / multiple views in the main image [documented]
5. Low resolution (under 1,000 px longest side; under 500 px rejected) [documented]
6. Product still in packaging (unless consumable or collectible) [documented]

Non-image suppression triggers that still matter to a creative pipeline
[documented / observed]:
- Missing required category attributes (size, colour, material, description)
- Wrong category or product type
- Prohibited keywords, duplicate ASINs
- Compliance/safety requirements (hazmat needs an appeal)

Two distinct states must be modelled separately [inferred]: SEARCH suppression
(invisible in search, cannot sell) vs BUY BOX suppression (visible but unbuyable).
The remediation path and urgency differ.

Fix flow [documented]: Inventory > Manage All Inventory > Fix Blocked Listings >
Listing Quality tab states the reason and offers an Edit action. Reactivation can
take up to 24 hours while Amazon re-crawls.

VARIATION TRAP [observed]: fixing the parent and leaving child ASINs with
non-compliant main images leaves those children suppressed and invisible in search.

---

## 3. What Amazon says vs what credible tests show about creative and ranking

SEPARATED DELIBERATELY, because this is where the industry is least honest.

### 3.1 Documented by Amazon

- "The presence of a quality image is an important element that helps a customer
  choose one search result over another" and "Images help them to visually evaluate
  and compare key features" [documented - Listing quality help page].
- Manage Your Experiments lets you A/B test product title, main images, bullet
  points, product description, A+ Content and Brand Story; results report sales and
  conversion plus the probability that the winning content is better [documented].
- Experiment-to-significance concludes when a version reaches 66% significance
  [documented]. Own-duration experiments recommended 8-10 weeks; to-significance can
  conclude in about four weeks [documented].
- A+ Content can increase sales by up to 8%; Premium A+ up to 20% [documented as
  Amazon's own marketing claim - a company claim, not an independent test].
- Brands reported up to 25% sales increase with Manage Your Experiments and 15%
  conversion improvement [documented as Amazon's own claim, 2022 brand reports].

### 3.2 Seller lore / vendor-reported (NOT Amazon-documented)

- Rufus/COSMO read images with OCR and vision-language models as a ranking signal,
  so text overlays and infographic text are now "indexed" [inferred - no Amazon
  source]. A vendor guide states plainly that AMAZON HAS NOT PUBLISHED DOCUMENTATION
  specifying which image signals influence recommendation outcomes, how visual
  analysis is weighted relative to listing text, or which image features are most
  influential [documented by the vendor as an absence].
- A+ Content body text is claimed NOT to be indexed by A9 or COSMO and instead
  trains the assistant through conversions [inferred - trade press].
- Overlap between AI recommendations and traditional page-one results: one vendor
  claims 22% overlap over 1,000+ products; Marketplace Pulse measured 1,963 queries /
  12,810 recommendations with 63.9% NOT in the organic top 10 [inferred - two
  vendor measurements that cannot both be precise]. Treat every percentage here as
  vendor-measured, never Amazon-published.
- Amazon is claimed to be REMOVING seller-written alt text from A+ Content modules
  in a phased rollout starting 2025 through 2026, with an AI generating image
  descriptions instead, and that Amazon has published nothing about it [inferred -
  single trade-press claim, MUST be verified before building an alt-text workflow].

### 3.3 Rufus / assistant facts that are dated and reportable

- Rufus integrated into Lens Live, which scans items pictured on websites and social
  feeds to produce real-time product matches; available to tens of millions of
  customers in the Amazon Shopping app on iOS, rolling out further [observed - trade
  press, Sept 2025].

DESIGN CONSEQUENCE FOR NORTHSTAR: we must not build a feature that promises
"this will improve your ranking through image text". The defensible propositions are:
(a) pass documented compliance checks so the listing is not suppressed;
(b) support Amazon's OWN A/B experiment loop (Manage Your Experiments) so the
operator can measure creative impact themselves;

---

## 4. Brand Registry features that gate creative

GATED BEHIND BRAND REGISTRY [documented]:
- A+ Content (basic, premium) and Brand Story
- Sponsored Brands ads (sellers must be registered brand owners through Brand Registry)
- Manage Your Experiments (Brand Representative for an enrolled brand)
- Amazon Brand Store / Storefront
- Premium A+ additionally needs Brand Story published on all brand-owned listings

ELIGIBILITY [documented]:
- Active registered trademark OR a pending trademark registration
- Must be a text-based (word) mark or an image-based mark with words/letters/numbers
- Issued by an approved government IP office of a country with a corresponding Amazon store
- Applicant must be the trademark owner, or an authorised agent with the owner
  enrolling first and adding them
- Trademark text must match the brand name exactly; number must match the record exactly
- IP Accelerator allows enrollment while the application is pending

CRITICAL CONSTRAINT ON AI CREATIVE [documented - Brand Registry Application Guide]:
Product images submitted for enrollment must be ACTUAL PHOTOS of the product.
Amazon does NOT consider a mock-up or digitally altered image (e.g. brand name or
logo photoshopped onto the product or packaging) valid proof of IP ownership.
Submitting one may cause additional scrutiny or REMOVAL from the program.
Stickers, labels, stamps and tags are not considered permanent brand affixation.

This is a hard design constraint: mockup/packaging creative is fine for marketing
use, but must never be offered as what to upload for Brand Registry enrollment.

---

## 5. Policy risks of AI imagery on Amazon (hard constraint on the design)

DOCUMENTED RULES [documented]:
- A+ Content: AI-generated people that are photorealistic require disclosure. Add the
  IPTC keyword `contains-synthetic-performer` to the `dc:subject` (XMP) field, or use
  the "AI-generated" / "AI-generated people" checkbox when uploading in A+ Content
  Manager.
- Do NOT tag when: the image features only real people (even if altered with AI
  tools); only characters from films/games/expressive works; contains no people; or
  the people are not photorealistic.
- Brand Registry enrollment rejects mockups and digitally altered product images as
  proof of ownership (see section 4).
- Listing quality: images must accurately represent the product and show only the
  product that is for sale.

SUBSTANTIATED COMPLIANCE RISK [inferred]: an AI-generated lifestyle or infographic
that shows a feature the real product does not have is a misrepresentation risk
(product-accuracy complaints). Amazon's own guidance requires the image to
accurately represent the product.

DESIGN CONSEQUENCE: every AI generation path in Design Studio must (1) preserve the
operator's real product pixels as the base layer, (2) never add claims not present in
the listing copy (a vendor guide explicitly calls the mismatch between infographic
claims and listing copy a "consistency gap" that AI detects), (3) carry a
pre-flight disclosure checklist before any export, and (4) record provenance
(prompt, model, seed, base asset) on every generated asset so the operator can audit
what was synthesised.

---

## 6. What this means for the Northstar Design Studio (build implications)

1. A SPEC REGISTRY as the single source of truth for every format above. Each export
   preset validates width, height, aspect, format, colour space, DPI and file size
   before it is offered. No manual sizes anywhere in the UI.
2. A COMPLIANCE PRE-CHECK that runs the documented main-image rules (white
   background, 85% fill, no text/logo/watermark, min dimension, format, DPI) and
   the A+ rules (RGB, <2 MB, alt text present, uniqueness), returning pass/fail with
   the specific rule that failed.
3. HONEST SAFE-ZONE OVERLAYS for the 8 slots/types that document crop/safe zones:
   main image frame, Store hero (16% crop each side + logo 18% left), Store image
   tiles with link titles (19% bottom rectangle / 12% bottom square), A+ overlay
   modules, Sponsored Brands video text (no text bottom-right corner), video first
   3 seconds / core message in 5 seconds.
4. BULK VARIATION SETS: one project -> per-child main image plus additional images,
   using the flat-file column schema (`main_image_url`, `other_image_url1..8`,
   `swatch_image_url`) as the export contract, and a PartialUpdate-safe diff view so
   an operator can see exactly what a feed will blank.
5. AN EXPERIMENT HOOK: the Design Studio project model must carry the
   Manage Your Experiments vocabulary (Version A / Version B, attribute tested,
   eligible ASIN, significance) so a creative A/B tracker in Phase 2+ maps onto
   Amazon's own measurement tool rather than inventing a parallel score.
6. AN AI DISCLOSURE STEP in every export path that writes IPTC
   `contains-synthetic-performer` metadata when the asset contains photorealistic
   AI-generated people.
7. NEVER PRESENT a mockup as valid Brand Registry enrollment proof.

---

## 7. Open questions for the operator

1. Do we want to attempt A+ alt-text authoring at all, given the trade-press claim
   that Amazon is removing seller-written alt text in 2025-2026? (Needs
   verification before building.)
2. Is there a marketplace beyond US we must support? Store tile specs and Brand
   Registry eligibility differ per country and we only captured US here.
3. Do we want to model the lifestyle-main-image exception (BED, BED_FRAME,
   MATTRESS, RUG, RUG_PAD, SOFA) in the compliance checker, or keep the checker
   conservative and let the operator override with a reason?
4. Should the export flow generate flat files directly, or only produce assets plus
   a manifest the operator maps into Seller Central?
